"""
Utility per le operazioni di database del calendario lezioni.
Questo modulo centralizza le operazioni di lettura, scrittura ed eliminazione dei record dal database.
"""

import os
import pandas as pd
import streamlit as st
import traceback
import time
from typing import Union, Tuple, Dict, Any, List, Optional

# Importa utility per date e dati
from date_utils import setup_locale, format_date, parse_date
from data_utils import normalize_code

# Costanti per i file
DATA_FOLDER = 'dati'
DEFAULT_JSON_FILE = 'dati.json'
DEFAULT_JSON_PATH = os.path.join(DATA_FOLDER, DEFAULT_JSON_FILE)

# Importa le costanti necessarie da data_utils
from data_utils import BASE_COLUMNS, FULL_COLUMNS

def load_data(file_path=None, debug_container=None, print_debug=False) -> pd.DataFrame:
    """
    Carica i dati dal file JSON predefinito o da un file specificato.
    
    Args:
        file_path: Percorso personalizzato del file da caricare (opzionale)
        debug_container: Container Streamlit per i messaggi di debug (opzionale)
        print_debug: Se True, stampa messaggi di debug sulla console
    
    Returns:
        pd.DataFrame: DataFrame con i dati del file, o un DataFrame vuoto in caso di errore
    """
    try:
        # Configurazione iniziale
        setup_locale()
        
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
        
        # Usa il file path personalizzato se fornito, altrimenti usa quello predefinito
        if file_path is None:
            file_path = DEFAULT_JSON_PATH
        
        # Controlla se il file JSON esiste
        if not os.path.exists(file_path):
            if log_available:
                logger.warning(f"File JSON {file_path} non trovato.")
            
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
            if log_available:
                logger.debug(f"File JSON trovato: {file_path}")
        
        # Verifica che il file sia leggibile
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
            
        # Lettura del file JSON
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
            
            # Pulizia dei dati
            # Rimuovi righe completamente vuote
            original_rows = len(df)
            df = df.dropna(how='all')
            
            # Filtra le righe che hanno almeno l'orario compilato
            if 'Orario' in df.columns:
                rows_before = len(df)
                df = df[df['Orario'].notna() & (df['Orario'] != '')]
            
            # Normalizza i codici insegnamento
            if 'Codice insegnamento' in df.columns:
                df['Codice insegnamento'] = df['Codice insegnamento'].apply(lambda x: normalize_code(x) if pd.notna(x) else '')
            
            # Gestione delle date
            if 'Data' in df.columns:
                # Converti le date in modo più robusto
                # Con JSON, le date potrebbero già essere state parsate correttamente
                try:
                    # Verifica se le date sono già in formato datetime
                    if not pd.api.types.is_datetime64_any_dtype(df['Data']):
                        # Prima converti a stringa per uniformare il formato
                        df['Data'] = df['Data'].astype(str)
                        # Poi converti a datetime
                        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                    
                    # Rimuovi le righe con date non valide
                    rows_before = len(df)
                    df = df.dropna(subset=['Data'])
                    
                    # Estrai e aggiorna le colonne di Giorno, Mese e Anno in modo sicuro
                    if len(df) > 0:
                        try:
                            df['Giorno'] = df['Data'].dt.strftime('%A').str.capitalize()
                            df['Mese'] = df['Data'].dt.strftime('%B').str.capitalize()
                            df['Anno'] = df['Data'].dt.year.astype(str)
                        except Exception:
                            pass  # Mantieni i valori esistenti in caso di errore
                except Exception:
                    pass  # Gestito silenziosamente
            
            # Gestione valori nulli
            # Sostituisci NaN con stringa vuota nelle colonne di testo
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].fillna('')
            
            # Se ci sono colonne oggetto con valori 'nan' come stringhe, sostituisci con stringa vuota
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].replace('nan', '')
                df[col] = df[col].replace('None', '')
            
            return df
            
        except Exception as read_err:
            if log_available:
                logger.error(f"Errore durante la lettura del file JSON: {read_err}")
                logger.error(traceback.format_exc())
            
            if debug_container is not None:
                debug_container.error(f"Errore durante la lettura del file JSON: {read_err}")
                debug_container.error(traceback.format_exc())
            elif print_debug:
                print(f"Errore durante la lettura del file JSON: {read_err}")
                print(traceback.format_exc())
            
            return empty_df
    
    except Exception as e:
        # Cattura errori generali
        error_msg = f"Errore durante il caricamento dei dati: {e}"
        st.error(error_msg)
        error_details = traceback.format_exc()
        
        try:
            from log_utils import logger
            logger.error(error_msg)
            logger.error(error_details)
        except ImportError:
            pass
            
        if print_debug:
            print(error_msg)
            print(error_details)
        
        # Restituisci un DataFrame vuoto per permettere di continuare l'importazione
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
            logger.error(traceback.format_exc())
        except ImportError:
            pass
    
    # Usa un container fittizio per evitare problemi con Streamlit
    debug_container = LoggerDebugContainer()
    
    try:
        debug_container.text("Fase 1: Preparazione del DataFrame...")
        try:
            from log_utils import logger
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

        # Non è più necessario gestire i file CSV dato che utilizziamo SQLite
        
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
            debug_container.error(f"Dettaglio: {traceback.format_exc()}")
            raise  # Rilancia l'eccezione per essere gestita dal blocco try principale
        
        # Convertiamo le date in formato standard YYYY-MM-DD per il salvataggio
        debug_container.text("Fase 10: Preparazione formato date...")
        try:
            # Crea una copia delle date in formato stringa ISO
            df['Data_ISO'] = df['Data'].dt.strftime('%Y-%m-%d')
            
            # Verifica che tutte le conversioni abbiano funzionato
            if df['Data_ISO'].isna().any():
                na_count = df['Data_ISO'].isna().sum()
                debug_container.warning(f"❗ Ci sono ancora {na_count} date non convertite correttamente")
                # Sostituisci i NaN con stringa vuota
                df['Data_ISO'] = df['Data_ISO'].fillna('')
            
            # Prepara la versione finale del dataframe per il salvataggio
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
                        # Converti in stringa per evitare valori 'nan'
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
            
        except Exception as format_err:
            debug_container.error(f"❌ Errore durante la preparazione del formato dei dati: {format_err}")
            debug_container.error(f"Dettaglio errore: {traceback.format_exc()}")
            raise  # Rilancia l'eccezione per essere gestita dal blocco try principale
        
        # Riordina le colonne
        df = df[FULL_COLUMNS]
            
        # Salva il dataframe in formato JSON
        debug_container.text("Fase 11: Scrittura del file JSON...")
        
        # Il formato JSON gestisce automaticamente i tipi di dati, incluse le date
        df.to_json(DEFAULT_JSON_PATH, orient='records', date_format='iso')
        
        st.success(f"Dati salvati correttamente nel database e nel file {DEFAULT_JSON_FILE} di backup")
        debug_container.success("✅ Salvataggio completato con successo")
        
    except Exception as e:
        st.error(f"Errore durante il salvataggio dei dati: {e}")
        debug_container.error(f"❌ Errore durante il salvataggio: {e}")
        debug_container.error(f"Dettaglio: {traceback.format_exc()}")
        
    return DEFAULT_JSON_PATH

# La funzione delete_record è stata spostata in db_delete_operations.py
from db_delete_operations import delete_record

# Qui era presente il codice di delete_record che è stato spostato nel file db_delete_operations.py
