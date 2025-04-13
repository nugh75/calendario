import pandas as pd
import streamlit as st
import os
import bcrypt
import sys
from typing import List, Dict, Any, Union
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Importa il sistema di logging
from log_utils import logger

# Importa le utility centralizzate per la gestione dei file
from file_utils import (
    load_data, save_data, delete_record, format_date,
    DEFAULT_CSV_PATH, DATA_FOLDER
)
# Importa le funzioni per la gestione di Excel
from excel_utils import (
    process_excel_upload, create_sample_excel as create_sample_excel_central
)
# Importa le funzioni per la manipolazione dei dati
from data_utils import (
    create_new_record, edit_record
)

# Costanti
# Ottieni la password dall'ambiente invece che hardcoded
ADMIN_PASSWORD = os.getenv("PS", "password_default")
# Flag per attivare l'hashing delle password (per retrocompatibilità)
USE_PASSWORD_HASHING = True

# Definizione delle colonne complete del dataset
FULL_COLUMNS = ['Data', 'Orario', 'Dipartimento', 'Classe di concorso', 
               'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 
               'PeF36 all.5', 'PeF30 art.13', 'Codice insegnamento',
               'Denominazione Insegnamento', 'Docente', 'Aula', 
               'Link Teams', 'CFU', 'Note', 'Giorno', 'Mese', 'Anno']

def verify_password(password: str) -> bool:
    """
    Verifica la password dell'amministratore utilizzando bcrypt per una maggiore sicurezza.
    
    Args:
        password: La password inserita dall'utente
        
    Returns:
        bool: True se la password è corretta, False altrimenti
    """
    try:
        # Se l'hashing è attivato, utilizza bcrypt
        if USE_PASSWORD_HASHING:
            # Controlla se la password è già stata hashata in precedenza
            if 'hashed_password' not in st.session_state:
                # Prima esecuzione: hash della password di ambiente
                password_bytes = ADMIN_PASSWORD.encode('utf-8')
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(password_bytes, salt)
                st.session_state.hashed_password = hashed
                
            # Verifica la password con bcrypt
            return bcrypt.checkpw(password.encode('utf-8'), st.session_state.hashed_password)
        else:
            # Metodo legacy di confronto diretto (meno sicuro)
            return password == ADMIN_PASSWORD
    except Exception as e:
        # Log dell'errore
        logger.error(f"Errore nella verifica della password: {e}")
        # Fallback al metodo legacy in caso di errore
        return password == ADMIN_PASSWORD

def login_admin(password):
    """
    Verifica le credenziali e imposta lo stato di autenticazione.
    Registra anche i tentativi di accesso nei log.
    
    Args:
        password: La password inserita dall'utente
        
    Returns:
        bool: True se l'autenticazione è riuscita, False altrimenti
    """
    # Verifica la password
    is_valid = verify_password(password)
    
    if is_valid:
        # Autenticazione riuscita
        st.session_state.authenticated = True
        st.session_state.admin_logged_in = True
        logger.info("Accesso amministratore riuscito")
        return True
    else:
        # Autenticazione fallita - log del tentativo fallito
        logger.warning("Tentativo di accesso amministratore fallito")
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

