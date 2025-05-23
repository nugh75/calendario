"""
Utility per la gestione dei file del calendario lezioni.
Questo modulo centralizza tutte le operazioni di lettura, scrittura ed eliminazione dei file.
"""

import os
import pandas as pd
import streamlit as st
import traceback
import time
from typing import Union, Tuple, Dict, Any, List, Optional

# Importa utility per date e dati dai nuovi moduli
from date_utils import setup_locale, format_date, extract_date_components, parse_date
from data_utils import BASE_COLUMNS, FULL_COLUMNS

# Importa le operazioni di database dai nuovi moduli
from db_operations import load_data, save_data, delete_record
from db_edit_operation import edit_record

# Definizione delle liste di classi di concorso per i gruppi A e B
# Classi che mostrano anche risultati della Trasversale A quando cercate
CLASSI_GRUPPO_A = [
    'A001', 'A007', 'A008', 'A011', 'A012', 'A013', 'A017', 'A018', 'A019',
    'A022', 'A023', 'AA24', 'AB24', 'AC24', 'AL24', 'A029', 'A030',
    'A037', 'A053', 'A054', 'A061', 'A063', 'A064'
]

# Classi che mostrano anche risultati della Trasversale B quando cercate
CLASSI_GRUPPO_B = [
    'A020', 'A026', 'A027', 'A028', 'A040', 'A042', 'A045', 'A046',
    'A050', 'A060', 'B015'
]

# Costanti per i file
DATA_FOLDER = 'dati'
DEFAULT_JSON_FILE = 'dati.json'
DEFAULT_JSON_PATH = os.path.join(DATA_FOLDER, DEFAULT_JSON_FILE)

def setup_logger():
    """
    Inizializza e restituisce il logger se disponibile.
    
    Returns:
        tuple: (log_available, logger_instance)
    """
    try:
        from log_utils import logger
        return True, logger
    except ImportError:
        return False, None

def load_from_sqlite():
    """
    Tenta di caricare i dati dal database SQLite.
    
    Returns:
        pd.DataFrame o None: DataFrame con i dati o None in caso di errore
    """
    log_available, logger = setup_logger()
    
    try:
        from db_utils import load_data as load_data_db
        
        if log_available:
            logger.info("Tentativo di caricamento dati da SQLite...")
        
        db_df = load_data_db()
        
        # Se ha funzionato e ci sono dati, restituisci il DataFrame
        if db_df is not None and len(db_df) > 0:
            if log_available:
                logger.info(f"Dati caricati con successo da SQLite: {len(db_df)} record")
            return db_df
        
        # Se non ci sono dati nel DB, torna al metodo JSON
        if log_available:
            logger.info("Nessun dato trovato nel database SQLite, utilizzo il metodo JSON")
        return None
    except ImportError:
        # Se db_utils non è disponibile, log e continua con JSON
        if log_available:
            logger.info("Modulo db_utils non disponibile, utilizzo il metodo JSON")
        return None
    except Exception as db_error:
        # In caso di errore con SQLite, log e continua con JSON
        if log_available:
            logger.warning(f"Errore nel caricamento dati da SQLite: {db_error}, utilizzo il metodo JSON")
        return None

def find_json_file():
    """
    Trova il file JSON da utilizzare per caricare i dati.
    
    Returns:
        tuple: (file_path, empty_df)
    """
    log_available, logger = setup_logger()
    empty_df = pd.DataFrame(columns=FULL_COLUMNS)
    
    # Controlla se il file JSON esiste
    if not os.path.exists(DEFAULT_JSON_PATH):
        if log_available:
            logger.warning(f"File JSON {DEFAULT_JSON_PATH} non trovato.")
        
        # Cerca altri file JSON come fallback
        if not os.path.exists(DATA_FOLDER):
            if log_available:
                logger.warning(f"Cartella {DATA_FOLDER} non trovata, creazione...")
            os.makedirs(DATA_FOLDER, exist_ok=True)
            return None, empty_df
        
        json_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.json')]
        if not json_files:
            if log_available:
                logger.warning("Nessun file JSON trovato nella cartella 'dati'")
            return None, empty_df
            
        # Usa il file JSON più recente come fallback
        file_path = os.path.join(DATA_FOLDER, sorted(json_files)[-1])
        if log_available:
            logger.info(f"Usando file JSON alternativo: {file_path}")
    else:
        file_path = DEFAULT_JSON_PATH
        if log_available:
            logger.debug(f"File JSON trovato: {file_path}")
    
    # Verifica che il file sia leggibile
    if not os.path.isfile(file_path):
        if log_available:
            logger.error(f"Il percorso {file_path} non è un file valido.")
        return None, empty_df
    
    if os.path.getsize(file_path) == 0:
        if log_available:
            logger.warning(f"Il file JSON {file_path} è vuoto.")
        return None, empty_df
    
    return file_path, empty_df

