"""
Utility per la gestione dei file del calendario lezioni.
Questo modulo centralizza tutte le operazioni di lettura, scrittura ed eliminazione dei file.
"""

import os
import pandas as pd
import streamlit as st
import locale
import datetime
import traceback
from typing import Union, Tuple, Dict, Any, List, Optional

# Costanti per i file
DATA_FOLDER = 'dati'
DEFAULT_JSON_FILE = 'dati.json'
DEFAULT_JSON_PATH = os.path.join(DATA_FOLDER, DEFAULT_JSON_FILE)

# Manteniamo il vecchio path per compatibilità durante la migrazione
DEFAULT_CSV_FILE = 'dati.csv'
DEFAULT_CSV_PATH = os.path.join(DATA_FOLDER, DEFAULT_CSV_FILE)

# Costanti per le colonne
BASE_COLUMNS = [
    'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
    'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
    'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
    'Aula', 'Link Teams', 'CFU', 'Note'
]

FULL_COLUMNS = BASE_COLUMNS + ['Giorno', 'Mese', 'Anno']

# Costanti per le intestazioni dei file CSV
CSV_HEADERS = [
    "Calendario lezioni;;;;;;;;;;;;;;\n",
    "Percorsi di formazione iniziale dei docenti                   ;;;;;;;;;;;;;;;\n",
    "(DPCM 4 agosto 2023);;;;;;;;;;;;;;;\n"
]

def setup_locale() -> bool:
    """
    Imposta la localizzazione italiana per le date.
    
    Returns:
        bool: True se la localizzazione è stata impostata correttamente, False altrimenti
    """
    # Lista di possibili localizzazioni italiane in ordine di preferenza
    italian_locales = ['it_IT.UTF-8', 'it_IT.utf8', 'it_IT', 'it', 'Italian_Italy']
    
    # Salva la localizzazione corrente per poterla ripristinare in caso di errore
    current_locale = locale.getlocale(locale.LC_TIME)
    
    for loc in italian_locales:
        try:
            locale.setlocale(locale.LC_TIME, loc)
            return True
        except locale.Error:
            continue
    
    try:
        # Fallback: usa la localizzazione di default del sistema
        locale.setlocale(locale.LC_TIME, '')
        # Log dell'avviso
        from log_utils import logger
        logger.warning("Impossibile impostare la localizzazione italiana. Usata localizzazione di default.")
        return False
    except:
        # Ripristina la localizzazione originale se tutte le altre opzioni falliscono
        try:
            locale.setlocale(locale.LC_TIME, current_locale)
        except:
            pass
        return False

def format_date(date_obj_or_str) -> Optional[str]:
    """
    Formatta una data in un formato standardizzato italiano.
    
    Args:
        date_obj_or_str: Data come oggetto datetime o stringa
        
    Returns:
        str: Data formattata come stringa nel formato "lunedì 14 aprile 2025", o None se non valida
    """
    if pd.isna(date_obj_or_str):
        return None
    
    # Definizione dei nomi dei mesi italiani per la traduzione manuale se necessario
    italian_months = {
        1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 
        6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 
        10: "ottobre", 11: "novembre", 12: "dicembre"
    }
    
    # Definizione dei nomi dei giorni italiani per la traduzione manuale
    italian_days = {
        0: "lunedì", 1: "martedì", 2: "mercoledì", 3: "giovedì",
        4: "venerdì", 5: "sabato", 6: "domenica"
    }
    
    try:
        # 1. Se è un oggetto datetime, procedi direttamente con la formattazione
        if isinstance(date_obj_or_str, (pd.Timestamp, datetime.datetime)):
            date_obj = date_obj_or_str
        else:
            # 2. Se è una stringa, tenta di convertirla in datetime
            try:
                date_obj = pd.to_datetime(date_obj_or_str, errors='raise')
            except:
                # 3. Se la stringa è già in formato italiano, restituiscila normalizzata
                if isinstance(date_obj_or_str, str):
                    date_str_lower = date_obj_or_str.lower()
                    if any(month in date_str_lower for month in italian_months.values()):
                        return date_str_lower
                return None
        
        # Tenta la formattazione standard con localizzazione italiana
        try:
            # Verifica che la localizzazione italiana sia attiva
            locale_test = datetime.datetime(2025, 1, 1).strftime("%B")
            if locale_test.lower() in ["january", "jan", "gennaio", "gen"]:
                # Localizzazione funzionante, usa strftime
                return date_obj.strftime("%A %d %B %Y").lower()
            else:
                # Fallback: formattazione manuale
                raise Exception("Localizzazione non disponibile")
        except:
            # Fallback con traduzione manuale
            day_name = italian_days.get(date_obj.weekday(), "")
            month_name = italian_months.get(date_obj.month, "")
            if day_name and month_name:
                return f"{day_name} {date_obj.day:02d} {month_name} {date_obj.year}"
            else:
                # Ultimo fallback: formato internazionale
                return date_obj.strftime("%d/%m/%Y")
            
    except Exception as e:
        # Log dell'errore
        try:
            from log_utils import logger
            logger.error(f"Errore nella formattazione data: {e}")
        except:
            st.warning(f"Errore nella formattazione data: {e}")
    
    return None