def upload_excel_file(uploaded_file):
    """
    Processa un file Excel caricato e gestisce i record duplicati,
    dando all'utente la possibilità di decidere se includerli o meno.
    L'utente può esaminare i dati prima di confermare l'implementazione.
    
    Args:
        uploaded_file: File Excel caricato tramite st.file_uploader
        
    Returns:
        bool: True se l'importazione è avvenuta con successo, False altrimenti
    """
    # Importa il sistema di logging
    try:
        from log_utils import logger
    except ImportError:
        logger = None
    
    if uploaded_file is None:
        st.warning("Nessun file selezionato per l'importazione.")
        return False
    
    # Inizializza lo stato della sessione per l'upload se non esiste
    if 'excel_upload' not in st.session_state:
        st.session_state.excel_upload = {
            'processed': False,
            'new_df': None,
            'duplicate_records': None,
            'unique_records': None,
            'existing_df': None,
            'action_selected': False,
            'action': None,
            'duplicate_keys': None,
            'key_columns': ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento']
        }
    
    # FASE 1: Elaborazione iniziale del file Excel
    if not st.session_state.excel_upload['processed']:
        # Processa il file Excel
        new_df = process_excel_upload(uploaded_file)
        
        if new_df is None or len(new_df) == 0:
            st.error("Impossibile processare il file Excel.")
            return False
        
        # Carica i dati esistenti
        existing_df = load_data()
        
        st.session_state.excel_upload['new_df'] = new_df
        st.session_state.excel_upload['existing_df'] = existing_df
        
        # Identifica i record duplicati
        if len(existing_df) > 0:
            # Crea una chiave di confronto per identificare i duplicati
            key_columns = st.session_state.excel_upload['key_columns']
            
            # Crea colonna temporanea per identificare i duplicati
            existing_df['temp_key'] = existing_df[key_columns].astype(str).agg('-'.join, axis=1)
            new_df['temp_key'] = new_df[key_columns].astype(str).agg('-'.join, axis=1)
            
            # Identifica i duplicati
            duplicate_keys = set(existing_df['temp_key']).intersection(set(new_df['temp_key']))
            duplicate_records = new_df[new_df['temp_key'].isin(duplicate_keys)]
            unique_records = new_df[~new_df['temp_key'].isin(duplicate_keys)]
            
            # Rimuovi la colonna temporanea
            existing_df_clean = existing_df.drop('temp_key', axis=1)
            new_df_clean = new_df.drop('temp_key', axis=1)
            if not duplicate_records.empty:
                duplicate_records = duplicate_records.drop('temp_key', axis=1)
            if not unique_records.empty:
                unique_records = unique_records.drop('temp_key', axis=1)
            
            st.session_state.excel_upload['duplicate_keys'] = duplicate_keys
            st.session_state.excel_upload['duplicate_records'] = duplicate_records
            st.session_state.excel_upload['unique_records'] = unique_records
            st.session_state.excel_upload['existing_df'] = existing_df_clean
            st.session_state.excel_upload['new_df'] = new_df_clean
        
        st.session_state.excel_upload['processed'] = True
    
    # Recupera i dataframe dalle variabili di sessione
    new_df = st.session_state.excel_upload['new_df']
    existing_df = st.session_state.excel_upload['existing_df']
    duplicate_records = st.session_state.excel_upload['duplicate_records']
    unique_records = st.session_state.excel_upload['unique_records']
    duplicate_keys = st.session_state.excel_upload['duplicate_keys']
    key_columns = st.session_state.excel_upload['key_columns']
    
    # FASE 2: Mostra i dati importati e permetti di esaminarli
    st.subheader("Anteprima dei dati importati")
    
    # Mostra i dati complessivi da importare
    with st.expander("📋 Visualizza tutti i dati da importare", expanded=True):
        st.dataframe(new_df)
    
    # FASE 3: Gestione dei duplicati (se presenti)
    if duplicate_records is not None and len(duplicate_records) > 0:
        st.warning(f"⚠️ Trovati {len(duplicate_records)} record duplicati su {len(new_df)} totali.")
        
        # Mostra i record duplicati
        with st.expander("🔍 Visualizza solo i record duplicati", expanded=True):
            st.dataframe(duplicate_records)
        
        # Mostra i record unici
        if len(unique_records) > 0:
            with st.expander("✨ Visualizza solo i record unici"):
                st.dataframe(unique_records)
        
        # Chiedi all'utente cosa fare con i duplicati
        action = st.radio(
            "Come vuoi gestire i record duplicati?",
            ["Salta duplicati (importa solo record unici)", 
             "Sostituisci duplicati (aggiorna i record esistenti)",
             "Importa tutti (includi anche i duplicati)"]
        )
        
        st.session_state.excel_upload['action'] = action
        st.session_state.excel_upload['action_selected'] = True
    else:
        # Nessun duplicato trovato
        st.success(f"✅ Nessun duplicato trovato tra i {len(new_df)} record da importare.")
        st.session_state.excel_upload['action'] = "Importa tutti"
        st.session_state.excel_upload['action_selected'] = True
    
    # FASE 4: Conferma e implementazione
    if st.session_state.excel_upload['action_selected']:
        # Mostra un riepilogo dell'azione che verrà eseguita
        action = st.session_state.excel_upload['action']
        
        if action == "Salta duplicati (importa solo record unici)":
            if duplicate_records is not None and len(unique_records) == 0:
                st.info("Non ci sono record unici da importare.")
                if st.button("Annulla importazione"):
                    # Reset dello stato
                    st.session_state.excel_upload = {
                        'processed': False,
                        'new_df': None,
                        'duplicate_records': None,
                        'unique_records': None,
                        'existing_df': None,
                        'action_selected': False,
                        'action': None,
                        'duplicate_keys': None,
                        'key_columns': key_columns
                    }
                    st.rerun()
                return False
            
            st.info(f"Verranno importati {len(unique_records) if unique_records is not None else len(new_df)} record unici.")
        
        elif action == "Sostituisci duplicati (aggiorna i record esistenti)":
            if duplicate_records is not None and len(duplicate_records) > 0:
                st.info(f"Verranno importati tutti i {len(new_df)} record, sostituendo {len(duplicate_records)} record esistenti.")
            else:
                st.info(f"Verranno importati tutti i {len(new_df)} record.")
        
        else:  # "Importa tutti"
            total = len(new_df)
            duplicates = len(duplicate_records) if duplicate_records is not None else 0
            st.info(f"Verranno importati tutti i {total} record, inclusi {duplicates} duplicati.")
        
        # Bottone di conferma
        confirm_col, cancel_col = st.columns(2)
        
        with confirm_col:
            if st.button("✅ Conferma importazione"):
                # Implementa la scelta dell'utente
                if action == "Salta duplicati (importa solo record unici)":
                    if duplicate_records is not None and len(unique_records) == 0:
                        st.info("Non ci sono record unici da importare.")
                        return False
                    
                    # Salva solo i record unici
                    final_df = pd.concat([existing_df, unique_records], ignore_index=True)
                    result = save_data(final_df)
                    
                    st.success(f"✅ Importati {len(unique_records)} record unici. {len(duplicate_records)} record duplicati sono stati saltati.")
                    if logger:
                        logger.info(f"Excel import: {len(unique_records)} record unici importati, {len(duplicate_records)} duplicati saltati")
                    
                elif action == "Sostituisci duplicati (aggiorna i record esistenti)":
                    if duplicate_records is not None and len(duplicate_records) > 0:
                        # Rimuovi i record duplicati esistenti e aggiungi le nuove versioni
                        non_duplicate_existing = existing_df[~existing_df[key_columns].astype(str).agg('-'.join, axis=1).isin(duplicate_keys)]
                        final_df = pd.concat([non_duplicate_existing, new_df], ignore_index=True)
                    else:
                        final_df = pd.concat([existing_df, new_df], ignore_index=True)
                    
                    result = save_data(final_df)
                    
                    st.success(f"✅ Importati tutti i {len(new_df)} record. {len(duplicate_records) if duplicate_records is not None else 0} record esistenti sono stati aggiornati.")
                    if logger:
                        logger.info(f"Excel import: {len(new_df)} record importati, {len(duplicate_records) if duplicate_records is not None else 0} record esistenti aggiornati")
                    
                else:  # "Importa tutti"
                    # Unisci tutti i record
                    final_df = pd.concat([existing_df, new_df], ignore_index=True)
                    result = save_data(final_df)
                    
                    st.success(f"✅ Importati tutti i {len(new_df)} record, inclusi {len(duplicate_records) if duplicate_records is not None else 0} duplicati.")
                    if logger:
                        logger.info(f"Excel import: Tutti i {len(new_df)} record importati, inclusi {len(duplicate_records) if duplicate_records is not None else 0} duplicati")
                
                # Reset dello stato dell'importazione
                st.session_state.excel_upload = {
                    'processed': False,
                    'new_df': None,
                    'duplicate_records': None,
                    'unique_records': None,
                    'existing_df': None,
                    'action_selected': False,
                    'action': None,
                    'duplicate_keys': None,
                    'key_columns': key_columns
                }
                
                return True
        
        with cancel_col:
            if st.button("❌ Annulla importazione"):
                # Reset dello stato
                st.session_state.excel_upload = {
                    'processed': False,
                    'new_df': None,
                    'duplicate_records': None,
                    'unique_records': None,
                    'existing_df': None,
                    'action_selected': False,
                    'action': None,
                    'duplicate_keys': None,
                    'key_columns': key_columns
                }
                st.rerun()
    
    return False


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