def process_excel_upload(uploaded_file, debug_container=None) -> pd.DataFrame:
    """
    Processa un file Excel caricato dall'utente.
    I campi Giorno, Mese e Anno vengono generati automaticamente dalla colonna Data.
    
    Args:
        uploaded_file: File Excel caricato tramite st.file_uploader
        debug_container: Container Streamlit per i messaggi di debug (opzionale)
        
    Returns:
        pd.DataFrame: DataFrame con i dati del file, o None in caso di errore
    """
    if uploaded_file is None:
        st.warning("Nessun file selezionato per l'importazione.")
        return None
    
    # Inizializza la barra di progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Funzione di aggiornamento della barra di progresso
    def update_progress(step, total_steps, message=""):
        progress = int(step / total_steps * 100)
        progress_bar.progress(progress)
        if message:
            status_text.text(f"Fase {step}/{total_steps}: {message}")
    
    # Crea un debug_container fittizio se non fornito
    if debug_container is None:
        from fixed_logger_debug_container import LoggerDebugContainer
        debug_container = LoggerDebugContainer()
    
    # Definisci il numero totale di passaggi per il tracking del progresso
    total_steps = 8  # 8 passaggi per includere la validazione SQLite
    current_step = 0
    
    try:
        # Passo 1: Preparazione e localizzazione
        current_step += 1
        update_progress(current_step, total_steps, "Preparazione e impostazione localizzazione")
        debug_container.text("Avvio processo di importazione Excel...")
        
        # Imposta localizzazione italiana
        setup_locale()
        log_available, logger = setup_logger()
        
        # Passo 2: Tentativo di lettura del file Excel
        current_step += 1
        update_progress(current_step, total_steps, "Lettura del file Excel")
        
        # Definisci i tipi di dati attesi per le colonne problematiche
        expected_dtypes = {
            'Aula': str,
            'Link Teams': str,
            'Note': str,
            'CFU': str,  # Leggi come stringa per gestire virgole/punti
            'Codice insegnamento': str # Leggi come stringa per preservare formati
        }
        # Assicurati che tutte le colonne base siano definite
        for col in BASE_COLUMNS:
            if col not in expected_dtypes:
                expected_dtypes[col] = object # Default a object (stringa) se non specificato
                
        # Prima leggi il file senza saltare righe per ispezionarlo
        try:
            preview_df = pd.read_excel(uploaded_file, nrows=10)
            
            # Determina automaticamente se ci sono righe di intestazione da saltare
            skip_rows = 0
            headers_detected = False
            
            # Esamina le prime righe per trovare intestazioni standard
            header_keywords = ["calendario", "lezioni", "percorsi", "formazione", "docenti"]
            for i in range(min(5, len(preview_df))):  # Controlla solo le prime 5 righe
                row_text = ' '.join([str(val).lower() for val in preview_df.iloc[i].values if pd.notna(val)])
                if any(keyword in row_text for keyword in header_keywords):
                    skip_rows = i + 1  # Salta questa riga e tutte quelle precedenti
                    headers_detected = True
            
            # Se non sono state rilevate intestazioni standard, mantieni il comportamento predefinito (3 righe)
            if not headers_detected:
                skip_rows = 3  # Comportamento predefinito
                debug_container.info(f"Nessuna intestazione standard rilevata. Utilizzo comportamento predefinito: {skip_rows} righe saltate.")
            else:
                debug_container.success(f"Rilevate intestazioni standard. Saltate {skip_rows} righe.")
            
            # Ora leggi il file con il numero corretto di righe da saltare
            df = pd.read_excel(uploaded_file, skiprows=skip_rows, dtype=expected_dtypes)
            
            # Verifica iniziale della struttura del file
            if len(df) == 0:
                progress_bar.empty()
                status_text.empty()
                st.error("⚠️ Importazione fallita: Il file Excel caricato è vuoto.")
                return None
                
            if len(df.columns) < 4:  # Minimo di colonne essenziali (Data, Orario, Docente, Denominazione)
                progress_bar.empty()
                status_text.empty()
                st.error("⚠️ Importazione fallita: Il file Excel non ha la struttura corretta. Mancano colonne essenziali.")
                st.info("Scarica il template per vedere la struttura corretta.")
                return None
                
        except Exception as excel_err:
            progress_bar.empty()
            status_text.empty()
            st.error(f"⚠️ Importazione fallita: Errore nella lettura del file Excel. {excel_err}")
            st.info("Assicurati che il file sia nel formato Excel (.xlsx o .xls) e che non sia danneggiato.")
            return None
        
        # Passo 3: Gestione delle colonne
        current_step += 1
        update_progress(current_step, total_steps, "Preparazione delle colonne")
        
        # Gestisci solo le colonne essenziali (senza Giorno, Mese, Anno)
        essential_columns = BASE_COLUMNS  # Colonne essenziali escludendo Giorno, Mese, Anno
        
        # Mostra informazioni sulle colonne rilevate
        debug_container.info(f"Colonne rilevate nel file: {len(df.columns)}")
        debug_container.info(f"Nomi delle colonne: {df.columns.tolist()}")
        
        # Se ci sono meno colonne del previsto
        if len(df.columns) <= len(essential_columns):
            # Assegna i nomi delle colonne disponibili
            df.columns = essential_columns[:len(df.columns)]
            # Aggiungi colonne essenziali mancanti
            for col in essential_columns[len(df.columns):]:
                df[col] = None
                debug_container.warning(f"Aggiunta colonna mancante: {col}")
        else:
            # Se ci sono più colonne del previsto, prendi solo le colonne essenziali
            df = df.iloc[:, :len(essential_columns)]
            df.columns = essential_columns
            debug_container.warning(f"Rimosse colonne in eccesso. Mantenute solo le prime {len(essential_columns)} colonne.")
        
        # Passo 4: Pulizia dei dati 
        current_step += 1
        update_progress(current_step, total_steps, "Pulizia dei dati")
        df = clean_dataframe(df)
        
        # Passo 5: Gestione delle date
        current_step += 1
        update_progress(current_step, total_steps, "Conversione e validazione delle date")
        df = process_dates(df)
        
        # Passo 6: Pulizia valori nulli
        current_step += 1
        update_progress(current_step, total_steps, "Pulizia valori nulli")
        df = clean_null_values(df)
        
        # Passo 7: Validazione finale
        current_step += 1
        update_progress(current_step, total_steps, "Validazione finale")
        
        # Calcola il totale dei CFU
        total_cfu = 0
        if 'CFU' in df.columns:
            # Assicurati che tutti i valori CFU siano numerici
            df['CFU'] = pd.to_numeric(df['CFU'], errors='coerce')
            total_cfu = df['CFU'].fillna(0).sum()
            debug_container.info(f"Totale CFU calcolati: {total_cfu}")
            
        # Aggiorna il conteggio dei record e dei CFU nella sessione
        st.session_state['total_records'] = len(df)
        st.session_state['total_cfu'] = total_cfu
        
        # Completa la barra di progresso
        progress_bar.progress(100)
        
        # Mostra il risultato finale
        record_count = len(df)
        if record_count > 0:
            status_text.text(f"✅ Importazione completata: {record_count} record validi importati.")
            st.success(f"✅ File Excel elaborato con successo: {record_count} record validi importati.")
        else:
            progress_bar.empty()
            status_text.empty()
            st.error("⚠️ Importazione fallita: Nessun record valido trovato nel file.")
            return None
        
        # Resetta la barra di progresso dopo un breve ritardo
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
        
        return df
    except Exception as e:
        # Pulizia dell'interfaccia in caso di errore
        progress_bar.empty()
        status_text.empty()
        
        error_message = f"Errore durante l'elaborazione del file: {e}"
        st.error(f"⚠️ Importazione fallita: {error_message}")
        st.info("Dettagli tecnici dell'errore sono stati registrati nei log.")
        debug_container.error(error_message)
        debug_container.error(f"Dettaglio: {traceback.format_exc()}")
        return None
        
