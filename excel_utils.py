"""
Utility per la gestione dei file Excel del calendario lezioni.
Questo modulo centralizza le operazioni di importazione, esportazione e creazione di template Excel.
"""
import os
import pandas as pd
import streamlit as st
import traceback
import time
import locale
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# Importa le costanti necessarie dal modulo file_utils
from file_utils import (
    BASE_COLUMNS, FULL_COLUMNS, DATA_FOLDER,
    setup_locale, normalize_code
)

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
            
            # Verifica se il DataFrame è vuoto dopo la lettura
            if preview_df.empty:
                progress_bar.empty()
                status_text.empty()
                st.error("⚠️ Importazione fallita: Il file Excel caricato è vuoto.")
                return None
            
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
            
            # Se non sono state rilevate intestazioni standard, mantieni il comportamento predefinito (nessuna riga)
            if not headers_detected:
                skip_rows = 0  # Non saltare righe
                debug_container.info(f"Nessuna intestazione standard rilevata. Non salto righe.")
            else:
                debug_container.success(f"Rilevate intestazioni standard. Saltate {skip_rows} righe.")
            
            # Riavvolgi il file per poterlo leggere nuovamente
            uploaded_file.seek(0)
            
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
        
        # Converti le date in formato datetime con gestione robusta di vari formati
        # Prima prova a convertire le date con il formato italiano (DD/MM/YYYY o DD-MM-YYYY)
        try:
            # Verifica se le date potrebbero essere in formato italiano
            sample_date = str(df['Data'].iloc[0]) if len(df) > 0 else ""
            debug_container.info(f"Esempio di formato data rilevato: {sample_date}")
            
            if len(df) > 0 and isinstance(sample_date, str):
                # Rileva il possibile separatore (/ o -)
                separator = "/" if "/" in sample_date else "-" if "-" in sample_date else None
                if separator and len(sample_date.split(separator)) == 3:
                    day, month, year = sample_date.split(separator)
                    # Verifica se il primo numero sembra essere un giorno (1-31)
                    if day.isdigit() and 1 <= int(day) <= 31:
                        debug_container.info(f"Rilevato possibile formato data italiano (DD{separator}MM{separator}YYYY)")
                        # Lista di possibili formati italiani
                        date_formats = [f'%d{separator}%m{separator}%Y', f'%d{separator}%m{separator}%y']
                        
                        # Prova a convertire con i formati italiani
                        for fmt in date_formats:
                            try:
                                debug_container.info(f"Tentativo di conversione con formato: {fmt}")
                                df['Data'] = pd.to_datetime(df['Data'], format=fmt, errors='coerce')
                                if not df['Data'].isna().all():  # Se almeno una data è valida
                                    debug_container.success(f"Date convertite con successo usando il formato: {fmt}")
                                    break
                            except Exception as e:
                                debug_container.warning(f"Formato {fmt} non valido: {str(e)}")
        except Exception as format_err:
            debug_container.warning(f"Errore nel rilevamento del formato data: {str(format_err)}")
        
        # Se le conversioni specifiche falliscono, tenta la conversione automatica come fallback
        if 'Data' not in df.columns or df['Data'].isna().all():
            debug_container.warning("Tentativo di conversione automatica delle date")
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
                st.info("Controlla che le date siano nel formato GG/MM/AAAA o GG-MM-AAAA per il formato italiano, oppure AAAA-MM-GG per il formato standard.")
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
        
        # Verifichiamo esplicitamente che la colonna Data sia di tipo datetime
        if not pd.api.types.is_datetime64_any_dtype(df['Data']):
            debug_container.warning("La colonna Data non è in formato datetime. Tentativo di conversione...")
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            
        # Generiamo i giorni e mesi usando il mapping diretto invece di fare affidamento sulla localizzazione
        # Assicuriamoci che x sia un oggetto datetime prima di chiamare weekday() o month
        df['Giorno'] = df['Data'].apply(lambda x: italian_days.get(x.weekday(), "") if pd.notnull(x) and hasattr(x, 'weekday') else "").str.capitalize()
        df['Mese'] = df['Data'].apply(lambda x: italian_months.get(x.month, "") if pd.notnull(x) and hasattr(x, 'month') else "").str.capitalize()
        
        # Per Anno, utilizziamo lo stesso approccio sicuro con apply() invece di .dt.year
        df['Anno'] = df['Data'].apply(lambda x: str(x.year) if pd.notnull(x) and hasattr(x, 'year') and not pd.isna(x) else "")
        
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
            df['Codice insegnamento'] = df['Codice insegnamento'].apply(normalize_code)
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
            debug_container.success(f"File Excel elaborato con successo: {record_count} record validi importati.")
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

def create_sample_excel():
    """
    Crea un file Excel di esempio con la struttura corretta per l'importazione.
    Il modello è allineato con la struttura del database SQLite.
    
    Returns:
        str: Percorso del file Excel creato
    """
    from datetime import datetime
    
    # Usiamo le costanti definite a livello di modulo per le colonne
    # BASE_COLUMNS e FULL_COLUMNS che importiamo da file_utils
    
    # Crea un DataFrame di esempio con le colonne necessarie
    sample_data = {col: [] for col in FULL_COLUMNS}
    df = pd.DataFrame(sample_data)
    
    # Aggiungi due righe di esempio
    example_rows = [
        {
            'Data': '2025-04-28', 
            'Orario': '14:30-16:45',
            'Dipartimento': 'Area Trasversale - Canale A',
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
            'CFU': 0.5,
            'Note': '',
            'Giorno': 'Lunedì',
            'Mese': 'Aprile',
            'Anno': '2025'
        },
        {
            'Data': '2025-04-29', 
            'Orario': '16:45-19:00',
            'Dipartimento': 'Scienze della Formazione',
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
            'CFU': 0.5,
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