def admin_interface(df: pd.DataFrame) -> pd.DataFrame:
    """
    Interfaccia di amministrazione per gestire i record del calendario.
    
    Args:
        df: DataFrame contenente i dati
        
    Returns:
        pd.DataFrame: DataFrame aggiornato dopo le operazioni
    """
    st.header("Amministrazione Calendario")
    
    # Crea tab per le diverse funzionalità
    admin_tabs = st.tabs(["Visualizza Records", "Aggiungi Record", "Modifica Record", "Elimina Record"])
    
    # Copia del dataframe originale per i filtri
    display_df = df.copy()
    
    # Aggiungi filtri nella sidebar
    with st.sidebar:
        st.markdown("### 🔍 Filtri Records")
        
        # Funzionalità di ricerca
        search_term = st.text_input("Cerca nei record", 
                                  placeholder="Docente, insegnamento, data...",
                                  key="admin_search")
        
        st.markdown("---")
        
        # Filtro per Docente
        docenti = sorted(df['Docente'].dropna().unique())
        docente_selected = st.multiselect("Docente:", docenti, key="admin_filter_docente")
        
        # Filtro per Insegnamento
        insegnamenti = sorted(df['Denominazione Insegnamento'].dropna().unique())
        insegnamento_selected = st.multiselect("Insegnamento:", insegnamenti, key="admin_filter_insegnamento")
        
        # Filtro per Dipartimento
        dipartimenti = sorted(df['Dipartimento'].dropna().unique())
        dipartimento_selected = st.multiselect("Dipartimento:", dipartimenti, key="admin_filter_dipartimento")
            
        # Filtro per Classe di concorso
        classi_concorso = sorted(df['Classe di concorso'].dropna().unique())
        classe_concorso_selected = st.multiselect("Classe di concorso:", classi_concorso, key="admin_filter_classe")
        
        st.markdown("---")
        
        # Filtri temporali
        st.markdown("#### 📅 Filtri temporali")
        
        # Filtro per Mese
        mesi = sorted(df['Mese'].dropna().unique())
        mese_selected = st.multiselect("Mese:", mesi, key="admin_filter_mese")
            
        # Filtro per intervallo di date
        # Determina le date minime e massime nel dataset
        min_date = df['Data'].min().date() if not df['Data'].empty else pd.Timestamp.now().date()
        max_date = df['Data'].max().date() if not df['Data'].empty else pd.Timestamp.now().date()
        
        st.markdown("##### Intervallo date")
        
        date_start = st.date_input(
            "Data inizio:",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            key="admin_date_start"
        )
        
        date_end = st.date_input(
            "Data fine:",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
            key="admin_date_end"
        )
        
        use_date_range = st.checkbox("Filtra per intervallo date", key="admin_use_date_range")
        
        st.markdown("---")
        
        # Filtro per percorsi formativi
        st.markdown("#### 🎓 Percorsi formativi")
        
        pef_col1, pef_col2 = st.columns(2)
        
        with pef_col1:
            pef60_selected = st.checkbox("PeF60 (60 CFU)", key="admin_filter_pef60")
            pef36_selected = st.checkbox("PeF36 all.5 (36 CFU)", key="admin_filter_pef36")
            
        with pef_col2:
            pef30_all2_selected = st.checkbox("PeF30 all.2 (30 CFU)", key="admin_filter_pef30_all2")
            pef30_art13_selected = st.checkbox("PeF30 art.13 (30 CFU)", key="admin_filter_pef30_art13")
            
        st.markdown("---")
        
        # Selettore delle colonne da visualizzare
        st.markdown("#### 👁️ Visualizzazione Colonne")
        
        # Definisci tutte le colonne disponibili con etichette user-friendly
        available_columns = {
            'Data': 'Data',
            'Orario': 'Orario',
            'Dipartimento': 'Dipartimento',
            'Classe di concorso': 'Classe di concorso', 
            'Insegnamento comune': 'Insegnamento comune',
            'PeF60 all.1': 'PeF60 all.1',
            'PeF30 all.2': 'PeF30 all.2',
            'PeF36 all.5': 'PeF36 all.5',
            'PeF30 art.13': 'PeF30 art.13',
            'Codice insegnamento': 'Codice insegnamento',
            'Denominazione Insegnamento': 'Denominazione Insegnamento',
            'Docente': 'Docente',
            'Aula': 'Aula',
            'Link Teams': 'Link Teams', 
            'CFU': 'CFU',
            'Note': 'Note'
        }
        
        # Colonne predefinite (obbligatorie)
        default_columns = ['Data', 'Orario', 'Denominazione Insegnamento', 'Docente', 'Aula']
        
        # Selezione delle colonne da visualizzare
        if 'admin_selected_columns' not in st.session_state:
            st.session_state.admin_selected_columns = default_columns
                
        columns_to_display = st.multiselect(
            "Seleziona le colonne da visualizzare:",
            options=list(available_columns.keys()),
            default=st.session_state.admin_selected_columns,
            format_func=lambda x: available_columns[x],
            key="admin_columns_multiselect"
        )
        
        # Assicurati che ci siano sempre alcune colonne minime selezionate
        if not columns_to_display:
            columns_to_display = default_columns
            st.warning("Seleziona almeno una colonna. Sono state ripristinate le colonne predefinite.")
        
        # Aggiorna lo stato della sessione
        st.session_state.admin_selected_columns = columns_to_display
    
    # Tab per visualizzare i record
    with admin_tabs[0]:
        st.subheader("Elenco Records")
        
        # Filtra i risultati in base a tutti i criteri
        # Prima applica la ricerca testuale
        if search_term:
            # Cerca in tutte le colonne di stringhe
            mask = pd.Series(False, index=display_df.index)
            for col in display_df.columns:
                if display_df[col].dtype == 'object':  # Solo colonne di tipo object (stringhe)
                    mask = mask | display_df[col].fillna('').astype(str).str.lower().str.contains(search_term.lower())
            display_df = display_df[mask]
        
        # Applica i filtri avanzati
        # Filtro per docente
        if docente_selected:
            display_df = display_df[display_df['Docente'].isin(docente_selected)]
            
        # Filtro per insegnamento
        if insegnamento_selected:
            display_df = display_df[display_df['Denominazione Insegnamento'].isin(insegnamento_selected)]
            
        # Filtro per classe di concorso
        if classe_concorso_selected:
            display_df = display_df[display_df['Classe di concorso'].isin(classe_concorso_selected)]
            
        # Filtro per mese
        if mese_selected:
            display_df = display_df[display_df['Mese'].isin(mese_selected)]
        
        # Filtro per intervallo date
        if use_date_range:
            date_start_ts = pd.Timestamp(date_start)
            date_end_ts = pd.Timestamp(date_end)
            display_df = display_df[(display_df['Data'] >= date_start_ts) & (display_df['Data'] <= date_end_ts)]
            
        # Filtro per percorsi formativi
        pef_filters = []
        
        if pef60_selected:
            pef_filters.append((display_df['PeF60 all.1'] == 'P') | (display_df['PeF60 all.1'] == 'D'))
            
        if pef30_all2_selected:
            pef_filters.append((display_df['PeF30 all.2'] == 'P') | (display_df['PeF30 all.2'] == 'D'))
            
        if pef36_selected:
            pef_filters.append((display_df['PeF36 all.5'] == 'P') | (display_df['PeF36 all.5'] == 'D'))
            
        if pef30_art13_selected:
            pef_filters.append((display_df['PeF30 art.13'] == 'P') | (display_df['PeF30 art.13'] == 'D'))
        
        # Applica i filtri dei percorsi formativi se almeno uno è selezionato
        if pef_filters:
            combined_filter = pd.Series(False, index=display_df.index)
            for pef_filter in pef_filters:
                combined_filter = combined_filter | pef_filter
            display_df = display_df[combined_filter]
            
        # Mostra il conteggio dei risultati filtrati
        st.info(f"Trovati {len(display_df)} record corrispondenti ai filtri.")
        
        # Mostra i record
        if len(display_df) > 0:
            # Usa le colonne selezionate dall'utente nella sidebar
            view_cols = st.session_state.admin_selected_columns
            
            # Se sono selezionati percorsi formativi specifici, assicurati che le loro colonne siano incluse
            pef_cols_to_include = []
            if pef60_selected and 'PeF60 all.1' not in view_cols:
                pef_cols_to_include.append('PeF60 all.1')
            if pef30_all2_selected and 'PeF30 all.2' not in view_cols:
                pef_cols_to_include.append('PeF30 all.2')
            if pef36_selected and 'PeF36 all.5' not in view_cols:
                pef_cols_to_include.append('PeF36 all.5')
            if pef30_art13_selected and 'PeF30 art.13' not in view_cols:
                pef_cols_to_include.append('PeF30 art.13')
                
            # Aggiungi le colonne dei percorsi selezionati se non sono già incluse
            if pef_cols_to_include:
                view_cols = view_cols + pef_cols_to_include
            
            # Converti 'Data' al formato stringa per visualizzazione
            view_df = display_df.copy()
            view_df['Data'] = view_df['Data'].apply(format_date)
            
            st.dataframe(view_df[view_cols], use_container_width=True, height=400)
        else:
            st.warning("Nessun record trovato.")
    
    # Tab per aggiungere un nuovo record
    with admin_tabs[1]:
        df = create_new_record(df)
    
    # Tab per modificare un record
    with admin_tabs[2]:
        st.subheader("Modifica Record")
        
        # Crea un filtro per trovare il record da modificare
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            edit_search = st.text_input("Cerca il record da modificare", key="edit_search")
        with search_col2:
            edit_search_btn = st.button("Trova")
        
        # Filtra i risultati per la modifica
        edit_df = df.copy()
        if edit_search:
            # Cerca in tutte le colonne di stringhe
            mask = pd.Series(False, index=edit_df.index)
            for col in edit_df.columns:
                if edit_df[col].dtype == 'object':  # Solo colonne di tipo object (stringhe)
                    mask = mask | edit_df[col].fillna('').astype(str).str.lower().str.contains(edit_search.lower())
            edit_df = edit_df[mask]
        
        # Se ci sono risultati, mostra la lista di record
        if len(edit_df) > 0:
            # Visualizza i record con tutte le colonne rilevanti
            edit_df['Data_str'] = edit_df['Data'].apply(format_date)
            
            # Mostra tutte le colonne rilevanti
            view_cols = ['Data_str', 'Orario', 'Dipartimento', 'Classe di concorso', 'Insegnamento comune', 
                      'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
                      'Codice insegnamento', 'Denominazione Insegnamento', 'Docente', 'Aula', 
                      'Link Teams', 'CFU', 'Note']
            
            # Crea una copia per la visualizzazione
            edit_view = edit_df.copy()
            # Rinomina solo la colonna Data_str per coerenza
            view_cols_renamed = ['Data'] + view_cols[1:]
            
            # Seleziona le colonne da visualizzare
            edit_view = edit_view[view_cols]
            
            st.dataframe(edit_view, use_container_width=True, height=300)
            
            # Selezione del record da modificare
            record_indices = edit_df.index.tolist()
            record_options = [f"{i+1}. {format_date(edit_df.iloc[i]['Data'])} - {edit_df.iloc[i]['Orario']} - {edit_df.iloc[i]['Denominazione Insegnamento']} ({edit_df.iloc[i]['Docente']})" 
                            for i in range(len(edit_df))]
            
            selected_record = st.selectbox("Seleziona il record da modificare:", 
                                         record_options, 
                                         key="edit_select")
            
            if selected_record:
                # Ottieni l'indice del record selezionato
                selected_idx = record_indices[record_options.index(selected_record)]
                
                # Pulsante per confermare la modifica
                if st.button("Modifica questo record"):
                    df = edit_record(df, selected_idx)
        else:
            if edit_search:
                st.warning("Nessun record trovato con questi criteri di ricerca.")
            else:
                st.info("Inserisci un termine di ricerca per trovare il record da modificare.")
    
    # Tab per eliminare un record
    with admin_tabs[3]:
        st.subheader("Elimina Record")
        
        # Crea un filtro per trovare il record da eliminare
        del_col1, del_col2 = st.columns([3, 1])
        with del_col1:
            del_search = st.text_input("Cerca il record da eliminare", key="del_search")
        with del_col2:
            del_search_btn = st.button("Trova", key="del_search_btn")
        
        # Filtra i risultati per l'eliminazione
        del_df = df.copy()
        if del_search:
            # Cerca in tutte le colonne di stringhe
            mask = pd.Series(False, index=del_df.index)
            for col in del_df.columns:
                if del_df[col].dtype == 'object':  # Solo colonne di tipo object (stringhe)
                    mask = mask | del_df[col].fillna('').astype(str).str.lower().str.contains(del_search.lower())
            del_df = del_df[mask]
        
        # Se ci sono risultati, mostra la lista di record
        if len(del_df) > 0:
            # Visualizza i record con tutte le colonne rilevanti
            del_df['Data_str'] = del_df['Data'].apply(format_date)
            
            # Mostra tutte le colonne rilevanti
            view_cols = ['Data_str', 'Orario', 'Dipartimento', 'Classe di concorso', 'Insegnamento comune', 
                      'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
                      'Codice insegnamento', 'Denominazione Insegnamento', 'Docente', 'Aula', 
                      'Link Teams', 'CFU', 'Note']
            
            # Crea una copia per la visualizzazione
            del_view = del_df.copy()
            
            # Seleziona le colonne da visualizzare
            del_view = del_view[view_cols]
            
            st.dataframe(del_view, use_container_width=True, height=300)
            
            # Selezione del record da eliminare
            del_record_indices = del_df.index.tolist()
            del_record_options = [f"{i+1}. {format_date(del_df.iloc[i]['Data'])} - {del_df.iloc[i]['Orario']} - {del_df.iloc[i]['Denominazione Insegnamento']} ({del_df.iloc[i]['Docente']})" 
                                for i in range(len(del_df))]
            
            selected_del_record = st.selectbox("Seleziona il record da eliminare:", 
                                             del_record_options, 
                                             key="del_select")
            
            if selected_del_record:
                # Ottieni l'indice del record selezionato
                selected_del_idx = del_record_indices[del_record_options.index(selected_del_record)]
                
                # Pulsante per confermare l'eliminazione con conferma
                st.warning("⚠️ Questa operazione non può essere annullata!")
                
                # Usa una colonna per allineare il pulsante a sinistra
                _, col2, _ = st.columns([1, 2, 1])
                with col2:
                    if st.button("❌ Elimina record", key="confirm_delete"):
                        df = delete_record(df, selected_del_idx)
                        st.experimental_rerun()  # Ricarica l'interfaccia
        else:
            if del_search:
                st.warning("Nessun record trovato con questi criteri di ricerca.")
            else:
                st.info("Inserisci un termine di ricerca per trovare il record da eliminare.")
    
    return df