def read_json_file(file_path):
    """
    Legge un file JSON e restituisce un DataFrame.
    
    Args:
        file_path: Percorso del file JSON
        
    Returns:
        pd.DataFrame: DataFrame con i dati del file
    """
    log_available, logger = setup_logger()
    
    try:
        # Lettura del JSON con gestione robusta degli errori
        df = pd.read_json(file_path, orient='records')
        
        if log_available:
            logger.debug(f"JSON caricato. Shape: {df.shape}, colonne: {df.columns.tolist()}")
        
        # Verifica delle colonne
        if len(df.columns) < 4:  # Minimo necessario per i dati essenziali
            if log_available:
                logger.warning(f"Il file JSON ha solo {len(df.columns)} colonne, potrebbero mancare dati essenziali.")
        
        # Assicurati che il dataframe abbia tutte le colonne necessarie
        for col in FULL_COLUMNS:
            if col not in df.columns:
                df[col] = None
        
        return df
    except Exception as e:
        if log_available:
            logger.error(f"Errore durante la lettura del file JSON: {e}")
        return pd.DataFrame(columns=FULL_COLUMNS)

def clean_dataframe(df):
    """
    Pulisce il DataFrame rimuovendo righe vuote e normalizzando i dati.
    
    Args:
        df: DataFrame da pulire
        
    Returns:
        pd.DataFrame: DataFrame pulito
    """
    log_available, logger = setup_logger()
    
    # Rimuovi righe completamente vuote
    original_rows = len(df)
    df = df.dropna(how='all')
    if log_available and original_rows > len(df):
        logger.debug(f"Righe dopo rimozione vuote: {len(df)} (rimosse {original_rows - len(df)})")
    
    # Filtra le righe che hanno almeno l'orario compilato
    if 'Orario' in df.columns:
        rows_before = len(df)
        df = df[df['Orario'].notna() & (df['Orario'] != '')]
        if log_available and rows_before > len(df):
            logger.debug(f"Righe dopo filtro orario: {len(df)} (rimosse {rows_before - len(df)})")
    
    return df
            
def process_dates(df):
    """
    Elabora le date nel DataFrame, convertendole in formato datetime e 
    generando le colonne Giorno, Mese e Anno.
    
    Args:
        df: DataFrame con dati da elaborare
        
    Returns:
        pd.DataFrame: DataFrame con date elaborate
    """
    log_available, logger = setup_logger()
    
    if 'Data' not in df.columns:
        return df
        
    if log_available:
        logger.debug(f"Tipo della colonna Data prima della conversione: {df['Data'].dtype}")
        if len(df) > 0:
            logger.debug(f"Esempi valori Data: {df['Data'].head().tolist()}")
    
    try:
        # Verifica se le date sono già in formato datetime
        if not pd.api.types.is_datetime64_any_dtype(df['Data']):
            # Prima converti a stringa per uniformare il formato
            df['Data'] = df['Data'].astype(str)
            # Poi converti a datetime
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        if log_available:
            logger.debug(f"Tipo della colonna Data dopo la conversione: {df['Data'].dtype}")
            if len(df) > 0:
                logger.debug(f"Esempi date convertite: {df['Data'].head().tolist()}")
        
        # Rimuovi le righe con date non valide
        rows_before = len(df)
        df = df.dropna(subset=['Data'])
        if log_available and rows_before > len(df):
            logger.debug(f"Righe dopo rimozione date invalide: {len(df)} (rimosse {rows_before - len(df)})")
        
        # Estrai e aggiorna le colonne di Giorno, Mese e Anno in modo sicuro
        if len(df) > 0:
            try:
                df['Giorno'] = df['Data'].dt.strftime('%A').str.capitalize()
                df['Mese'] = df['Data'].dt.strftime('%B').str.capitalize()
                df['Anno'] = df['Data'].dt.year.astype(str)
                if log_available:
                    logger.debug("Date elaborate con successo.")
            except Exception as date_comp_err:
                if log_available:
                    logger.warning(f"Errore durante l'estrazione dei componenti dalla data: {date_comp_err}")
                # Manteniamo i valori esistenti in caso di errore
    except Exception as date_err:
        if log_available:
            logger.error(f"Errore durante la conversione delle date: {date_err}")
    
    return df

def clean_null_values(df):
    """
    Pulisce i valori nulli nel DataFrame.
    
    Args:
        df: DataFrame da pulire
        
    Returns:
        pd.DataFrame: DataFrame senza valori nulli
    """
    log_available, logger = setup_logger()
    
    if log_available:
        logger.debug("Pulizia valori nulli e NaN...")
    
    # Sostituisci NaN con stringa vuota nelle colonne di testo
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].fillna('')
    
    # Se ci sono colonne oggetto con valori 'nan' come stringhe, sostituisci con stringa vuota
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].replace('nan', '')
        df[col] = df[col].replace('None', '')
    
    return df

# FASE 6: Finalizzazione
def process_final_data(df):
    """
    Esegue le operazioni di finalizzazione sul DataFrame.
    
    Args:
        df: DataFrame da finalizzare
        
    Returns:
        pd.DataFrame: DataFrame finalizzato
    """
    log_available, logger = setup_logger()
    
    if log_available:
        logger.debug(f"Dati caricati con successo. Totale record: {len(df)}")
    
    # Calcola il totale dei CFU
    total_cfu = 0
    if 'CFU' in df.columns:
        # Assicurati che tutti i valori CFU siano numerici
        df['CFU'] = pd.to_numeric(df['CFU'], errors='coerce')
        total_cfu = df['CFU'].fillna(0).sum()
        
        if print_debug:
            print(f"Totale CFU calcolati: {total_cfu}")
    
    # Aggiorna il conteggio dei record e dei CFU nella sessione
    st.session_state['total_records'] = len(df)
    st.session_state['total_cfu'] = total_cfu
    
    return df



# La funzione delete_record è stata spostata in db_delete_operations.py
from db_delete_operations import delete_record

