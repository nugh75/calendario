import pandas as pd
import streamlit as st
import os
import bcrypt
from typing import List, Dict, Any, Union

# Importa le utility centralizzate per la gestione dei file
from file_utils import (
    load_data, save_data, delete_record, process_excel_upload,
    create_sample_excel as create_sample_excel_central,
    DEFAULT_CSV_PATH, DATA_FOLDER
)

# Costanti
# Password hardcoded per semplificare l'autenticazione
ADMIN_PASSWORD = "2025pef"

def verify_password(password: str) -> bool:
    """Verifica la password dell'amministratore."""
    return password == ADMIN_PASSWORD

def login_admin(password):
    """Verifica le credenziali e imposta lo stato di autenticazione."""
    if verify_password(password):
        st.session_state.authenticated = True
        st.session_state.admin_logged_in = True
        return True
    return False

def logout_admin():
    """Disconnette l'amministratore."""
    st.session_state.authenticated = False
    st.session_state.admin_logged_in = False
    return True

def is_admin_logged_in():
    """Verifica se l'amministratore è autenticato."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = st.session_state.authenticated
    return st.session_state.authenticated

def upload_excel_file(uploaded_file=None):
    """
    Processa un file Excel caricato con controllo duplicati.
    
    Args:
        uploaded_file: File Excel caricato tramite st.file_uploader
    
    Returns:
        DataFrame: Il dataframe caricato dal file Excel, o None in caso di errore
    """
    if uploaded_file is None:
        uploaded_file = st.file_uploader("Carica il file Excel", type=["xlsx", "xls"])
        if uploaded_file is None:
            return None
    
    try:
        # Carica i nuovi dati dall'Excel
        new_df = process_excel_upload(uploaded_file)
        if new_df is None or new_df.empty:
            st.error("Il file non contiene dati validi.")
            return None
            
        # Carica i dati esistenti
        existing_df = load_data()
        if existing_df is None:
            existing_df = pd.DataFrame(columns=FULL_COLUMNS)
            
        # Identifica i duplicati
        # Usiamo le stesse colonne chiave usate nella funzione save_data
        duplicate_mask = pd.Series(False, index=new_df.index)
        
        # Per ogni record nel nuovo dataframe, controlla se esiste già
        for idx, row in new_df.iterrows():
            # Cerca record con stessa data, orario, docente e insegnamento
            match_mask = (
                (existing_df['Data'].dt.date == row['Data'].date() if pd.notna(row['Data']) else False) & 
                (existing_df['Orario'] == row['Orario']) & 
                (existing_df['Docente'] == row['Docente']) & 
                (existing_df['Denominazione Insegnamento'] == row['Denominazione Insegnamento'])
            )
            
            if match_mask.any():
                duplicate_mask.at[idx] = True
        
        # Separa i nuovi record dai duplicati
        duplicates_df = new_df[duplicate_mask].copy()
        new_records_df = new_df[~duplicate_mask].copy()
        
        # Mostra all'utente le statistiche
        total_records = len(new_df)
        new_count = len(new_records_df)
        dup_count = len(duplicates_df)
        
        st.info(f"File Excel analizzato: {total_records} record totali")
        st.info(f"• {new_count} nuovi record da importare")
        st.info(f"• {dup_count} record duplicati")
        
        if dup_count > 0:
            st.warning("⚠️ Sono stati trovati record duplicati")
            
            # Mostra i duplicati
            if st.expander("Mostra record duplicati"):
                duplicates_df['Data'] = duplicates_df['Data'].apply(format_date)
                view_cols = ['Data', 'Orario', 'Denominazione Insegnamento', 'Docente']
                st.dataframe(duplicates_df[view_cols], use_container_width=True)
            
            # Opzioni per gestire i duplicati
            dup_action = st.radio(
                "Come gestire i record duplicati?",
                ["Importa solo i nuovi record", 
                 "Sovrascrivi i record esistenti con i duplicati", 
                 "Importa tutti i record (crea duplicati)"]
            )
        else:
            dup_action = "Importa solo i nuovi record"  # Default se non ci sono duplicati
        
        # Procedi con l'importazione in base alla scelta
        if st.button("Conferma importazione"):
            if dup_action == "Importa solo i nuovi record":
                if new_count > 0:
                    save_data(new_records_df)
                    st.success(f"{new_count} nuovi record importati con successo.")
                else:
                    st.info("Nessun nuovo record da importare.")
                    
            elif dup_action == "Sovrascrivi i record esistenti con i duplicati":
                # Per sovrascrivere, prima eliminiamo i record duplicati esistenti
                for idx, row in duplicates_df.iterrows():
                    match_mask = (
                        (existing_df['Data'].dt.date == row['Data'].date() if pd.notna(row['Data']) else False) & 
                        (existing_df['Orario'] == row['Orario']) & 
                        (existing_df['Docente'] == row['Docente']) & 
                        (existing_df['Denominazione Insegnamento'] == row['Denominazione Insegnamento'])
                    )
                    # Rimuovi i record duplicati
                    existing_df = existing_df[~match_mask]
                
                # Aggiungi tutti i nuovi record
                save_data(pd.concat([existing_df, new_df], ignore_index=True), replace_file=True)
                st.success(f"{total_records} record importati, sovrascrivendo i duplicati.")
                
            else:  # "Importa tutti i record (crea duplicati)"
                save_data(new_df)
                st.success(f"{total_records} record importati (inclusi i duplicati).")
            
            return new_df
        
        return None
        
    except Exception as e:
        st.error(f"Errore durante il caricamento del file: {e}")
        import traceback
        st.error(f"Dettaglio: {traceback.format_exc()}")
        return None

def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida i dati importati e rimuove righe non valide.
    """
    # Rimuovi righe con valori mancanti nelle colonne essenziali
    df = df.dropna(subset=['Data', 'Orario', 'Dipartimento', 'Docente'])
    
    # Rimuovi righe con date non valide
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    df = df.dropna(subset=['Data'])
    
    return df

def save_dataframe_to_csv(df: pd.DataFrame, path: str = 'dati') -> str:
    """
    Funzione wrapper che chiama la funzione centralizzata save_data.
    """
    # Utilizza la funzione centralizzata di salvataggio
    return save_data(df)

def create_sample_excel():
    """
    Wrapper per la funzione centralizzata create_sample_excel.
    
    Returns:
        str: Percorso del file Excel creato
    """
    return create_sample_excel_central()
