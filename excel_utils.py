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
import re  # Importazione aggiunta per le espressioni regolari
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

        # Passo 3: Gestione delle colonne - Mappatura intelligente
        current_step += 1
        update_progress(current_step, total_steps, "Preparazione delle colonne")
        
        # Colonne essenziali (senza Giorno, Mese, Anno che vengono generati automaticamente)
        essential_columns = BASE_COLUMNS
        
        # Normalizza le intestazioni del file Excel (rimuovi spazi in eccesso, converti in minuscolo)
        original_columns = df.columns.tolist()
        normalized_excel_columns = [str(col).strip().lower() for col in original_columns]
        
        # Mostra informazioni sulle colonne rilevate
        debug_container.info(f"Colonne rilevate nel file: {len(df.columns)}")
        debug_container.info(f"Nomi delle colonne originali: {original_columns}")
        
        # Crea un mapping tra le colonne standard e le colonne del file Excel
        column_mapping = {}
        unmapped_columns = []
        
        # Crea una lista di possibili varianti dei nomi delle colonne standard
        column_variants = {
            'Data': ['data', 'date', 'giorno', 'day'],
            'Orario': ['orario', 'ora', 'hour', 'time', 'ora inizio', 'ora fine'],
            'Dipartimento': ['dipartimento', 'department', 'dip', 'dipartimento di riferimento'],
            'Insegnamento comune': ['insegnamento comune', 'ins comune', 'comune', 'common'],
            'PeF60 all.1': ['pef60 all.1', 'pef60', 'all.1', 'allegato 1'],
            'PeF30 all.2': ['pef30 all.2', 'pef30', 'all.2', 'allegato 2'],
            'PeF36 all.5': ['pef36 all.5', 'pef36', 'all.5', 'allegato 5'],
            'PeF30 art.13': ['pef30 art.13', 'art.13', 'articolo 13'],
            'Codice insegnamento': ['codice insegnamento', 'codice', 'code', 'id corso', 'id insegnamento', 'course code'],
            'Denominazione Insegnamento': ['denominazione insegnamento', 'denominazione', 'insegnamento', 'materia', 'corso', 'subject', 'course'],
            'Docente': ['docente', 'prof', 'professore', 'teacher', 'instructor'],
            'Aula': ['aula', 'room', 'classe', 'class', 'location'],
            'Link Teams': ['link teams', 'teams', 'link', 'url', 'collegamento'],
            'CFU': ['cfu', 'crediti', 'crediti formativi', 'credits'],
            'Note': ['note', 'notes', 'annotazioni', 'commenti', 'comments']
        }
        
        # Per ogni colonna standard, cerca una corrispondenza nel file Excel
        for std_col in essential_columns:
            found = False
            std_col_lower = std_col.lower()
            
            # Prima cerca una corrispondenza esatta
            if std_col_lower in normalized_excel_columns:
                idx = normalized_excel_columns.index(std_col_lower)
                column_mapping[std_col] = original_columns[idx]
                found = True
            else:
                # Poi cerca tra le varianti
                variants = column_variants.get(std_col, [])
                for variant in variants:
                    for i, excel_col in enumerate(normalized_excel_columns):
                        # Verifica se la variante è nel nome della colonna Excel
                        if variant == excel_col or variant in excel_col.split():
                            column_mapping[std_col] = original_columns[i]
                            found = True
                            break
                    if found:
                        break
            
            # Se non è stata trovata nessuna corrispondenza
            if not found:
                unmapped_columns.append(std_col)
        
        # Identifica colonne nel file Excel che non corrispondono a colonne standard
        mapped_excel_cols = list(column_mapping.values())
        extra_columns = [col for col in original_columns if col not in mapped_excel_cols]
        
        # Registra dettagli sulle colonne extra per analisi futura
        if extra_columns:
            # Estrai un campione dei valori delle colonne extra per capire cosa contengono
            extra_columns_sample = {}
            sample_size = min(5, len(df))
            for col in extra_columns:
                # Prendi un campione dei primi valori non nulli
                sample_values = df[col].dropna().head(sample_size).tolist()
                extra_columns_sample[col] = sample_values
            
            # Salva informazioni sulle colonne extra nei log
            try:
                from log_utils import logger
                logger.info(f"Colonne aggiuntive ignorate durante l'importazione: {extra_columns}")
                logger.info(f"Campione valori colonne extra: {extra_columns_sample}")
            except ImportError:
                pass
        
        # Log delle informazioni di mappatura
        debug_container.info(f"Colonne mappate: {len(column_mapping)}/{len(essential_columns)}")
        if unmapped_columns:
            debug_container.warning(f"Colonne standard non trovate: {unmapped_columns}")
        if extra_columns:
            debug_container.warning(f"Colonne extra non utilizzate: {extra_columns}")
        
        # Crea un nuovo DataFrame con le colonne mappate correttamente
        new_df = pd.DataFrame()
        
        # Copia i dati dalle colonne mappate
        for std_col, excel_col in column_mapping.items():
            new_df[std_col] = df[excel_col]
        
        # Aggiungi colonne standard mancanti con valori nulli
        for col in unmapped_columns:
            new_df[col] = None
            debug_container.warning(f"Aggiunta colonna mancante: {col}")
        
        # Sostituisci il DataFrame originale con quello mappato
        df = new_df
        
        # Verifica le colonne essenziali per la validità dei dati
        missing_essential = [col for col in ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'] if col not in column_mapping]
        if missing_essential:
            progress_bar.empty()
            status_text.empty()
            st.error(f"⚠️ Importazione fallita: Mancano colonne essenziali: {', '.join(missing_essential)}")
            st.info("Scarica il template per vedere la struttura corretta delle colonne.")
            return None
        
        # Mostra un riepilogo della mappatura all'utente con feedback migliorato
        with st.expander("Dettaglio mappatura colonne"):
            st.write("**Colonne riconosciute e mappate:**")
            for std_col, excel_col in column_mapping.items():
                st.write(f"- '{excel_col}' → '{std_col}'")
            
            if extra_columns:
                st.write("**Colonne aggiuntive ignorate:**")
                st.info("Le seguenti colonne non sono state riconosciute e sono state ignorate durante l'importazione:")
                
                # Estrai piccoli campioni per mostrare cosa contenevano queste colonne
                sample_size = min(3, len(df))
                for col in extra_columns:
                    try:
                        # Verifica se la colonna esiste ancora nel dataframe prima di accedervi
                        if col in df.columns:
                            # Mostra un campione dei primi valori non nulli
                            sample_values = df[col].dropna().head(sample_size).tolist()
                            sample_str = ", ".join([f'"{v}"' for v in sample_values]) if sample_values else "nessun valore"
                        else:
                            sample_str = "colonna rimossa"
                        st.write(f"- '{col}' (esempi: {sample_str})")
                    except Exception as col_err:
                        # In caso di errore, mostra un messaggio generico
                        st.write(f"- '{col}' (impossibile mostrare esempi)")
                        debug_container.warning(f"Errore nell'accesso alla colonna '{col}': {str(col_err)}")
                
                st.info("💡 Suggerimento: Se ritieni che alcune di queste colonne contengano dati importanti, considera di rinominarle nel file Excel usando i nomi standard delle colonne e riprova l'importazione.")
            
            if unmapped_columns:
                st.write("**Colonne standard mancanti create automaticamente:**")
                missing_essential = [col for col in ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'] if col in unmapped_columns]
                if missing_essential:
                    st.warning(f"⚠️ Attenzione: Mancano colonne essenziali: {', '.join(missing_essential)}. Questi campi sono stati creati vuoti e dovrai compilarli manualmente.")
                
                for col in unmapped_columns:
                    importance = "**essenziale**" if col in ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'] else "opzionale"
                    st.write(f"- '{col}' (campo {importance})")
            
            # Aggiungi pulsante per scaricare il template
            st.write("---")
            st.info("Se hai problemi con l'importazione, puoi scaricare un modello Excel con le colonne corrette:")
            if st.button("📥 Scarica modello Excel", key="download_template_button"):
                try:
                    template_path = create_sample_excel()
                    with open(template_path, "rb") as file:
                        template_bytes = file.read()
                    
                    st.download_button(
                        label="⬇️ Clicca per scaricare il modello Excel",
                        data=template_bytes,
                        file_name="template_calendario.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Impossibile generare il template: {str(e)}")
        
        # Assicurati che tutte le colonne standard siano presenti
        for col in essential_columns:
            if col not in df.columns:
                df[col] = None
        
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
        
        # Passo 5: Gestione avanzata delle date
        current_step += 1
        update_progress(current_step, total_steps, "Conversione e validazione avanzata delle date")
        
        # Miglioramento del rilevamento e della conversione dei formati di data
        try:
            # Prima verifichiamo se ci sono date da convertire
            if 'Data' not in df.columns or df.empty:
                debug_container.warning("Nessuna colonna 'Data' trovata o DataFrame vuoto")
            else:
                # Salva una copia delle date originali per riferimento
                df['Data_originale'] = df['Data'].copy()
                
                # Analizza un campione di date per determinare il formato più probabile
                sample_dates = df['Data'].dropna().head(5).tolist()
                sample_dates_str = [str(d) for d in sample_dates if pd.notna(d)]
                
                debug_container.info(f"Campione di date da analizzare: {sample_dates_str}")
                
                # Definisci diversi formati di data comuni da provare
                # Metti i formati italiani all'inizio per dare loro priorità
                date_formats = {
                    "Italiano (GG-MM-AAAA)": ['%d-%m-%Y', '%d-%m-%y'],  # Formato principale richiesto
                    "Italiano (GG/MM/AAAA)": ['%d/%m/%Y', '%d/%m/%y'],  # Formato italiano alternativo
                    "Testo Italiano (GG mese AAAA)": ['%d %B %Y', '%d %b %Y'],
                    "Internazionale (AAAA-MM-GG)": ['%Y-%m-%d'],
                    "Internazionale (AAAA/MM/GG)": ['%Y/%m/%d'],
                    "US/UK (MM/GG/AAAA)": ['%m/%d/%Y', '%m/%d/%y'],
                    "US/UK (MM-GG-AAAA)": ['%m-%d-%Y', '%m-%d-%y'],
                }
                
                # Funzione per testare un formato su un campione di date
                def test_date_format(date_str, fmt):
                    try:
                        dt = pd.to_datetime(date_str, format=fmt)
                        return not pd.isna(dt)
                    except:
                        return False
                
                # Conto per ciascun formato quante date del campione riconosce
                format_scores = {}
                
                for format_name, formats in date_formats.items():
                    format_scores[format_name] = 0
                    for fmt in formats:
                        score = sum(1 for d in sample_dates_str if test_date_format(d, fmt))
                        if score > format_scores[format_name]:
                            format_scores[format_name] = score
                
                # Ordina i formati per punteggio
                best_formats = sorted(format_scores.items(), key=lambda x: x[1], reverse=True)
                
                debug_container.info(f"Analisi dei formati di data: {best_formats}")
                
                # Prova a convertire con i formati migliori
                conversion_success = False
                for format_name, score in best_formats:
                    if score > 0:  # Se almeno una data è stata riconosciuta con questo formato
                        for fmt in date_formats[format_name]:
                            try:
                                temp_dates = pd.to_datetime(df['Data'], format=fmt, errors='coerce')
                                # Se almeno l'80% delle date sono state convertite correttamente, usa questo formato
                                valid_ratio = temp_dates.notna().mean()
                                if valid_ratio >= 0.8:
                                    df['Data'] = temp_dates
                                    debug_container.success(f"Date convertite con formato {format_name} ({fmt}): {valid_ratio:.1%} valide")
                                    conversion_success = True
                                    break
                                else:
                                    debug_container.info(f"Formato {format_name} ({fmt}) ha riconosciuto solo {valid_ratio:.1%} delle date")
                            except Exception as e:
                                debug_container.warning(f"Errore con formato {fmt}: {str(e)}")
                    
                    if conversion_success:
                        break
                
                # Se nessun formato specifico ha funzionato abbastanza bene, prova la conversione automatica
                if not conversion_success:
                    debug_container.warning("Nessun formato specifico ha funzionato bene. Tentativo di conversione automatica...")
                    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                    valid_ratio = df['Data'].notna().mean()
                    debug_container.info(f"Conversione automatica: {valid_ratio:.1%} date valide")
                
                # Identifica le date problematiche per fornire feedback all'utente
                invalid_dates_idx = df['Data'].isna()
                if invalid_dates_idx.any():
                    invalid_count = invalid_dates_idx.sum()
                    debug_container.warning(f"Rilevate {invalid_count} date non valide")
                    
                    # Mostra esempi di date non valide
                    invalid_examples = df.loc[invalid_dates_idx, 'Data_originale'].head(5).tolist()
                    debug_container.warning(f"Esempi di date non valide: {invalid_examples}")
                    
                    # Offri suggerimenti all'utente con priorità al formato italiano
                    with st.expander("⚠️ Date non valide rilevate"):
                        st.warning(f"Sono state trovate {invalid_count} date non valide nel file.")
                        st.write("Esempi di date problematiche:")
                        for i, example in enumerate(invalid_examples):
                            st.code(f"{example}")
                        st.info("Suggerimento: Assicurati che le date siano nel formato italiano GG-MM-AAAA (es. 28-04-2025) o GG/MM/AAAA (es. 28/04/2025)")
        
        except Exception as format_err:
            debug_container.error(f"Errore durante l'analisi del formato delle date: {str(format_err)}")
            debug_container.error(traceback.format_exc())
        
        # Rimozione delle righe con date non valide (dopo tutti i tentativi di conversione)
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
                st.info("Controlla che le date siano nel formato italiano GG-MM-AAAA (preferibile) o GG/MM/AAAA. Questi sono i formati ufficiali per le date in Italia.")
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
        # Gestiamo in modo sicuro le possibili eccezioni nella generazione dei giorni
        try:
            # Colonna Giorno - con gestione robusta degli errori
            df['Giorno'] = df['Data'].apply(
                lambda x: italian_days.get(x.weekday(), "") if pd.notnull(x) and hasattr(x, 'weekday') else ""
            )
            # Capitalizza solo se non ci sono valori NaN
            if not df['Giorno'].isna().all():
                df['Giorno'] = df['Giorno'].str.capitalize()
            
            # Colonna Mese - con gestione robusta degli errori
            df['Mese'] = df['Data'].apply(
                lambda x: italian_months.get(x.month, "") if pd.notnull(x) and hasattr(x, 'month') else ""
            )
            # Capitalizza solo se non ci sono valori NaN
            if not df['Mese'].isna().all():
                df['Mese'] = df['Mese'].str.capitalize()
            
            # Per Anno, utilizziamo lo stesso approccio sicuro con apply() invece di .dt.year
            df['Anno'] = df['Data'].apply(
                lambda x: str(x.year) if pd.notnull(x) and hasattr(x, 'year') else ""
            )
        except Exception as date_err:
            debug_container.error(f"Errore durante la generazione di Giorno, Mese e Anno: {str(date_err)}")
            # Assicuriamo che i campi esistano anche in caso di errore
            if 'Giorno' not in df.columns: df['Giorno'] = ""
            if 'Mese' not in df.columns: df['Mese'] = ""
            if 'Anno' not in df.columns: df['Anno'] = ""
        
        # Controlla se ci sono problemi con i campi generati
        if df['Giorno'].isna().any() or df['Mese'].isna().any():
            debug_container.warning("Attenzione: Alcuni nomi di Giorno o Mese potrebbero non essere stati generati correttamente")
            status_text.text("Attenzione: Alcuni campi relativi alle date potrebbero non essere completi")
        
        # Passo 7: Elaborazione finale e validazione
        current_step += 1
        update_progress(current_step, total_steps, "Validazione finale e normalizzazione dei dati")
        
        # Gestione avanzata dei CFU con rilevamento e correzione di errori comuni
        if 'CFU' in df.columns:
            # Salva una copia dei valori originali per riferimento e debug
            df['CFU_originale'] = df['CFU'].copy()
            
            # Converti tutto in stringa per un'elaborazione uniforme
            df['CFU'] = df['CFU'].astype(str)
            
            # Funzione avanzata per la normalizzazione e correzione dei CFU
            def normalize_cfu(cfu_value):
                if pd.isna(cfu_value) or cfu_value == '' or cfu_value in ['nan', 'None', 'NaN', 'none', '<NA>', 'null']:
                    return 0.0
                
                try:
                    # Converti a stringa se non lo è già
                    cfu_str = str(cfu_value).strip()
                    
                    # Sostituisci virgole con punti per la notazione decimale
                    cfu_str = cfu_str.replace(',', '.')
                    
                    # Gestisci frazioni comuni (es. "1/2" -> 0.5)
                    if '/' in cfu_str:
                        num, denom = map(float, cfu_str.split('/', 1))
                        return num / denom if denom != 0 else 0.0
                    
                    # Gestisci formati come "1h" o "1 ora" (1 ora = 0.125 CFU)
                    if 'h' in cfu_str.lower() or 'ora' in cfu_str.lower() or 'ore' in cfu_str.lower():
                        # Estrai solo i numeri
                        import re
                        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", cfu_str)
                        if numbers:
                            hours = float(numbers[0])
                            # Converti ore in CFU (8 ore = 1 CFU)
                            return round(hours / 8, 2)
                    
                    # Gestisci valori fuori range
                    cfu_float = float(cfu_str)
                    
                    # Se il valore è troppo grande (probabilmente sono minuti invece di CFU)
                    if cfu_float > 30:  # Nessun corso ha più di 30 CFU tipicamente
                        # Potrebbe essere in minuti, converti in CFU (480 minuti = 1 CFU)
                        return round(cfu_float / 480, 2)
                    
                    return cfu_float
                    
                except Exception:
                    return 0.0
            
            # Applica la funzione di normalizzazione a tutti i valori
            df['CFU'] = df['CFU'].apply(normalize_cfu)
            
            # Rileva e registra le correzioni significative per il feedback
            cfu_corrections = []
            for idx, (original, normalized) in enumerate(zip(df['CFU_originale'], df['CFU'])):
                if str(original) != str(normalized) and not (pd.isna(original) and normalized == 0.0):
                    # Registra solo le correzioni significative
                    try:
                        if abs(float(str(original).replace(',', '.')) - normalized) > 0.01:
                            cfu_corrections.append((idx, original, normalized))
                    except:
                        cfu_corrections.append((idx, original, normalized))
            
            # Fornisci feedback sulle correzioni
            if cfu_corrections:
                debug_container.info(f"Corretti {len(cfu_corrections)} valori CFU non standard")
                
                # Limitati ai primi 10 esempi per non sovraccaricare l'interfaccia
                with st.expander(f"ℹ️ Valori CFU corretti automaticamente ({len(cfu_corrections)})"):
                    st.info("Alcuni valori CFU sono stati normalizzati automaticamente:")
                    for i, (idx, original, normalized) in enumerate(cfu_corrections[:10]):
                        st.write(f"- Riga {idx+1}: '{original}' → {normalized}")
                    if len(cfu_corrections) > 10:
                        st.write(f"... e altri {len(cfu_corrections) - 10} valori")
                    st.info("💡 Suggerimento: Per ottenere risultati più precisi, formatta i CFU come numeri decimali nel file Excel (es. 0.5)")
            
            # Log dei valori CFU finali
            debug_container.info(f"Valori CFU elaborati. Range: {df['CFU'].min()} - {df['CFU'].max()}, Media: {df['CFU'].mean():.2f}")

        # Gestisci Codice insegnamento (rimuovi .0 se presente) con gestione più robusta
        if 'Codice insegnamento' in df.columns:
            # Converti in stringa e gestisci valori nulli
            df['Codice insegnamento'] = df['Codice insegnamento'].fillna('').astype(str)
            # Rimuovi .0 alla fine dei codici numerici
            df['Codice insegnamento'] = df['Codice insegnamento'].apply(normalize_code)
            # Rimuovi spazi extra all'inizio e alla fine
            df['Codice insegnamento'] = df['Codice insegnamento'].str.strip()

        # Sistema intelligente di validazione e rilevamento degli errori
        validation_issues = {
            'missing_fields': [],      # Campi obbligatori mancanti
            'format_issues': [],       # Problemi di formato (es. orario)
            'suspicious_values': [],   # Valori sospetti che potrebbero essere errori
            'auto_corrections': []     # Correzioni automatiche applicate
        }
        
        # 1. Verifica dei campi essenziali mancanti
        for idx, row in df.iterrows():
            # Controlla i campi essenziali
            missing_fields = []
            
            if pd.isna(row['Docente']) or row['Docente'] == '':
                missing_fields.append('Docente')
                
            if pd.isna(row['Denominazione Insegnamento']) or row['Denominazione Insegnamento'] == '':
                missing_fields.append('Denominazione Insegnamento')
                
            if missing_fields:
                date_str = row['Data'].strftime('%d/%m/%Y') if pd.notna(row['Data']) and hasattr(row['Data'], 'strftime') else "Data sconosciuta"
                validation_issues['missing_fields'].append((idx, date_str, missing_fields))
        
        # 2. Verifica e correzione del formato orario
        orario_fixed = 0
        orario_pattern = re.compile(r'^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$')
        
        for idx, orario in enumerate(df['Orario']):
            if pd.isna(orario) or orario == '':
                continue
                
            # Se l'orario è già nel formato corretto, salta
            if orario_pattern.match(str(orario)):
                continue
            
            original = str(orario)
            corrected = None
            
            # Tentativo di correzione automatica dei formati di orario comuni
            try:
                # Caso: separatore diverso da : (es. 14.30-16.45)
                if re.match(r'^\d{1,2}[.,]\d{2}-\d{1,2}[.,]\d{2}$', original):
                    corrected = re.sub(r'(\d{1,2})[.,](\d{2})-(\d{1,2})[.,](\d{2})', r'\1:\2-\3:\4', original)
                
                # Caso: orari con H (es. 14H30-16H45)
                elif re.match(r'^\d{1,2}[hH]\d{2}-\d{1,2}[hH]\d{2}$', original):
                    corrected = re.sub(r'(\d{1,2})[hH](\d{2})-(\d{1,2})[hH](\d{2})', r'\1:\2-\3:\4', original)
                
                # Caso: spazi attorno al trattino (es. 14:30 - 16:45)
                elif re.match(r'^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$', original):
                    corrected = re.sub(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', r'\1-\2', original)
                
                # Caso: formato con testo (es. "dalle 14:30 alle 16:45")
                elif "alle" in original.lower() and re.search(r'\d{1,2}:\d{2}', original):
                    # Estrai gli orari
                    orari = re.findall(r'\d{1,2}:\d{2}', original)
                    if len(orari) >= 2:
                        corrected = f"{orari[0]}-{orari[1]}"
                
                if corrected and corrected != original:
                    df.at[idx, 'Orario'] = corrected
                    validation_issues['auto_corrections'].append((idx, 'Orario', original, corrected))
                    orario_fixed += 1
            
            except Exception as e:
                debug_container.warning(f"Errore nella correzione dell'orario: {str(e)}")
        
        if orario_fixed > 0:
            debug_container.success(f"Corretti automaticamente {orario_fixed} formati di orario non standard")
        
        # 3. Rilevamento di valori sospetti e potenziali errori
        
        # 3.1 Controlla durate delle lezioni anomale (meno di 30 minuti o più di 5 ore)
        for idx, row in df.iterrows():
            if pd.isna(row['Orario']) or row['Orario'] == '':
                continue
                
            try:
                # Estrai le ore di inizio e fine
                if '-' in str(row['Orario']):
                    start, end = str(row['Orario']).split('-')
                    
                    # Converti in minuti dall'inizio della giornata
                    def time_to_minutes(time_str):
                        if ':' in time_str:
                            h, m = map(int, time_str.split(':'))
                            return h * 60 + m
                        return 0
                    
                    start_min = time_to_minutes(start)
                    end_min = time_to_minutes(end)
                    
                    # Gestisci il caso di lezioni che finiscono dopo mezzanotte
                    if end_min < start_min:
                        end_min += 24 * 60  # Aggiungi un giorno
                        
                    duration = end_min - start_min
                    
                    # Rileva durate sospette
                    if duration < 30:
                        validation_issues['suspicious_values'].append((idx, 'Orario', row['Orario'], 'Durata troppo breve (meno di 30 minuti)'))
                    elif duration > 300:  # 5 ore
                        validation_issues['suspicious_values'].append((idx, 'Orario', row['Orario'], 'Durata sospettamente lunga (più di 5 ore)'))
            
            except Exception:
                # Se c'è un errore nell'analisi, potrebbe essere un formato di orario non riconosciuto
                validation_issues['format_issues'].append((idx, 'Orario', row['Orario'], 'Formato non riconosciuto'))
        
        # 3.2 Controlla CFU sospetti (molto grandi o con decimali strani)
        if 'CFU' in df.columns:
            for idx, cfu in enumerate(df['CFU']):
                if pd.isna(cfu):
                    continue
                
                try:
                    cfu_value = float(cfu)
                    # CFU troppo grandi
                    if cfu_value > 12:  # Raramente un singolo corso ha più di 12 CFU
                        validation_issues['suspicious_values'].append((idx, 'CFU', cfu, 'Valore insolitamente alto per un singolo corso'))
                except:
                    pass
        
        # 4. Visualizza un riepilogo dei problemi rilevati e delle correzioni
        total_issues = (len(validation_issues['missing_fields']) + 
                       len(validation_issues['format_issues']) + 
                       len(validation_issues['suspicious_values']))
                       
        total_corrections = len(validation_issues['auto_corrections'])
        
        if total_issues > 0 or total_corrections > 0:
            with st.expander(f"📊 Riepilogo validazione dati ({total_issues} problemi, {total_corrections} correzioni automatiche)"):
                # Tab per visualizzare diversi tipi di problemi
                tabs = st.tabs(["Campi mancanti", "Problemi di formato", "Valori sospetti", "Correzioni automatiche"])
                
                # Tab 1: Campi mancanti
                with tabs[0]:
                    if validation_issues['missing_fields']:
                        st.warning(f"{len(validation_issues['missing_fields'])} righe con campi essenziali mancanti")
                        for idx, data_str, campi in validation_issues['missing_fields'][:15]:  # limita a 15 per non sovraccaricare l'UI
                            st.write(f"- Riga {idx+1} ({data_str}): Mancano {', '.join(campi)}")
                        if len(validation_issues['missing_fields']) > 15:
                            st.write(f"... e altri {len(validation_issues['missing_fields']) - 15} record")
                    else:
                        st.success("Tutti i campi essenziali sono compilati ✓")
                
                # Tab 2: Problemi di formato
                with tabs[1]:
                    if validation_issues['format_issues']:
                        st.warning(f"{len(validation_issues['format_issues'])} problemi di formato rilevati")
                        for idx, campo, valore, descrizione in validation_issues['format_issues'][:15]:
                            st.write(f"- Riga {idx+1}, {campo}: '{valore}' → {descrizione}")
                        if len(validation_issues['format_issues']) > 15:
                            st.write(f"... e altri {len(validation_issues['format_issues']) - 15} problemi")
                    else:
                        st.success("Nessun problema di formato rilevato ✓")
                
                # Tab 3: Valori sospetti
                with tabs[2]:
                    if validation_issues['suspicious_values']:
                        st.warning(f"{len(validation_issues['suspicious_values'])} valori potenzialmente errati")
                        for idx, campo, valore, descrizione in validation_issues['suspicious_values'][:15]:
                            st.write(f"- Riga {idx+1}, {campo}: '{valore}' → {descrizione}")
                        if len(validation_issues['suspicious_values']) > 15:
                            st.write(f"... e altri {len(validation_issues['suspicious_values']) - 15} valori")
                    else:
                        st.success("Nessun valore sospetto rilevato ✓")
                
                # Tab 4: Correzioni automatiche
                with tabs[3]:
                    if validation_issues['auto_corrections']:
                        st.info(f"{len(validation_issues['auto_corrections'])} correzioni applicate automaticamente")
                        for idx, campo, originale, corretto in validation_issues['auto_corrections'][:15]:
                            st.write(f"- Riga {idx+1}, {campo}: '{originale}' → '{corretto}'")
                        if len(validation_issues['auto_corrections']) > 15:
                            st.write(f"... e altre {len(validation_issues['auto_corrections']) - 15} correzioni")
                    else:
                        st.success("Nessuna correzione automatica necessaria ✓")
                
                # Suggerimenti generali
                st.info("💡 Suggerimento: Per ottenere i migliori risultati, assicurati che i dati seguano questi formati:")
                st.code("""
                Data: GG/MM/AAAA (es. 28/04/2025) o AAAA-MM-GG (es. 2025-04-28)
                Orario: HH:MM-HH:MM (es. 14:30-16:45)
                CFU: Numero decimale (es. 0.5)
                """)
        
        # Aggiorna lo stato per mostrare i problemi rilevati
        if len(validation_issues['missing_fields']) > 0:
            status_text.text(f"Trovate {len(validation_issues['missing_fields'])} righe con dati essenziali mancanti")

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
            'Data': '28-04-2025', 
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
            'Data': '29-04-2025', 
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
        worksheet.write(len(df) + 6, 0, "• La Data deve essere nel formato italiano DD-MM-YYYY (es. 28-04-2025)")
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