def process_excel_upload(uploaded_file, debug_container=None) -> pd.DataFrame:
    """
    Processa un file Excel caricato dall'utente.
    I campi Giorno, Mese e Anno vengono generati automaticamente dalla colonna Data.
    
    Args:
        uploaded_file: File Excel caricato tramite st.file_uploader
        debug_container: Container Streamlit per i messaggi di debug (opzionale)
        
    Returns:
        pd.DataFrame: DataFrame con i dati del file, o None in caso di errore
    """
    if uploaded_file is None:
        st.warning("Nessun file selezionato per l'importazione.")
        return None
    
    # Inizializza la barra di progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Funzione di aggiornamento della barra di progresso
    def update_progress(step, total_steps, message=""):
        progress = int(step / total_steps * 100)
        progress_bar.progress(progress)
        if message:
            status_text.text(f"Fase {step}/{total_steps}: {message}")
    
    # Crea un debug_container fittizio se non fornito
    if debug_container is None:
        class DummyContainer:
            def text(self, message): 
                # Si può aggiungere un logger qui se necessario
                try:
                    from log_utils import logger
                    logger.debug(message)
                except ImportError:
                    pass
            def info(self, message): 
                try:
                    from log_utils import logger
                    logger.info(message)
                except ImportError:
                    pass
            def success(self, message): 
                try:
                    from log_utils import logger
                    logger.info(f"SUCCESS: {message}")
                except ImportError:
                    pass
            def warning(self, message): 
                try:
                    from log_utils import logger
                    logger.warning(message)
                except ImportError:
                    pass
            def error(self, message): 
                try:
                    from log_utils import logger
                    logger.error(message)
                except ImportError:
                    pass
            def expander(self, title): return self
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb): pass
        
        debug_container = DummyContainer()
    
    # Definisci il numero totale di passaggi per il tracking del progresso
    total_steps = 8  # Aggiornato a 8 per includere la validazione SQLite
    current_step = 0
    
    try:
        # Passo 1: Preparazione e localizzazione
        current_step += 1
        update_progress(current_step, total_steps, "Preparazione e impostazione localizzazione")
        debug_container.text("Avvio processo di importazione Excel...")
        # Imposta localizzazione italiana e verifica se è stato impostato correttamente
        locale_set = setup_locale()
        if not locale_set:
            debug_container.warning("Impossibile impostare la localizzazione italiana. I nomi di giorni e mesi potrebbero non essere in italiano.")
        
        # Passo 2: Tentativo di lettura del file Excel
        current_step += 1
        update_progress(current_step, total_steps, "Lettura del file Excel")
        
        # Definisci i tipi di dati attesi per le colonne problematiche
        expected_dtypes = {
            'Aula': str,
            'Link Teams': str,
            'Note': str,
            'CFU': str,  # Leggi come stringa per gestire virgole/punti
            'Codice insegnamento': str # Leggi come stringa per preservare formati
        }
        # Assicurati che tutte le colonne base siano definite
        for col in BASE_COLUMNS:
            if col not in expected_dtypes:
                expected_dtypes[col] = object # Default a object (stringa) se non specificato

        # Prima, tentiamo di leggere senza saltare righe per verificare la struttura del file
        try:
            # Leggi prima il file senza saltare righe per ispezionarlo
            preview_df = pd.read_excel(uploaded_file, nrows=10)
            
            # Determina automaticamente se ci sono righe di intestazione da saltare
            skip_rows = 0
            headers_detected = False
            
            # Esamina le prime righe per trovare intestazioni standard
            header_keywords = ["calendario", "lezioni", "percorsi", "formazione", "docenti"]
            for i in range(min(5, len(preview_df))):  # Controlla solo le prime 5 righe
                row_text = ' '.join([str(val).lower() for val in preview_df.iloc[i].values if pd.notna(val)])
                if any(keyword in row_text for keyword in header_keywords):
                    skip_rows = i + 1  # Salta questa riga e tutte quelle precedenti
                    headers_detected = True
            
            # Se non sono state rilevate intestazioni standard, mantieni il comportamento predefinito (3 righe)
            if not headers_detected:
                skip_rows = 3  # Comportamento predefinito
                debug_container.info(f"Nessuna intestazione standard rilevata. Utilizzo comportamento predefinito: {skip_rows} righe saltate.")
            else:
                debug_container.success(f"Rilevate intestazioni standard. Saltate {skip_rows} righe.")
            
            # Ora leggi il file con il numero corretto di righe da saltare
            df = pd.read_excel(uploaded_file, skiprows=skip_rows, dtype=expected_dtypes)
            
            # Verifica iniziale della struttura del file
            if len(df) == 0:
                progress_bar.empty()
                status_text.empty()
                st.error("⚠️ Importazione fallita: Il file Excel caricato è vuoto.")
                return None
                
            if len(df.columns) < 4:  # Minimo di colonne essenziali (Data, Orario, Docente, Denominazione)
                progress_bar.empty()
                status_text.empty()
                st.error("⚠️ Importazione fallita: Il file Excel non ha la struttura corretta. Mancano colonne essenziali.")
                st.info("Scarica il template per vedere la struttura corretta.")
                return None
                
        except Exception as excel_err:
            progress_bar.empty()
            status_text.empty()
            st.error(f"⚠️ Importazione fallita: Errore nella lettura del file Excel. {excel_err}")
            st.info("Assicurati che il file sia nel formato Excel (.xlsx o .xls) e che non sia danneggiato.")
            return None

        # Passo 3: Gestione delle colonne
        current_step += 1
        update_progress(current_step, total_steps, "Preparazione delle colonne")
        
        # Gestisci solo le colonne essenziali (senza Giorno, Mese, Anno)
        essential_columns = BASE_COLUMNS  # Colonne essenziali escludendo Giorno, Mese, Anno
        
        # Mostra informazioni sulle colonne rilevate
        debug_container.info(f"Colonne rilevate nel file: {len(df.columns)}")
        debug_container.info(f"Nomi delle colonne: {df.columns.tolist()}")
        
        # Se ci sono meno colonne del previsto
        if len(df.columns) <= len(essential_columns):
            # Assegna i nomi delle colonne disponibili
            df.columns = essential_columns[:len(df.columns)]
            # Aggiungi colonne essenziali mancanti
            for col in essential_columns[len(df.columns):]:
                df[col] = None
                debug_container.warning(f"Aggiunta colonna mancante: {col}")
        else:
            # Se ci sono più colonne del previsto, prendi solo le colonne essenziali
            df = df.iloc[:, :len(essential_columns)]
            df.columns = essential_columns
            debug_container.warning(f"Rimosse colonne in eccesso. Mantenute solo le prime {len(essential_columns)} colonne.")
        
        # Passo 4: Pulizia dei dati
        current_step += 1
        update_progress(current_step, total_steps, "Pulizia dei dati")
        
        # Pulizia IMMEDIATA dei dati dopo la lettura
        # Sostituisci tutti i NaN con stringhe vuote nelle colonne di tipo object
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].fillna('')
        
        # Rimuovi le stringhe 'nan', 'None', etc.
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].replace(['nan', 'None', 'NaN', 'none', '<NA>', 'null'], '', regex=False)
        
        # Filtra le righe con Orario mancante
        initial_rows = len(df)
        df = df[df['Orario'] != '']
        rows_after_orario = len(df)
        
        if rows_after_orario < initial_rows:
            removed_rows = initial_rows - rows_after_orario
            debug_container.warning(f"Rimosse {removed_rows} righe senza orario")
            if removed_rows > 0:
                status_text.text(f"Rimosse {removed_rows} righe senza orario")
        
        # Passo 5: Gestione delle date
        current_step += 1
        update_progress(current_step, total_steps, "Conversione e validazione delle date")
        
        # Converti le date in formato datetime con gestione robusta
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        # Rimuovi le righe con date non valide
        rows_before_date_filter = len(df)
        df = df.dropna(subset=['Data'])
        rows_after_date_filter = len(df)
        
        # Mostra avviso se sono state rimosse righe per date non valide
        if rows_after_date_filter < rows_before_date_filter:
            removed_date_rows = rows_before_date_filter - rows_after_date_filter
            debug_container.warning(f"Rimosse {removed_date_rows} righe con date non valide")
            status_text.text(f"Rimosse {removed_date_rows} righe con date non valide")
            
            if rows_after_date_filter == 0:
                progress_bar.empty()
                status_text.empty()
                st.error("⚠️ Importazione fallita: Tutte le date nel file sono non valide o in un formato non riconosciuto.")
                st.info("Controlla che le date siano nel formato YYYY-MM-DD o altro formato standard.")
                return None
        
        # Passo 6: Generazione campi derivati dalle date
        current_step += 1
        update_progress(current_step, total_steps, "Generazione campi Giorno, Mese e Anno")
        
        # Metodo migliorato per generare i campi Giorno e Mese in italiano
        # Utilizza la funzione format_date migliorata che abbiamo implementato
        # che include fallback per la localizzazione
        italian_days = {
            0: "lunedì", 1: "martedì", 2: "mercoledì", 3: "giovedì",
            4: "venerdì", 5: "sabato", 6: "domenica"
        }
        
        italian_months = {
            1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 
            6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 
            10: "ottobre", 11: "novembre", 12: "dicembre"
        }
        
        # Generiamo i giorni e mesi usando il mapping diretto invece di fare affidamento sulla localizzazione
        df['Giorno'] = df['Data'].apply(lambda x: italian_days.get(x.weekday(), "").capitalize())
        df['Mese'] = df['Data'].apply(lambda x: italian_months.get(x.month, "").capitalize())
        df['Anno'] = df['Data'].dt.year.astype(str)
        
        # Controlla se ci sono problemi con i campi generati
        if df['Giorno'].isna().any() or df['Mese'].isna().any():
            debug_container.warning("Attenzione: Alcuni nomi di Giorno o Mese potrebbero non essere stati generati correttamente")
            status_text.text("Attenzione: Alcuni campi relativi alle date potrebbero non essere completi")
        
        # Passo 7: Elaborazione finale e validazione
        current_step += 1
        update_progress(current_step, total_steps, "Validazione finale e normalizzazione dei dati")
        
        # Gestisci CFU (converti a float dopo aver pulito) con gestione più robusta
        if 'CFU' in df.columns:
            # Prima converti in stringa e sostituisci le virgole con punti
            df['CFU'] = df['CFU'].astype(str).str.replace(',', '.')
            # Pulisci i valori strani prima della conversione
            df['CFU'] = df['CFU'].replace(['', 'nan', 'None', 'NaN', 'none', '<NA>', 'null'], '0')
            # Ora converti in numerico, con gestione errori
            df['CFU'] = pd.to_numeric(df['CFU'], errors='coerce').fillna(0.0)
            
            # Log dei valori CFU
            debug_container.info(f"Valori CFU elaborati. Range: {df['CFU'].min()} - {df['CFU'].max()}")

        # Verifica campi essenziali con feedback più dettagliato
        missing_fields_rows = []
        for idx, row in df.iterrows():
            missing_fields = []
            
            if pd.isna(row['Docente']) or row['Docente'] == '':
                missing_fields.append('Docente')
                
            if pd.isna(row['Denominazione Insegnamento']) or row['Denominazione Insegnamento'] == '':
                missing_fields.append('Denominazione Insegnamento')
                
            if missing_fields:
                missing_fields_rows.append((idx, row['Data'], missing_fields))
        
        if missing_fields_rows:
            debug_container.warning(f"Trovate {len(missing_fields_rows)} righe con dati incompleti")
            status_text.text(f"Trovate {len(missing_fields_rows)} righe con dati essenziali mancanti")
            
            # Fornisci dettagli sui record problematici
            with st.expander("Dettagli record con dati incompleti"):
                for idx, data, campi in missing_fields_rows:
                    st.write(f"Riga {idx+1} ({data.strftime('%d/%m/%Y')}): Mancano {', '.join(campi)}")

        # Aggiungiamo un nuovo passo di validazione per SQLite
        current_step += 1
        update_progress(current_step, total_steps, "Validazione compatibilità con database SQLite")
        
        # Verifica compatibilità con SQLite
        sqlite_validation_ok = True
        sqlite_validation_message = ""
        try:
            # Tenta di importare db_utils per verificare lo schema del database
            from db_utils import validate_record_schema, get_db_schema
            
            # Campiona alcuni record per la validazione (max 5)
            sample_size = min(5, len(df))
            if sample_size > 0:
                sample_records = df.head(sample_size).to_dict('records')
                
                # Valida ogni record del campione
                validation_results = []
                for idx, record in enumerate(sample_records):
                    is_valid, message = validate_record_schema(record)
                    if not is_valid:
                        validation_results.append(f"Record {idx+1}: {message}")
                
                if validation_results:
                    sqlite_validation_ok = False
                    sqlite_validation_message = "\n".join(validation_results)
                    debug_container.warning(f"Problemi di compatibilità con SQLite: {len(validation_results)} errori trovati")
                else:
                    debug_container.success("Validazione SQLite: Tutti i record del campione sono compatibili con il database")
            
            # Log dello schema del database
            try:
                db_schema = get_db_schema()
                debug_container.info(f"Schema del database SQLite: {db_schema}")
            except Exception as schema_err:
                debug_container.warning(f"Impossibile recuperare lo schema del database: {str(schema_err)}")
                
        except ImportError:
            debug_container.info("Modulo db_utils non disponibile, saltata la validazione SQLite")
        except Exception as e:
            debug_container.warning(f"Errore durante la validazione SQLite: {str(e)}")
            debug_container.warning(traceback.format_exc())
        
        # Se ci sono problemi di compatibilità SQLite, mostra un avviso ma continua
        if not sqlite_validation_ok:
            with st.expander("⚠️ Avviso di compatibilità con il database"):
                st.warning("I dati importati potrebbero non essere completamente compatibili con il database SQLite.")
                st.write("Dettaglio problemi:")
                st.code(sqlite_validation_message)
                st.info("L'importazione può continuare, ma alcuni record potrebbero non essere salvati correttamente nel database.")
        
        # Completa la barra di progresso e mostra il risultato finale
        progress_bar.progress(100)
        
        # Log dei risultati
        record_count = len(df)
        if record_count > 0:
            status_text.text(f"✅ Importazione completata: {record_count} record validi importati.")
            st.success(f"✅ File Excel elaborato con successo: {record_count} record validi importati.")
        else:
            progress_bar.empty()
            status_text.empty()
            st.error("⚠️ Importazione fallita: Nessun record valido trovato nel file.")
            return None
            
        try:
            from log_utils import logger
            logger.info(f"File Excel processato: {len(df)} record validi. Tipi dopo process_excel_upload: {df.dtypes.to_dict()}")
            if not sqlite_validation_ok:
                logger.warning(f"Potenziali problemi di compatibilità con SQLite: {sqlite_validation_message}")
        except ImportError:
            pass
        
        # Resetta la barra di progresso dopo un breve ritardo
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
        
        return df
    except Exception as e:
        # Pulizia dell'interfaccia in caso di errore
        progress_bar.empty()
        status_text.empty()
        
        error_message = f"Errore durante l'elaborazione del file: {e}"
        st.error(f"⚠️ Importazione fallita: {error_message}")
        st.info("Dettagli tecnici dell'errore sono stati registrati nei log.")
        debug_container.error(error_message)
        debug_container.error(f"Dettaglio: {traceback.format_exc()}")
        return None

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
            
        # Filtro per insegnamento comune con funzionalità di ricerca testuale
        st.markdown("##### Cerca per insegnamento comune")
        insegnamento_comune_search = st.text_input("Cerca classe:", placeholder="Ad es.: A022, A023...", key="admin_filter_insegnamento_comune")
        
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
            
        st.markdown("---")            # Selettore delle colonne da visualizzare
        st.markdown("#### 👁️ Visualizzazione Colonne")
        
        # Definisci tutte le colonne disponibili con etichette user-friendly
        available_columns = {
            'Data': 'Data',
            'Orario': 'Orario',
            'Dipartimento': 'Dipartimento',
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
            
        # Filtro per insegnamento comune con logica avanzata per trasversali
        if insegnamento_comune_search:
            search_term_upper = insegnamento_comune_search.upper()
            
            # Inizializza la maschera di filtro base (ricerca standard nell'insegnamento comune)
            base_mask = display_df['Insegnamento comune'].fillna('').astype(str).str.upper().str.contains(search_term_upper)
            
            # Flag per sapere se dobbiamo aggiungere trasversali
            include_trasversale_a = False
            include_trasversale_b = False
            
            # Controlla se il termine di ricerca è una classe del gruppo A o B
            for classe in CLASSI_GRUPPO_A:
                if classe.upper() in search_term_upper or search_term_upper in classe.upper():
                    include_trasversale_a = True
                    break
                    
            for classe in CLASSI_GRUPPO_B:
                if classe.upper() in search_term_upper or search_term_upper in classe.upper():
                    include_trasversale_b = True
                    break
            
            # Crea la maschera finale
            final_mask = base_mask
            
            # Aggiungi i record della trasversale A o B se necessario
            if include_trasversale_a:
                trasversale_a_mask = display_df['Insegnamento comune'].fillna('').astype(str).str.upper().str.contains('TRASVERSALE A')
                final_mask = final_mask | trasversale_a_mask
                
            if include_trasversale_b:
                trasversale_b_mask = display_df['Insegnamento comune'].fillna('').astype(str).str.upper().str.contains('TRASVERSALE B')
                final_mask = final_mask | trasversale_b_mask
            
            # Applica il filtro finale
            display_df = display_df[final_mask]
            
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
        
        # Usa i filtri della sidebar per prefiltrare i records
        edit_df = display_df.copy()  # Usa display_df che ha già applicato i filtri della sidebar
        
        # Crea un filtro aggiuntivo oltre ai filtri della sidebar
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            edit_search = st.text_input("Filtro aggiuntivo", key="edit_search")
        with search_col2:
            edit_search_btn = st.button("Trova")
        
        # Applica il filtro di ricerca specifico se inserito
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
            
            # Mostra tutte le colonne rilevanti (rimossa 'Classe di concorso' perché obsoleta)
            view_cols = ['Data_str', 'Orario', 'Dipartimento', 'Insegnamento comune', 
                      'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
                      'Denominazione Insegnamento', 'Docente', 'Aula', 
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
                
                # Inizializza la variabile di stato se non esiste
                if 'edit_idx' not in st.session_state:
                    st.session_state.edit_idx = None
                
                # Pulsante per confermare la modifica
                if st.button("✏️ Modifica questo record", key=f'edit_btn_{selected_idx}'):
                    st.session_state.edit_idx = selected_idx
                
                # Mostra sempre la form finché l'indice è definito
                if st.session_state.edit_idx is not None:
                    df = edit_record(df, st.session_state.edit_idx)
        else:
            if edit_search:
                st.warning("Nessun record trovato con questi criteri di ricerca.")
            else:
                st.info("Inserisci un termine di ricerca per trovare il record da modificare.")
    
    # Tab per eliminare un record
    with admin_tabs[3]:
        st.subheader("Elimina Record")
        
        # Usa i filtri della sidebar per prefiltrare i records
        del_df = display_df.copy()  # Usa display_df che ha già applicato i filtri della sidebar
        
        # Crea un filtro aggiuntivo oltre ai filtri della sidebar
        del_col1, del_col2 = st.columns([3, 1])
        with del_col1:
            del_search = st.text_input("Filtro aggiuntivo", key="del_search")
        with del_col2:
            del_search_btn = st.button("Trova", key="del_search_btn")
        
        # Applica il filtro di ricerca specifico se inserito
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
            view_cols = ['Data_str', 'Orario', 'Dipartimento' , 'Insegnamento comune', 
                      'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
                      'Denominazione Insegnamento', 'Docente', 'Aula', 
                      'Link Teams', 'CFU', 'Note']
            
            # Crea una copia per la visualizzazione
            del_view = del_df.copy()
            
            # Seleziona le colonne da visualizzare
            del_view = del_view[view_cols]
            
            st.dataframe(del_view, use_container_width=True, height=300)
            
            # Pulsante per eliminazione multipla (posizionato subito dopo la tabella)
            st.info(f"Trovati {len(del_df)} record corrispondenti ai filtri attuali.")
            
            # Aggiungiamo checkbox per conferma eliminazione multipla
            col_multi1, col_multi2 = st.columns([3, 1])
            with col_multi1:
                multi_delete_confirm = st.checkbox("Confermo di voler eliminare tutti i record filtrati", key="multi_delete_confirm")
            with col_multi2:
                if multi_delete_confirm:
                    if st.button("❌ Elimina tutti i record filtrati", key="delete_all_filtered"):
                        # Importa la funzione di eliminazione multipla
                        from db_delete_operations import delete_filtered_records
                        # Elimina tutti i record filtrati
                        df = delete_filtered_records(df, del_df)
                        # Ricarica l'interfaccia
                        st.rerun()
            
            st.markdown("---")
            st.subheader("Eliminazione singolo record")
            
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

def create_sample_excel():
    """
    Crea un file Excel di esempio con la struttura corretta per l'importazione.
    Il modello è allineato con la struttura del database SQLite.
    
    Returns:
        str: Percorso del file Excel creato
    """
    import os
    import pandas as pd
    from datetime import datetime
    
    # Usiamo le costanti definite a livello di modulo per le colonne
    # BASE_COLUMNS e FULL_COLUMNS
    
    # Crea un DataFrame di esempio con le colonne necessarie
    sample_data = {col: [] for col in FULL_COLUMNS}
    df = pd.DataFrame(sample_data)
    
    # Aggiungi due righe di esempio
    example_rows = [
        {
            'Data': '2025-04-28', 
            'Orario': '14:30-16:45',
            'Dipartimento': 'Area Trasversale - Canale A',
            'Classe di concorso': 'Area Trasversale - Canale A',
            'Insegnamento comune': 'Trasversale A',
            'PeF60 all.1': 'D',
            'PeF30 all.2': 'D',
            'PeF36 all.5': 'D',
            'PeF30 art.13': 'D',
            'Denominazione Insegnamento': 'Pedagogia generale e interculturale',
            'Docente': 'Scaramuzzo Gilberto',
            'Aula': '',
            'Link Teams': '',
            'CFU': 0.5,  # Come numero decimale, non come stringa
            'Note': '',
            'Giorno': 'Lunedì',
            'Mese': 'Aprile',
            'Anno': '2025'
        },
        {
            'Data': '2025-04-29', 
            'Orario': '16:45-19:00',
            'Dipartimento': 'Scienze della Formazione',
            'Classe di concorso': 'A018',
            'Insegnamento comune': 'A018',
            'PeF60 all.1': 'P',
            'PeF30 all.2': 'P',
            'PeF36 all.5': 'P',
            'PeF30 art.13': 'D',
            'Denominazione Insegnamento': 'Didattica della psicologia',
            'Docente': 'Vecchio Giovanni Maria',
            'Aula': 'aula 15 Via Principe Amedeo, 182/b',
            'Link Teams': 'A018',
            'CFU': 0.5,  # Come numero decimale, non come stringa
            'Note': 'Esempio di nota',
            'Giorno': 'Martedì',
            'Mese': 'Aprile',
            'Anno': '2025'
        }
    ]
    
    df = pd.concat([df, pd.DataFrame(example_rows)], ignore_index=True)
    
    # Salva il DataFrame in un file Excel
    os.makedirs(DATA_FOLDER, exist_ok=True)
    template_path = os.path.join(DATA_FOLDER, 'template_calendario.xlsx')
    
    try:
        # Utilizzo di xlsxwriter per creare un Excel con formattazione
        writer = pd.ExcelWriter(template_path, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Calendario')
        
        # Ottieni il foglio di lavoro per applicare formattazione
        workbook = writer.book
        worksheet = writer.sheets['Calendario']
        
        # Formato per le intestazioni
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E6E6E6',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Applica formattazione alle intestazioni
        for col_num, column in enumerate(df.columns):
            worksheet.write(0, col_num, column, header_format)
            # Imposta la larghezza delle colonne
            worksheet.set_column(col_num, col_num, max(len(column) * 1.2, 12))
        
        # Aggiungi informazioni sul modello
        worksheet.write(len(df) + 2, 0, "Informazioni sul modello:")
        worksheet.write(len(df) + 3, 0, "• Le colonne con sfondo grigio sono obbligatorie")
        worksheet.write(len(df) + 4, 0, "• Il campo CFU deve essere un numero (es. 0.5)")
        worksheet.write(len(df) + 5, 0, "• I campi Giorno, Mese e Anno possono essere vuoti, verranno generati dalla Data")
        worksheet.write(len(df) + 6, 0, "• La Data deve essere nel formato YYYY-MM-DD (es. 2025-04-28)")
        worksheet.write(len(df) + 7, 0, "• L'Orario deve essere nel formato HH:MM-HH:MM (es. 14:30-16:45)")
        
        # Chiudi il writer per salvare il file
        writer.close()
    except ImportError:
        # Se xlsxwriter non è disponibile, usa il metodo standard
        df.to_excel(template_path, index=False)
    
    # Registra la creazione nel log, se disponibile
    try:
        from log_utils import logger
        logger.info(f"Creato modello Excel in: {template_path}")
    except ImportError:
        pass
    
    import os
    import pandas as pd
    from datetime import datetime
    
    # Usiamo le costanti definite a livello di modulo per le colonne
    # BASE_COLUMNS e FULL_COLUMNS
    
    # Crea un DataFrame di esempio con le colonne necessarie
    sample_data = {col: [] for col in FULL_COLUMNS}
    df = pd.DataFrame(sample_data)
    
    # Aggiungi due righe di esempio
    example_rows = [
        {
            'Data': '2025-04-28', 
            'Orario': '14:30-16:45',
            'Dipartimento': 'Area Trasversale - Canale A',
            'Classe di concorso': 'Area Trasversale - Canale A',
            'Insegnamento comune': 'Trasversale A',
            'PeF60 all.1': 'D',
            'PeF30 all.2': 'D',
            'PeF36 all.5': 'D',
            'PeF30 art.13': 'D',
            'Denominazione Insegnamento': 'Pedagogia generale e interculturale',
            'Docente': 'Scaramuzzo Gilberto',
            'Aula': '',
            'Link Teams': '',
            'CFU': 0.5,  # Come numero decimale, non come stringa
            'Note': '',
            'Giorno': 'Lunedì',
            'Mese': 'Aprile',
            'Anno': '2025'
        },
        {
            'Data': '2025-04-29', 
            'Orario': '16:45-19:00',
            'Dipartimento': 'Scienze della Formazione',
            'Classe di concorso': 'A018',
            'Insegnamento comune': 'A018',
            'PeF60 all.1': 'P',
            'PeF30 all.2': 'P',
            'PeF36 all.5': 'P',
            'PeF30 art.13': 'D',
            'Denominazione Insegnamento': 'Didattica della psicologia',
            'Docente': 'Vecchio Giovanni Maria',
            'Aula': 'aula 15 Via Principe Amedeo, 182/b',
            'Link Teams': 'A018',
            'CFU': 0.5,  # Come numero decimale, non come stringa
            'Note': 'Esempio di nota',
            'Giorno': 'Martedì',
            'Mese': 'Aprile',
            'Anno': '2025'
        }
    ]
    
    df = pd.concat([df, pd.DataFrame(example_rows)], ignore_index=True)
    
    # Salva il DataFrame in un file Excel
    os.makedirs(DATA_FOLDER, exist_ok=True)
    template_path = os.path.join(DATA_FOLDER, 'template_calendario.xlsx')
    
    try:
        # Utilizzo di xlsxwriter per creare un Excel con formattazione
        writer = pd.ExcelWriter(template_path, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Calendario')
        
        # Ottieni il foglio di lavoro per applicare formattazione
        workbook = writer.book
        worksheet = writer.sheets['Calendario']
        
        # Formato per le intestazioni
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E6E6E6',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Applica formattazione alle intestazioni
        for col_num, column in enumerate(df.columns):
            worksheet.write(0, col_num, column, header_format)
            # Imposta la larghezza delle colonne
            worksheet.set_column(col_num, col_num, max(len(column) * 1.2, 12))
        
        # Aggiungi informazioni sul modello
        worksheet.write(len(df) + 2, 0, "Informazioni sul modello:")
        worksheet.write(len(df) + 3, 0, "• Le colonne con sfondo grigio sono obbligatorie")
        worksheet.write(len(df) + 4, 0, "• Il campo CFU deve essere un numero (es. 0.5)")
        worksheet.write(len(df) + 5, 0, "• I campi Giorno, Mese e Anno possono essere vuoti, verranno generati dalla Data")
        worksheet.write(len(df) + 6, 0, "• La Data deve essere nel formato YYYY-MM-DD (es. 2025-04-28)")
        worksheet.write(len(df) + 7, 0, "• L'Orario deve essere nel formato HH:MM-HH:MM (es. 14:30-16:45)")
        
        # Chiudi il writer per salvare il file
        writer.close()
    except ImportError:
        # Se xlsxwriter non è disponibile, usa il metodo standard
        df.to_excel(template_path, index=False)
    
    # Registra la creazione nel log, se disponibile
    try:
        from log_utils import logger
        logger.info(f"Creato modello Excel in: {template_path}")
    except ImportError:
        pass
    
    return template_path
    # NB: Manteniamo i nomi delle colonne user-friendly, la conversione avviene durante l'importazione
    db_compatible_columns = [
        'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
        'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
        'Denominazione Insegnamento', 'Docente',
        'Aula', 'Link Teams', 'CFU', 'Note'
    ]
    
    # Aggiungi le colonne che vengono generate automaticamente dalla Data (non obbligatorie)
    full_columns = db_compatible_columns + ['Giorno', 'Mese', 'Anno']
    
    # Crea un DataFrame di esempio con le colonne necessarie
    sample_data = {col: [] for col in full_columns}
    df = pd.DataFrame(sample_data)
    
    # Aggiungi due righe di esempio
    example_rows = [
        {
            'Data': '2025-04-28', 
            'Orario': '14:30-16:45',
            'Dipartimento': 'Area Trasversale - Canale A',
            'Classe di concorso': 'Area Trasversale - Canale A',
            'Insegnamento comune': 'Trasversale A',
            'PeF60 all.1': 'D',
            'PeF30 all.2': 'D',
            'PeF36 all.5': 'D',
            'PeF30 art.13': 'D',
            'Denominazione Insegnamento': 'Pedagogia generale e interculturale',
            'Docente': 'Scaramuzzo Gilberto',
            'Aula': '',
            'Link Teams': '',
            'CFU': 0.5,  # Ora come numero, non come stringa
            'Note': '',
            'Giorno': 'Lunedì',
            'Mese': 'Aprile',
            'Anno': '2025'
        },
        {
            'Data': '2025-04-29', 
            'Orario': '16:45-19:00',
            'Dipartimento': 'Scienze della Formazione',
            'Classe di concorso': 'A018',
            'Insegnamento comune': 'A018',
            'PeF60 all.1': 'P',
            'PeF30 all.2': 'P',
            'PeF36 all.5': 'P',
            'PeF30 art.13': 'D',
            'Denominazione Insegnamento': 'Didattica della psicologia',
            'Docente': 'Vecchio Giovanni Maria',
            'Aula': 'aula 15 Via Principe Amedeo, 182/b',
            'Link Teams': 'A018',
            'CFU': 0.5,  # Ora come numero, non come stringa
            'Note': 'Esempio di nota',
            'Giorno': 'Martedì',
            'Mese': 'Aprile',
            'Anno': '2025'
        }
    ]
    
    df = pd.concat([df, pd.DataFrame(example_rows)], ignore_index=True)
    
    # Salva il DataFrame in un file Excel
    os.makedirs(DATA_FOLDER, exist_ok=True)
    template_path = os.path.join(DATA_FOLDER, 'template_calendario.xlsx')
    
    # Crea un writer Excel con formattazione
    with pd.ExcelWriter(template_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Calendario')
        
        # Ottieni il foglio di lavoro per applicare formattazione
        worksheet = writer.sheets['Calendario']
        
        # Applica formattazione alle intestazioni
        for col in range(1, len(full_columns) + 1):
            cell = worksheet.cell(row=1, column=col)
            cell.font = openpyxl.styles.Font(bold=True)
            cell.fill = openpyxl.styles.PatternFill(start_color='E6E6E6', end_color='E6E6E6', fill_type='solid')
        
        # Imposta la larghezza delle colonne
        for idx, col in enumerate(full_columns):
            worksheet.column_dimensions[openpyxl.utils.get_column_letter(idx+1)].width = 18
    
    # Aggiungi un commento al file Excel per spiegare compatibilità
    try:
        wb = openpyxl.load_workbook(template_path)
        sheet = wb.active
        # Aggiungi commento alla cella A1 con istruzioni per la compatibilità
        sheet['A1'].comment = openpyxl.comments.Comment(
            "Questo modello è ottimizzato per l'importazione nel database. "
            "Le colonne Giorno, Mese e Anno possono essere lasciate vuote, verranno generate automaticamente. "
            "Il campo CFU deve contenere numeri (es. 0.5).", "Sistema"
        )
        wb.save(template_path)
    except Exception:
        # Se la formattazione aggiuntiva fallisce, il file è comunque valido
        pass
    
    try:
        from log_utils import logger
        logger.info(f"Creato modello Excel in: {template_path}")
    except ImportError:
        pass
    
    return template_path


# Utilizziamo la funzione centralizzata da data_utils invece di quella locale
from data_utils import create_new_record
