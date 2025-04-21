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
    load_data, save_data, delete_record, DATA_FOLDER
)
from date_utils import format_date
from data_utils import create_new_record, edit_record
# Importa le funzioni per la gestione di Excel
from excel_utils import (
    process_excel_upload, create_sample_excel as create_sample_excel_central
)
# Importa le funzioni per la manipolazione dei dati
from data_utils import (
    create_new_record, edit_record
)

# Importa le funzioni per SQLite
try:
    from db_utils import save_record
except ImportError:
    logger.error("Impossibile importare le funzioni da db_utils")
    save_record = None

# Costanti
# Ottieni la password dall'ambiente invece che hardcoded
ADMIN_PASSWORD = os.getenv("PS", "password_default")
# Flag per attivare l'hashing delle password (per retrocompatibilità)
USE_PASSWORD_HASHING = True

# Definizione delle colonne complete del dataset
FULL_COLUMNS = ['Data', 'Orario', 'Dipartimento',
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
            'key_columns': ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento', 'Insegnamento comune']
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

def save_dataframe_to_db(df: pd.DataFrame, path: str = None) -> bool:
    """
    Salva un DataFrame nel database SQLite.
    
    Args:
        df: DataFrame contenente i dati da salvare
        path: Parametro ignorato, mantenuto per compatibilità
        
    Returns:
        bool: True se il salvataggio è riuscito, False altrimenti
    """
    try:
        # Log dell'operazione
        logger.info(f"Salvataggio di {len(df)} record nel database")
        
        # Verifica che la funzione save_record sia disponibile
        if save_record is None:
            logger.error("Funzione save_record non disponibile. Impossibile salvare i dati nel database.")
            return False
        
        # Salva ogni record nel database
        success_count = 0
        for _, row in df.iterrows():
            # Converti la riga in dizionario
            record_data = row.to_dict()
            
            # Salva nel database
            if save_record(record_data):
                success_count += 1
        
        logger.info(f"Salvataggio completato: {success_count}/{len(df)} record salvati con successo")
        return success_count > 0
    
    except Exception as e:
        # Log dell'errore
        logger.error(f"Errore nel salvataggio del DataFrame: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# Nota: le funzioni save_dataframe_to_csv e create_sample_excel sono state rimosse
# poiché erano solo wrapper per le funzioni centralizzate in altri moduli
# Utilizzare direttamente save_data() da file_utils.py e create_sample_excel_central() da excel_utils.py

def admin_interface(df: pd.DataFrame) -> pd.DataFrame:
    """
    Funzione wrapper che richiama l'interfaccia di amministrazione centralizzata in file_utils.
    Questa funzione è mantenuta per retrocompatibilità, ma utilizza l'implementazione
    centralizzata per evitare duplicazioni di codice.
    
    Args:
        df: DataFrame contenente i dati
        
    Returns:
        pd.DataFrame: DataFrame aggiornato dopo le operazioni
    """
    # Importa la funzione centralizzata da file_utils
    from file_utils import admin_interface as admin_interface_central
    
    # Utilizzo della funzione centralizzata
    return admin_interface_central(df)