def extract_date_components(date_str: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Estrae i componenti (giorno, mese, anno) da una data in formato stringa.
    
    Args:
        date_str: Data in formato "lunedì 14 aprile 2025"
        
    Returns:
        tuple: (giorno, mese, anno) come stringhe, o (None, None, None) se non valida
    """
    if pd.isna(date_str) or date_str == '':
        return None, None, None
        
    try:
        date = pd.to_datetime(date_str, format='%A %d %B %Y', errors='coerce')
        if pd.isna(date):
            return None, None, None
            
        giorno = date.strftime("%A").capitalize()
        mese = date.strftime("%B").capitalize()
        anno = str(date.year)
        return giorno, mese, anno
    
    except Exception as e:
        st.warning(f"Errore nell'estrazione dei componenti della data: {e}")
        return None, None, None

def normalize_code(code_str: str) -> str:
    """
    Normalizza un codice insegnamento rimuovendo eventuali decimali.
    
    Args:
        code_str: Stringa con il codice insegnamento
        
    Returns:
        str: Codice normalizzato
    """
    if pd.isna(code_str):
        return ""
    
    code_str = str(code_str)
    return code_str.split('.')[0] if '.' in code_str else code_str

def parse_date(date_str):
    """
    Converte una stringa data in oggetto datetime.
    
    Args:
        date_str: Data come stringa
        
    Returns:
        datetime: Data convertita o None se non valida
    """
    if pd.isna(date_str):
        return None
    try:
        # Prima prova il formato italiano
        return pd.to_datetime(date_str, format='%A %d %B %Y')
    except:
        try:
            # Poi prova il formato ISO
            date = pd.to_datetime(date_str)
            return date
        except:
            return None

def load_data() -> pd.DataFrame:
    """
    Funzione centralizzata per caricare i dati del calendario.
    Prima tenta di caricare da SQLite, se fallisce torna al metodo JSON.
    
    Returns:
        pd.DataFrame: Dataframe contenente i dati del calendario, o un DataFrame vuoto in caso di errore
    """
    try:
        # Configurazione iniziale
        setup_locale()
        print_debug = True  # Attiva per ottenere output di debug dettagliato
        
        # Inizializza il logger se disponibile
        try:
            from log_utils import logger
            log_available = True
            logger.debug("Inizio caricamento dati...")
        except ImportError:
            log_available = False
            if print_debug:
                print("Logger non disponibile")
        
        # Prima tenta di caricare i dati dal database SQLite
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
        except ImportError:
            # Se db_utils non è disponibile, log e continua con JSON
            if log_available:
                logger.info("Modulo db_utils non disponibile, utilizzo il metodo JSON")
        except Exception as db_error:
            # In caso di errore con SQLite, log e continua con JSON
            if log_available:
                logger.warning(f"Errore nel caricamento dati da SQLite: {db_error}, utilizzo il metodo JSON")
                
        if log_available:
            logger.debug("Inizio caricamento dati da JSON...")
        
        # Inizializza un DataFrame vuoto con le colonne corrette
        empty_df = pd.DataFrame(columns=FULL_COLUMNS)
        
        # Controlla se il file JSON esiste
        if not os.path.exists(DEFAULT_JSON_PATH):
            if log_available:
                logger.warning(f"File JSON {DEFAULT_JSON_PATH} non trovato.")
            
            # Prova a cercare un file CSV esistente come fallback per la migrazione
            if os.path.exists(DEFAULT_CSV_PATH):
                if log_available:
                    logger.info(f"Trovato file CSV. Tentativo di migrazione a JSON...")
                
                # Tenta di caricare il CSV e convertirlo a JSON (viene gestito separatamente nella funzione migrate_csv_to_json)
                return migrate_csv_to_json()
                
            # Cerca altri file JSON come fallback
            if not os.path.exists(DATA_FOLDER):
                if log_available:
                    logger.warning(f"Cartella {DATA_FOLDER} non trovata, creazione...")
                os.makedirs(DATA_FOLDER, exist_ok=True)
                return empty_df
            
            json_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.json')]
            if not json_files:
                if log_available:
                    logger.warning("Nessun file JSON trovato nella cartella 'dati'")
                return empty_df
                
            # Usa il file JSON più recente come fallback
            file_path = os.path.join(DATA_FOLDER, sorted(json_files)[-1])
            if log_available:
                logger.info(f"Usando file JSON alternativo: {file_path}")
        else:
            file_path = DEFAULT_JSON_PATH
            if log_available:
                logger.debug(f"File JSON trovato: {file_path}")
        
        # FASE 1: Verifica che il file sia leggibile
        if print_debug:
            print(f"Verificando file JSON: {file_path}")
        
        if not os.path.isfile(file_path):
            if log_available:
                logger.error(f"Il percorso {file_path} non è un file valido.")
            return empty_df
        
        if os.path.getsize(file_path) == 0:
            if log_available:
                logger.warning(f"Il file JSON {file_path} è vuoto.")
            return empty_df
        
        # FASE 2: Lettura del file JSON
        try:
            if print_debug:
                print("Tentativo di lettura del file JSON...")
            
            # Lettura del JSON con gestione robusta degli errori
            df = pd.read_json(file_path, orient='records')
            
            if print_debug:
                print(f"JSON caricato. Shape: {df.shape}, colonne: {df.columns.tolist()}")
            
            # Verifica delle colonne
            if len(df.columns) < 4:  # Minimo necessario per i dati essenziali
                if log_available:
                    logger.warning(f"Il file JSON ha solo {len(df.columns)} colonne, potrebbero mancare dati essenziali.")
            
            # Assicurati che il dataframe abbia tutte le colonne necessarie
            for col in FULL_COLUMNS:
                if col not in df.columns:
                    df[col] = None
            
            if print_debug:
                print(f"Verifica colonne del dataframe: {df.columns.tolist()}")
            
            # FASE 3: Pulizia dei dati
            if print_debug:
                print("Inizio pulizia dati...")
            
            # Rimuovi righe completamente vuote
            original_rows = len(df)
            df = df.dropna(how='all')
            if print_debug:
                print(f"Righe dopo rimozione vuote: {len(df)} (rimosse {original_rows - len(df)})")
            
            # Filtra le righe che hanno almeno l'orario compilato
            if 'Orario' in df.columns:
                rows_before = len(df)
                df = df[df['Orario'].notna() & (df['Orario'] != '')]
                if print_debug:
                    print(f"Righe dopo filtro orario: {len(df)} (rimosse {rows_before - len(df)})")
            
            # Normalizza i codici insegnamento
            if 'Codice insegnamento' in df.columns:
                if print_debug:
                    print("Normalizzazione codici insegnamento...")
                df['Codice insegnamento'] = df['Codice insegnamento'].apply(lambda x: normalize_code(x) if pd.notna(x) else '')
            
            # FASE 4: Gestione delle date
            if print_debug:
                print("Gestione delle date...")
            
            if 'Data' in df.columns:
                if print_debug:
                    print(f"Tipo della colonna Data prima della conversione: {df['Data'].dtype}")
                    if len(df) > 0:
                        print(f"Esempi valori Data: {df['Data'].head().tolist()}")
                
                # Converti le date in modo più robusto
                # Nota: Con JSON, le date potrebbero già essere state parsate correttamente
                try:
                    # Verifica se le date sono già in formato datetime
                    if not pd.api.types.is_datetime64_any_dtype(df['Data']):
                        # Prima converti a stringa per uniformare il formato
                        df['Data'] = df['Data'].astype(str)
                        # Poi converti a datetime
                        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                    
                    if print_debug:
                        print(f"Tipo della colonna Data dopo la conversione: {df['Data'].dtype}")
                        if len(df) > 0:
                            print(f"Esempi date convertite: {df['Data'].head().tolist()}")
                    
                    # Rimuovi le righe con date non valide
                    rows_before = len(df)
                    df = df.dropna(subset=['Data'])
                    if print_debug:
                        print(f"Righe dopo rimozione date invalide: {len(df)} (rimosse {rows_before - len(df)})")
                    
                    # Estrai e aggiorna le colonne di Giorno, Mese e Anno in modo sicuro
                    if len(df) > 0:
                        try:
                            df['Giorno'] = df['Data'].dt.strftime('%A').str.capitalize()
                            df['Mese'] = df['Data'].dt.strftime('%B').str.capitalize()
                            df['Anno'] = df['Data'].dt.year.astype(str)
                            if print_debug:
                                print("Date elaborate con successo.")
                        except Exception as date_comp_err:
                            if print_debug:
                                print(f"Errore durante l'estrazione dei componenti dalla data: {date_comp_err}")
                            # Fallback: mantieni i valori esistenti o imposta valori predefiniti
                except Exception as date_err:
                    if print_debug:
                        print(f"Errore durante la conversione delle date: {date_err}")
            
            # FASE 5: Gestione valori nulli
            if print_debug:
                print("Pulizia valori nulli e NaN...")
            
            # Sostituisci NaN con stringa vuota nelle colonne di testo
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].fillna('')
            
            # Se ci sono colonne oggetto con valori 'nan' come stringhe, sostituisci con stringa vuota
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].replace('nan', '')
                df[col] = df[col].replace('None', '')
            
            # FASE 6: Finalizzazione
            if print_debug:
                print(f"Dati JSON caricati con successo. Totale record: {len(df)}")
            
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
            
        except Exception as read_err:
            if log_available:
                logger.error(f"Errore durante la lettura del file JSON: {read_err}")
            if print_debug:
                print(f"Errore lettura JSON: {read_err}")
            return empty_df
    
    except Exception as e:
        # Cattura errori generali
        error_msg = f"Errore durante il caricamento dei dati: {e}"
        st.error(error_msg)
        
        import traceback
        error_details = traceback.format_exc()
        
        try:
            from log_utils import logger
            logger.error(error_msg)
            logger.error(f"Dettaglio: {error_details}")
        except ImportError:
            pass
            
        if print_debug:
            print(error_msg)
            print(f"Stack trace: {error_details}")
        
        # Restituisci un DataFrame vuoto per permettere di continuare l'importazione
        return pd.DataFrame(columns=FULL_COLUMNS)

def migrate_csv_to_json() -> pd.DataFrame:
    """
    Migra i dati da un file CSV esistente a un nuovo file JSON.
    Questa funzione è utilizzata per facilitare la transizione dal vecchio formato al nuovo.
    
    Returns:
        pd.DataFrame: DataFrame con i dati migrati o un DataFrame vuoto in caso di errore
    """
    try:
        # Inizializza il logger se disponibile
        try:
            from log_utils import logger
            log_available = True
            logger.info("Avvio migrazione da CSV a JSON...")
        except ImportError:
            log_available = False
        
        # Verifica se il file CSV esiste
        if not os.path.exists(DEFAULT_CSV_PATH):
            st.warning(f"Nessun file CSV trovato in {DEFAULT_CSV_PATH} per la migrazione.")
            return pd.DataFrame(columns=FULL_COLUMNS)
        
        try:
            # Leggi il file CSV - uso parametri compatibili con pandas ≥ 1.3.0
            # 'on_bad_lines' è il sostituto di 'error_bad_lines' e non c'è più 'warn_bad_lines'
            try:
                df = pd.read_csv(DEFAULT_CSV_PATH, delimiter=';', encoding='utf-8', skiprows=3,
                                on_bad_lines='skip')
            except TypeError:
                # Fallback per versioni precedenti di pandas
                df = pd.read_csv(DEFAULT_CSV_PATH, delimiter=';', encoding='utf-8', skiprows=3,
                                error_bad_lines=False, warn_bad_lines=True)
            
            # Verifica se il DataFrame ha dati
            if df.empty:
                st.warning("Il file CSV è vuoto, nessun dato da migrare.")
                return pd.DataFrame(columns=FULL_COLUMNS)
            
            # Standardizza i nomi delle colonne
            if len(df.columns) >= len(FULL_COLUMNS):
                df.columns = FULL_COLUMNS
            else:
                # Se ci sono meno colonne del previsto
                df.columns = FULL_COLUMNS[:len(df.columns)]
                # Aggiungi colonne mancanti
                for col in FULL_COLUMNS[len(df.columns):]:
                    df[col] = None
            
            # Pulizia e normalizzazione dei dati
            # Filtra le righe che hanno almeno l'orario compilato
            df = df[df['Orario'].notna() & (df['Orario'] != '')]
            
            # Converti le date
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            
            # Rimuovi le righe con date non valide
            df = df.dropna(subset=['Data'])
            
            # Aggiorna i campi derivati dalla data
            df['Giorno'] = df['Data'].dt.strftime('%A').str.capitalize()
            df['Mese'] = df['Data'].dt.strftime('%B').str.capitalize()
            df['Anno'] = df['Data'].dt.year.astype(str)
            
            # Salva i dati nel nuovo formato JSON
            os.makedirs(DATA_FOLDER, exist_ok=True)
            df.to_json(DEFAULT_JSON_PATH, orient='records', date_format='iso')
            
            st.success(f"✓ Migrazione completata: {len(df)} record importati da CSV a JSON.")
            
            if log_available:
                logger.info(f"Migrazione CSV → JSON completata con successo: {len(df)} record.")
            
            return df
            
        except Exception as read_err:
            st.error(f"Errore durante la lettura del file CSV per la migrazione: {read_err}")
            if log_available:
                logger.error(f"Errore durante la migrazione CSV → JSON: {read_err}")
            return pd.DataFrame(columns=FULL_COLUMNS)
            
    except Exception as e:
        st.error(f"Errore durante la migrazione dei dati: {e}")
        import traceback
        if log_available:
            logger.error(f"Errore durante la migrazione CSV → JSON: {e}")
            logger.error(f"Dettaglio: {traceback.format_exc()}")
        
        return pd.DataFrame(columns=FULL_COLUMNS)

def save_data(df: pd.DataFrame, replace_file: bool = False) -> str:
    """
    Salva un dataframe sia nel database SQLite che nel file JSON standard del calendario.
    
    Args:
        df: DataFrame da salvare
        replace_file: Se True, sovrascrive completamente il file esistente invece di 
                      tentare di unire con dati esistenti
        
    Returns:
        str: Percorso del file salvato
    """
    os.makedirs(DATA_FOLDER, exist_ok=True)
    
    # Importa il logger se non è già disponibile
    try:
        from log_utils import logger
        logger.info(f"Avvio salvataggio dati: {len(df)} record, replace_file={replace_file}")
    except ImportError:
        pass  # Se il logger non è disponibile, continua senza errori
    
    # Importa il container di debug fittizio che usa solo il logger
    from fixed_logger_debug_container import LoggerDebugContainer
                
    # Prima, tenta di salvare i dati nel database SQLite
    sqlite_success = False
    try:
        from db_utils import save_record
        
        # Log del tentativo
        try:
            from log_utils import logger
            logger.info("Tentativo di salvare i dati in SQLite...")
        except ImportError:
            pass
            
        # Salva ogni record nel database
        success_count = 0
        for _, row in df.iterrows():
            if save_record(row.to_dict()):
                success_count += 1
                
        sqlite_success = success_count > 0
        
        # Log del risultato
        try:
            from log_utils import logger
            if sqlite_success:
                logger.info(f"Salvati con successo {success_count}/{len(df)} record nel database SQLite")
            else:
                logger.warning(f"Nessun record salvato con successo nel database SQLite")
        except ImportError:
            pass
            
    except ImportError:
        # Se il modulo db_utils non è disponibile, continua solo con il JSON
        try:
            from log_utils import logger
            logger.warning("Modulo db_utils non disponibile, utilizzo solo JSON")
        except ImportError:
            pass
    except Exception as e:
        # In caso di errore nel salvataggio SQLite, log e continua con JSON
        try:
            from log_utils import logger
            logger.error(f"Errore nel salvataggio dei dati in SQLite: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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
    
    # Usa un container fittizio per evitare problemi con Streamlit
    debug_container = LoggerDebugContainer()
    
    try:
        debug_container.text("Fase 1: Preparazione del DataFrame...")
        try:
            logger.debug(f"DF info - shape: {df.shape}, columns: {list(df.columns)}")
            # Log dei primi record per debug
            logger.debug(f"Prime 3 righe del dataframe:\n{df.head(3)}")
            
            # Log del risultato del salvataggio SQLite
            if sqlite_success:
                logger.debug("Il salvataggio in SQLite è stato completato con successo, procedendo con il salvataggio JSON per retrocompatibilità")
            else:
                logger.debug("Il salvataggio in SQLite non è riuscito o non è disponibile, utilizzo il metodo JSON")
        except:
            pass
        
        # Gestione robusta dei tipi di dati - crea una copia per evitare modifiche indesiderate
        df = df.copy()
        
        # Assicurati che il dataframe abbia tutte le colonne necessarie
        for col in FULL_COLUMNS:
            if col not in df.columns:
                df[col] = None
        
        # Gestione robusta delle date
        debug_container.text("Fase 2: Normalizzazione delle date...")
        
        # Converti tutte le date in formato datetime in modo robusto
        try:
            # Salva una copia del formato originale delle date per debug
            original_data_format = str(df['Data'].dtype)
            debug_container.text(f"Formato originale Data: {original_data_format}")
            
            # Se la colonna Data contiene valori datetime, non è necessario convertirla
            if pd.api.types.is_datetime64_any_dtype(df['Data']):
                debug_container.text("La colonna Data è già in formato datetime.")
            else:
                # Altrimenti, tenta la conversione
                debug_container.text("Conversione della colonna Data in formato datetime...")
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                debug_container.text(f"Conversione completata. Nuovo formato: {df['Data'].dtype}")
            
            # Rimuovi le righe con date non valide
            valid_rows_before = len(df)
            df = df.dropna(subset=['Data'])
            valid_rows_after = len(df)
            debug_container.text(f"Date non valide rimosse: {valid_rows_before - valid_rows_after}")
            
        except Exception as date_err:
            debug_container.error(f"Errore durante la normalizzazione delle date: {date_err}")
            import traceback
            debug_container.error(f"Dettaglio: {traceback.format_exc()}")
            raise
        
        # Leggi il file JSON esistente se presente e se non stiamo sostituendo completamente il file
        if os.path.exists(DEFAULT_JSON_PATH) and not replace_file:
            debug_container.text("Fase 3: Caricamento del file JSON esistente...")
            try:
                existing_df = pd.read_json(DEFAULT_JSON_PATH, orient='records')
                debug_container.success(f"File JSON caricato con successo")
                
                # Assicurati che il dataframe esistente abbia tutte le colonne richieste
                for col in FULL_COLUMNS:
                    if col not in existing_df.columns:
                        existing_df[col] = None
                
                debug_container.text("Fase 4: Standardizzazione delle date...")
                
                # Converti le date esistenti in formato datetime se necessario
                try:
                    if not pd.api.types.is_datetime64_any_dtype(existing_df['Data']):
                        existing_df['Data'] = pd.to_datetime(existing_df['Data'], errors='coerce')
                    debug_container.text(f"Conversione date esistenti completata: {existing_df['Data'].dtype}")
                except Exception as existing_date_err:
                    debug_container.warning(f"Avviso durante la conversione delle date esistenti: {existing_date_err}")
                
                # Log di debug
                debug_container.info(f"Record esistenti: {len(existing_df)}, Nuovi record: {len(df)}")
                
                # Combina i dati
                debug_container.text("Fase 5: Combinazione dei dati...")
                df = pd.concat([existing_df, df], ignore_index=True)
                debug_container.text(f"Combinazione completata: {len(df)} record totali")
            except Exception as json_err:
                debug_container.warning(f"Errore durante il caricamento del file JSON esistente: {json_err}")
                debug_container.info("Creazione di un nuovo file JSON...")
                # Se c'è un errore nella lettura del JSON, procedi con il dataframe corrente

        # Pulizia dei dati
        debug_container.text("Fase 6: Pulizia dei dati...")
        df = df.dropna(how='all')  # Rimuovi righe vuote
        
        # Rimuovi duplicati basati su colonne chiave
        pre_dedup = len(df)
        df = df.drop_duplicates(
            subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'], 
            keep='last'
        )
        post_dedup = len(df)
        debug_container.text(f"Duplicati rimossi: {pre_dedup - post_dedup}")
            
        # Normalizza i codici insegnamento
        if 'Codice insegnamento' in df.columns:
            df['Codice insegnamento'] = df['Codice insegnamento'].apply(normalize_code)

        # Ordina il dataframe per data e orario in modo robusto
        debug_container.text("Fase 7: Ordinamento dei dati...")
        try:
            # Non c'è bisogno di creare una colonna temporanea se Data è già in formato datetime
            df = df.sort_values(['Data', 'Orario'])
        except Exception as sort_err:
            debug_container.warning(f"Avviso durante l'ordinamento: {sort_err}. Usando metodo alternativo...")
            # Metodo di fallback
            try:
                # In caso di problemi, crea una colonna temporanea con conversione
                df['Data_temp'] = pd.to_datetime(df['Data'], errors='coerce')
                df = df.sort_values(['Data_temp', 'Orario'])
                df = df.drop('Data_temp', axis=1)
            except Exception as fallback_err:
                debug_container.error(f"Anche il metodo alternativo ha fallito: {fallback_err}")
                # Se anche questo fallisce, procedi senza ordinamento

        # Se stiamo sostituendo il file o se non esiste, lo creiamo da zero
        debug_container.text("Fase 8: Preparazione del file CSV...")
        file_exists = os.path.exists(DEFAULT_CSV_PATH)
        create_new_file = replace_file or not file_exists
        
        # Salviamo l'informazione se stiamo creando un nuovo file per dopo
        create_new_file_with_headers = create_new_file
        
        if create_new_file:
            with open(DEFAULT_CSV_PATH, 'w', encoding='utf-8') as f:
                for header in CSV_HEADERS:
                    f.write(header)
        
        # Assicurati che tutte le date siano in formato datetime prima di procedere
        debug_container.text("Fase 9: Normalizzazione finale delle date...")
        
        # Verifica se ci sono righe con dati incompleti e registrale per il log
        missing_data_rows = []
        for idx, row in df.iterrows():
            missing_fields = []
            for critical_col in ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento']:
                if pd.isna(row.get(critical_col)) or row.get(critical_col) == '':
                    missing_fields.append(critical_col)
            
            if missing_fields:
                row_info = {
                    'Indice': idx, 
                    'Campi mancanti': missing_fields,
                    'Docente': row.get('Docente', 'N/A'),
                    'Denominazione': row.get('Denominazione Insegnamento', 'N/A')
                }
                missing_data_rows.append(row_info)
        
        # Log delle righe con dati incompleti
        if missing_data_rows:
            debug_container.warning(f"⚠️ Trovate {len(missing_data_rows)} righe con dati incompleti")
            with debug_container.expander("Mostra righe con dati incompleti"):
                for row_info in missing_data_rows:
                    debug_container.text(f"Riga {row_info['Indice']}: {row_info['Docente']} - {row_info['Denominazione']}")
                    debug_container.text(f"   Campi mancanti: {', '.join(row_info['Campi mancanti'])}")
        
        # Rimuovi le righe con dati incompleti essenziali
        total_rows_before = len(df)
        df_cleaned = df.dropna(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
        total_rows_after = len(df_cleaned)
        
        if total_rows_before > total_rows_after:
            debug_container.warning(f"⚠️ Rimosse {total_rows_before - total_rows_after} righe con dati incompleti essenziali")
            # Sostituisci il dataframe originale con quello pulito
            df = df_cleaned
        
        try:
            # Converte la colonna Data in formato datetime
            debug_container.text("Fase 9.1: Conversione date in formato datetime...")
            
            # Backup della colonna originale per debug
            df['Data_original'] = df['Data'].copy()
            
            # Converti in datetime in modo più affidabile
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            
            # Verifica se ci sono date non valide
            invalid_dates = df['Data'].isna().sum()
            if invalid_dates > 0:
                debug_container.warning(f"⚠️ Trovate {invalid_dates} date non valide che verranno rimosse")
                # Rimuovi righe con date non valide
                df = df.dropna(subset=['Data'])
                debug_container.warning(f"Rimossi {invalid_dates} record con date non valide")
                
            # Ora che abbiamo le date in formato datetime, aggiorna Giorno, Mese e Anno
            debug_container.text("Fase 9.2: Aggiornamento campi data derivati...")
            
            # Genera Giorno, Mese e Anno con gestione sicura dei valori nulli
            # Utilizziamo apply() per maggiore sicurezza con valori NaT
            df['Giorno'] = df['Data'].apply(lambda x: x.strftime('%A').capitalize() if pd.notnull(x) else "")
            df['Mese'] = df['Data'].apply(lambda x: x.strftime('%B').capitalize() if pd.notnull(x) else "")
            df['Anno'] = df['Data'].apply(lambda x: str(x.year) if pd.notnull(x) else "")
            
            debug_container.success(f"✅ Aggiornati {len(df)} record con Giorno, Mese e Anno")
            
            # Controllo di sicurezza per verificare che non ci siano NaN nei campi critici
            for col in ['Giorno', 'Mese', 'Anno', 'Orario', 'Docente', 'Denominazione Insegnamento']:
                if col in df.columns and df[col].isna().any():
                    na_count = df[col].isna().sum()
                    debug_container.warning(f"Trovati {na_count} valori NaN nella colonna {col}, sostituiti con stringhe vuote")
                    df[col] = df[col].fillna("")
            
            # Se ci sono colonne oggetto con valori 'nan' come stringhe, sostituisci con stringa vuota
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].replace('nan', '')
                df[col] = df[col].replace('None', '')
                # Converti anche i NaN effettivi in stringa vuota
                df[col] = df[col].fillna('')
            
        except Exception as component_err:
            debug_container.error(f"❌ Errore durante l'aggiornamento dei componenti data: {component_err}")
            import traceback
            debug_container.error(f"Dettaglio: {traceback.format_exc()}")
            raise  # Rilancia l'eccezione per essere gestita dal blocco try principale
        
        # Per evitare errori nella scrittura del CSV, convertiamo le date in formato standard YYYY-MM-DD
        debug_container.text("Fase 10: Preparazione formato date per CSV...")
        try:
            # Crea una copia delle date in formato stringa ISO per il salvataggio CSV
            df['Data_ISO'] = df['Data'].dt.strftime('%Y-%m-%d')
            
            # Verifica che tutte le conversioni abbiano funzionato
            if df['Data_ISO'].isna().any():
                na_count = df['Data_ISO'].isna().sum()
                debug_container.warning(f"❗ Ci sono ancora {na_count} date non convertite correttamente")
                # Sostituisci i NaN con stringa vuota
                df['Data_ISO'] = df['Data_ISO'].fillna('')
            
            # Sostituisci temporaneamente per la scrittura del CSV
            df_final = df.copy()
            df_final['Data'] = df['Data_ISO']
            
            # Rimuovi colonne temporanee
            df_final = df_final.drop(['Data_ISO', 'Data_original'], axis=1, errors='ignore')
            
            # PUNTO CRITICO: Gestione dei valori NaN in tutte le colonne
            debug_container.text("Fase 10.1: Sostituzione di tutti i valori NaN con stringhe vuote...")
            
            # Forza conversione delle colonne problematiche in stringhe
            problematic_columns = ['Aula', 'Link Teams', 'Note']
            for col in problematic_columns:
                if col in df_final.columns:
                    debug_container.text(f"Conversione forzata della colonna '{col}' da {df_final[col].dtype} a stringa")
                    # Prima sostituisci eventuali NaN con stringa vuota
                    df_final[col] = df_final[col].fillna('')
                    # Poi converti in stringa
                    df_final[col] = df_final[col].astype(str)
                    # Rimuovi valori 'nan', 'None', etc. che potrebbero essere stati introdotti (più completo)
                    df_final[col] = df_final[col].replace(['nan', 'None', 'NaN', 'none', '<NA>', 'null'], '', regex=False)
                    # Rimuovi '.0' dai numeri interi
                    df_final[col] = df_final[col].apply(lambda x: x.replace('.0', '') if isinstance(x, str) and x.endswith('.0') else x)
                    # Assicurati che il tipo sia object (string)
                    df_final[col] = df_final[col].astype('object')
                    debug_container.text(f"  - Dopo conversione: {df_final[col].dtype}")
            
            # Converti tutti i valori NaN in stringhe vuote in tutte le altre colonne
            for col in df_final.columns:
                if col not in problematic_columns:  # Salta le colonne già gestite
                    # Gestisci i tipi float con NaN
                    if df_final[col].dtype == 'float64':
                        # Converti in stringa per evitare il valore 'nan' nel CSV
                        df_final[col] = df_final[col].fillna('').astype(str)
                        # Rimuovi il '.0' dai numeri interi
                        df_final[col] = df_final[col].apply(lambda x: x.replace('.0', '') if x.endswith('.0') else x)
                    else:
                        # Per tutti gli altri tipi, basta fillna
                        df_final[col] = df_final[col].fillna('')
                    
            # Rimuovi le stringhe letterali 'nan' o 'None' che potrebbero esistere
            for col in df_final.select_dtypes(include=['object']).columns:
                df_final[col] = df_final[col].replace('nan', '')
                df_final[col] = df_final[col].replace('None', '')
                df_final[col] = df_final[col].replace('NaN', '')
                
            debug_container.success("✅ Valori NaN gestiti correttamente")
            
            debug_container.success("✅ Date convertite con successo in formato ISO")
            
            # Usa questo df_final per il salvataggio
            df = df_final
            
        except Exception as csv_err:
            debug_container.error(f"❌ Errore durante la preparazione del formato CSV: {csv_err}")
            import traceback
            debug_container.error(f"Dettaglio errore: {traceback.format_exc()}")
            raise  # Rilancia l'eccezione per essere gestita dal blocco try principale
        
        # Riordina le colonne
        df = df[FULL_COLUMNS]
            
        # Salva il dataframe in formato JSON
        debug_container.text("Fase 11: Scrittura del file JSON...")
        
        # Il formato JSON gestisce automaticamente i tipi di dati, incluse le date
        # Qui non abbiamo bisogno di preoccuparci delle intestazioni come facevamo con CSV
        df.to_json(DEFAULT_JSON_PATH, orient='records', date_format='iso')
        
        # Per compatibilità, manteniamo anche il file CSV
        debug_container.text("Fase 12: Aggiornamento file CSV per compatibilità (opzionale)...")
        try:
            # Salva anche il vecchio formato CSV per compatibilità
            with open(DEFAULT_CSV_PATH, 'w', encoding='utf-8') as f:
                for header in CSV_HEADERS:
                    f.write(header)
            
            df.to_csv(DEFAULT_CSV_PATH, mode='a', index=False, header=False, sep=';', encoding='utf-8')
            debug_container.text("✅ File CSV di backup creato con successo")
        except Exception as csv_err:
            debug_container.warning(f"Non è stato possibile creare il file CSV di backup: {csv_err}")
        
        st.success(f"Dati salvati correttamente nel file {DEFAULT_JSON_FILE}")
        debug_container.success("✅ Salvataggio completato con successo")
        
    except Exception as e:
        st.error(f"Errore durante il salvataggio dei dati: {e}")
        debug_container.error(f"❌ Errore durante il salvataggio: {e}")
        import traceback
        debug_container.error(f"Dettaglio: {traceback.format_exc()}")
        
    return DEFAULT_CSV_PATH

def delete_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """
    Elimina un record dal DataFrame, dal database SQLite e aggiorna il file JSON.
    
    Args:
        df: DataFrame contenente i dati
        index: Indice del record da eliminare
        
    Returns:
        pd.DataFrame: DataFrame aggiornato senza il record eliminato
    """
    if index < 0 or index >= len(df):
        st.error(f"Errore: indice record non valido ({index}). Deve essere tra 0 e {len(df)-1}")
        return df
        
    # Prima tenta di eliminare il record dal database SQLite
    sqlite_success = False
    try:
        from db_utils import delete_record as delete_sql_record
        
        # Ottieni i dati del record da eliminare
        record_data = df.iloc[index].to_dict()
        
        # Tenta l'eliminazione dal database
        if delete_sql_record(record_data):
            sqlite_success = True
            try:
                from log_utils import logger
                logger.info(f"Record eliminato con successo dal database SQLite")
            except ImportError:
                pass
        else:
            try:
                from log_utils import logger
                logger.warning(f"Impossibile eliminare il record dal database SQLite")
            except ImportError:
                pass
    except ImportError:
        # Se il modulo db_utils non è disponibile, continua solo con il JSON
        try:
            from log_utils import logger
            logger.warning("Modulo db_utils non disponibile, eliminazione solo dal JSON")
        except ImportError:
            pass
    except Exception as e:
        # In caso di errore nell'eliminazione da SQLite, log e continua con JSON
        try:
            from log_utils import logger
            logger.error(f"Errore nell'eliminazione del record da SQLite: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        except ImportError:
            pass
    
    # Elimina il record dal DataFrame
    df = df.drop(df.index[index]).reset_index(drop=True)
    
    # Salva il DataFrame aggiornato con sovrascrittura completa del file
    # (la funzione save_data si occuperà anche del salvataggio in SQLite)
    save_data(df, replace_file=True)
    
    # Conferma
    st.success("Record eliminato con successo!")
    
    return df

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

        # Gestisci Codice insegnamento (rimuovi .0 se presente) con gestione più robusta
        if 'Codice insegnamento' in df.columns:
            # Converti in stringa e gestisci valori nulli
            df['Codice insegnamento'] = df['Codice insegnamento'].fillna('').astype(str)
            # Rimuovi .0 alla fine dei codici numerici
            df['Codice insegnamento'] = df['Codice insegnamento'].apply(
                lambda x: x.split('.')[0] if '.' in x and x.split('.')[1] == '0' else x
            )
            # Rimuovi spazi extra all'inizio e alla fine
            df['Codice insegnamento'] = df['Codice insegnamento'].str.strip()

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
            'Codice insegnamento': '22911105',
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
            'Codice insegnamento': '22910050',
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
            'Codice insegnamento': '22911105',
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
            'Codice insegnamento': '22910050',
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
        'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
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
            'Codice insegnamento': '22911105',
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
            'Codice insegnamento': '22910050',
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

def edit_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """
    Modifica un record esistente nel DataFrame.
    
    Args:
        df: DataFrame contenente i dati
        index: Indice del record da modificare
        
    Returns:
        pd.DataFrame: DataFrame aggiornato dopo la modifica
    """
    if index < 0 or index >= len(df):
        st.error(f"Errore: indice record non valido ({index}). Deve essere tra 0 e {len(df)-1}")
        return df
    
    # Ottieni i valori correnti del record
    record = df.iloc[index]
    
    st.subheader("Modifica Record")
    
    # Preparazione dei campi da modificare
    col1, col2 = st.columns(2)
    
    # Converti la data in formato datetime comprensibile
    date_obj = record['Data'] if pd.notna(record['Data']) else None
    date_str = date_obj.strftime('%Y-%m-%d') if date_obj else ''
    
    with col1:
        new_date = st.date_input("Data", 
                                value=pd.to_datetime(date_str) if date_str else None,
                                format="YYYY-MM-DD",
                                key=f"date_input_{index}")
        new_orario = st.text_input("Orario (es. 14:30-16:45)", value=record['Orario'], key=f"orario_{index}")
        new_dipartimento = st.text_input("Dipartimento", value=record['Dipartimento'], key=f"dipartimento_{index}")
        new_classe = st.text_input("Classe di concorso", value=record['Classe di concorso'], key=f"classe_{index}")
        new_insegnamento_comune = st.text_input("Insegnamento comune", value=record['Insegnamento comune'], key=f"insegnamento_comune_{index}")
        new_pef60 = st.text_input("PeF60 all.1", value=record['PeF60 all.1'], key=f"pef60_{index}")
        new_pef30_all2 = st.text_input("PeF30 all.2", value=record['PeF30 all.2'], key=f"pef30_all2_{index}")
        new_pef36 = st.text_input("PeF36 all.5", value=record['PeF36 all.5'], key=f"pef36_{index}")
    
    with col2:
        new_pef30_art13 = st.text_input("PeF30 art.13", value=record['PeF30 art.13'], key=f"pef30_art13_{index}")
        new_codice = st.text_input("Codice insegnamento", value=record['Codice insegnamento'], key=f"codice_{index}")
        new_denominazione = st.text_input("Denominazione Insegnamento", value=record['Denominazione Insegnamento'], key=f"denominazione_{index}")
        new_docente = st.text_input("Docente", value=record['Docente'], key=f"docente_{index}")
        new_aula = st.text_input("Aula", value=record['Aula'], key=f"aula_{index}")
        new_link = st.text_input("Link Teams", value=record['Link Teams'], key=f"link_{index}")
        new_cfu = st.text_input("CFU", value=str(record['CFU']) if pd.notna(record['CFU']) else "", key=f"cfu_{index}")
        new_note = st.text_area("Note", value=record['Note'], key=f"note_{index}")
    
    # Pulsante per salvare le modifiche
    if st.button("Salva modifiche"):
        # Crea un dizionario con i nuovi valori
        new_values = {
            'Data': pd.to_datetime(new_date),
            'Orario': new_orario,
            'Dipartimento': new_dipartimento,
            'Classe di concorso': new_classe,
            'Insegnamento comune': new_insegnamento_comune,
            'PeF60 all.1': new_pef60,
            'PeF30 all.2': new_pef30_all2,
            'PeF36 all.5': new_pef36,
            'PeF30 art.13': new_pef30_art13,
            'Codice insegnamento': normalize_code(new_codice),
            'Denominazione Insegnamento': new_denominazione,
            'Docente': new_docente,
            'Aula': new_aula,
            'Link Teams': new_link,
            'CFU': float(new_cfu) if new_cfu.strip() else None,
            'Note': new_note
        }
        
        # Estrai i componenti dalla data
        giorno, mese, anno = None, None, None
        if pd.notna(new_values['Data']):
            giorno = new_values['Data'].strftime("%A").capitalize()
            mese = new_values['Data'].strftime("%B").capitalize()
            anno = str(new_values['Data'].year)
        
        # Aggiungi i componenti della data
        new_values['Giorno'] = giorno
        new_values['Mese'] = mese
        new_values['Anno'] = anno
        
        # Aggiorna il record nel dataframe
        for col, val in new_values.items():
            df.at[index, col] = val
        
        # Tentativo diretto di aggiornamento nel database SQLite
        sqlite_success = False
        try:
            from db_utils import update_record
            
            # Prepara i dati per l'aggiornamento
            updated_record = df.iloc[index].to_dict()
            
            # Tenta l'aggiornamento diretto nel database SQLite
            if update_record(updated_record):
                sqlite_success = True
                try:
                    from log_utils import logger
                    logger.info("Record aggiornato con successo nel database SQLite")
                except ImportError:
                    pass
        except ImportError:
            # Il modulo db_utils non è disponibile
            try:
                from log_utils import logger
                logger.warning("Modulo db_utils non disponibile, utilizzo solo JSON")
            except ImportError:
                pass
        except Exception as e:
            # Errore nell'aggiornamento SQLite
            try:
                from log_utils import logger
                logger.error(f"Errore nell'aggiornamento del record in SQLite: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
            except ImportError:
                pass
                
        # Indipendentemente dal risultato SQLite, aggiorna anche il file JSON
        # Nota: save_data() si occuperà comunque di tentare un salvataggio anche in SQLite
        save_data(df, replace_file=True)
        
        success_msg = "Record aggiornato con successo!"
        if sqlite_success:
            success_msg += " (Salvato in SQLite e JSON)"
            
        st.success(success_msg)
    
    return df

def create_new_record(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggiunge un nuovo record al DataFrame.
    
    Args:
        df: DataFrame contenente i dati
        
    Returns:
        pd.DataFrame: DataFrame aggiornato con il nuovo record
    """
    st.subheader("Aggiungi Nuovo Record")
    
    # Preparazione dei campi da compilare
    col1, col2 = st.columns(2)
    
    with col1:
        new_date = st.date_input("Data", format="YYYY-MM-DD")
        new_orario = st.text_input("Orario (es. 14:30-16:45)")
        new_dipartimento = st.text_input("Dipartimento")
        new_classe = st.text_input("Classe di concorso")
        new_insegnamento_comune = st.text_input("Insegnamento comune")
        new_pef60 = st.text_input("PeF60 all.1")
        new_pef30_all2 = st.text_input("PeF30 all.2")
        new_pef36 = st.text_input("PeF36 all.5")
    
    with col2:
        new_pef30_art13 = st.text_input("PeF30 art.13")
        new_codice = st.text_input("Codice insegnamento")
        new_denominazione = st.text_input("Denominazione Insegnamento")
        new_docente = st.text_input("Docente")
        new_aula = st.text_input("Aula")
        new_link = st.text_input("Link Teams")
        new_cfu = st.text_input("CFU")
        new_note = st.text_area("Note")
    
    # Pulsante per salvare il nuovo record
    if st.button("Salva nuovo record"):
        # Verifica che i campi obbligatori siano compilati
        if not new_date or not new_orario or not new_docente or not new_denominazione:
            st.error("Errore: i campi Data, Orario, Docente e Denominazione Insegnamento sono obbligatori.")
            return df
        
        # Estrai i componenti dalla data
        try:
            giorno = new_date.strftime("%A").capitalize()
            mese = new_date.strftime("%B").capitalize()
            anno = str(new_date.year)
        except Exception as e:
            st.error(f"Errore nella formattazione della data: {e}")
            return df
        
        # Crea un dizionario con i valori del nuovo record
        new_record = {
            'Data': pd.to_datetime(new_date),
            'Orario': new_orario,
            'Dipartimento': new_dipartimento,
            'Classe di concorso': new_classe,
            'Insegnamento comune': new_insegnamento_comune,
            'PeF60 all.1': new_pef60,
            'PeF30 all.2': new_pef30_all2,
            'PeF36 all.5': new_pef36,
            'PeF30 art.13': new_pef30_art13,
            'Codice insegnamento': normalize_code(new_codice),
            'Denominazione Insegnamento': new_denominazione,
            'Docente': new_docente,
            'Aula': new_aula,
            'Link Teams': new_link,
            'CFU': float(new_cfu) if new_cfu.strip() else None,
            'Note': new_note,
            'Giorno': giorno,
            'Mese': mese,
            'Anno': anno
        }
        
        # Tentativo diretto di inserimento nel database SQLite
        sqlite_success = False
        try:
            from db_utils import save_record
            
            # Tenta l'inserimento diretto nel database SQLite
            if save_record(new_record):
                sqlite_success = True
                try:
                    from log_utils import logger
                    logger.info("Nuovo record inserito con successo nel database SQLite")
                except ImportError:
                    pass
        except ImportError:
            # Il modulo db_utils non è disponibile
            try:
                from log_utils import logger
                logger.warning("Modulo db_utils non disponibile, utilizzo solo JSON")
            except ImportError:
                pass
        except Exception as e:
            # Errore nell'inserimento SQLite
            try:
                from log_utils import logger
                logger.error(f"Errore nell'inserimento del nuovo record in SQLite: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
            except ImportError:
                pass
        
        # Aggiungi il nuovo record al DataFrame in memoria
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        
        # Salva il DataFrame aggiornato nel file JSON per retrocompatibilità
        save_data(df)
        
        success_msg = "Nuovo record aggiunto con successo!"
        if sqlite_success:
            success_msg += " (Salvato in SQLite e JSON)"
            
        st.success(success_msg)
    
    return df
