"""
Utilità per la validazione avanzata dei dati importati nel calendario.
"""
import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Any, Optional
import os
import traceback

def validate_excel_structure(df_original: pd.DataFrame) -> dict:
    """
    Analizza la struttura di un DataFrame importato da Excel e identifica i problemi di mappatura.
    
    Args:
        df_original (pd.DataFrame): DataFrame originale importato dall'Excel
        
    Returns:
        dict: Dizionario con i risultati della validazione, includendo:
            - missing_essential_columns: colonne essenziali mancanti
            - potential_matches: possibili corrispondenze tra colonne Excel e colonne standard
            - problematic_rows: righe con dati incompleti o invalidi
    """
    # Colonne essenziali richieste
    essential_columns = ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento']
    
    # Definire possibili varianti per ogni colonna essenziale
    column_variants = {
        'Data': ['data', 'date', 'giorno', 'day', 'data lezione'],
        'Orario': ['orario', 'ora', 'hour', 'time', 'ora inizio', 'ora fine', 'fascia oraria'],
        'Docente': ['docente', 'prof', 'professore', 'teacher', 'instructor', 'nome docente', 'cognome docente'],
        'Denominazione Insegnamento': ['denominazione insegnamento', 'denominazione', 'insegnamento', 
                                     'materia', 'corso', 'subject', 'course', 'nome insegnamento']
    }
    
    # Risultati della validazione
    results = {
        'missing_essential_columns': [],
        'potential_matches': {},
        'problematic_rows': [],
        'missing_columns_data': {}
    }
    
    # 1. Converti tutti i nomi delle colonne a stringhe e normalizza
    original_columns = [str(col).strip() for col in df_original.columns]
    normalized_columns = [col.lower() for col in original_columns]
    
    # 2. Trova le colonne mancanti
    for std_col in essential_columns:
        # Cerca corrispondenza esatta
        if std_col.lower() in normalized_columns:
            # Colonna trovata
            pass
        else:
            # Cerca tra le varianti
            found = False
            variants = column_variants.get(std_col, [])
            
            # Cerca potenziali corrispondenze basate sui nomi delle colonne
            potential_matches = []
            for i, excel_col in enumerate(normalized_columns):
                for variant in variants:
                    if variant in excel_col or excel_col in variant:
                        potential_matches.append({
                            'original_name': original_columns[i],
                            'confidence': 'Alta' if excel_col == variant else 'Media' 
                                          if excel_col.startswith(variant) or excel_col.endswith(variant) 
                                          else 'Bassa'
                        })
                        found = True
            
            # Aggiungi anche analisi del contenuto per colonne senza nome o con nomi generici
            if not found:
                data_based_matches = []
                # Controlla il contenuto delle colonne per determinare potenziali corrispondenze
                for i, col in enumerate(original_columns):
                    col_data = df_original.iloc[:5, i].astype(str).tolist()
                    col_data_str = ' '.join(col_data).lower()
                    
                    # Regole specifiche per ogni tipo di colonna
                    if std_col == 'Data':
                        # Cerca date nel formato 2025-05-08 o simili
                        if any(['/' in str(x) or '-' in str(x) for x in col_data]) or 'timestamp' in str(type(df_original.iloc[0, i])).lower():
                            data_based_matches.append({
                                'original_name': col,
                                'confidence': 'Alta' if 'timestamp' in str(type(df_original.iloc[0, i])).lower() else 'Media',
                                'sample': col_data[:3]
                            })
                    elif std_col == 'Orario':
                        # Cerca pattern come 17:15-19:30 o simili
                        if any([':' in str(x) for x in col_data]):
                            data_based_matches.append({
                                'original_name': col,
                                'confidence': 'Alta',
                                'sample': col_data[:3]
                            })
                    elif std_col == 'Docente':
                        # Cerca nomi di persone (parole con iniziali maiuscole separate da spazi)
                        if any([' ' in str(x) and not str(x).islower() for x in col_data]):
                            data_based_matches.append({
                                'original_name': col,
                                'confidence': 'Media',
                                'sample': col_data[:3]
                            })
                    elif std_col == 'Denominazione Insegnamento':
                        # Cerca frasi lunghe che sembrano titoli di corsi
                        if any([len(str(x).split()) > 3 for x in col_data]):
                            data_based_matches.append({
                                'original_name': col,
                                'confidence': 'Media',
                                'sample': col_data[:3]
                            })
                
                if data_based_matches:
                    potential_matches.extend(data_based_matches)
                    found = True
            
            if not found or not potential_matches:
                results['missing_essential_columns'].append(std_col)
            else:
                results['potential_matches'][std_col] = potential_matches
    
    # 3. Analizza le prime righe per trovare problemi specifici
    problematic_rows = []
    for i in range(min(10, len(df_original))):
        row_problems = {}
        
        # Per ogni colonna essenziale che abbiamo potenzialmente identificato
        for col in essential_columns:
            if col not in results['missing_essential_columns']:
                # Prendiamo la colonna mappata o la prima corrispondenza potenziale
                col_name = None
                if col in results['potential_matches']:
                    if results['potential_matches'][col]:
                        col_name = results['potential_matches'][col][0]['original_name']
                
                if col_name and col_name in df_original.columns:
                    value = df_original.iloc[i][col_name]
                    if pd.isna(value) or value == '' or value is None:
                        if col not in row_problems:
                            row_problems[col] = []
                        row_problems[col].append(f"Valore mancante nella riga {i+1}")
        
        if row_problems:
            problematic_rows.append({
                'row': i+1,
                'problems': row_problems
            })
    
    results['problematic_rows'] = problematic_rows
    
    # 4. Informazioni sulla mappatura mancante per colonne essenziali
    for col in results['missing_essential_columns']:
        # Prepara una sezione che mostra le informazioni mancanti
        samples = {}
        for i, excel_col in enumerate(original_columns):
            # Mostra i primi 3 valori di ogni colonna che potrebbero contenere i dati mancanti
            if i < len(df_original.columns):
                sample_values = df_original.iloc[:3, i].astype(str).tolist()
                if any(sample_values) and not all(pd.isna(value) for value in sample_values):
                    samples[excel_col] = sample_values
        
        results['missing_columns_data'][col] = {
            'description': f"Non è stato possibile trovare una corrispondenza per '{col}'",
            'possible_columns': samples
        }
    
    return results

def show_validation_results(validation_results: dict, uploaded_file_name: str):
    """
    Mostra i risultati della validazione in una UI Streamlit.
    
    Args:
        validation_results (dict): Risultati della validazione dalla funzione validate_excel_structure
        uploaded_file_name (str): Nome del file caricato
    """
    st.markdown("## 🔍 Analisi dettagliata del file importato")
    st.markdown(f"File analizzato: **{uploaded_file_name}**")
    
    # Mostra il riassunto della validazione
    missing_count = len(validation_results['missing_essential_columns'])
    if missing_count > 0:
        st.error(f"⚠️ **{missing_count} colonne essenziali non trovate** nel file caricato.")
    else:
        st.success("✅ Tutte le colonne essenziali sono state individuate.")
    
    # 1. Mostra dettagli delle colonne mancanti
    if validation_results['missing_essential_columns']:
        st.markdown("### Colonne mancanti")
        
        for col in validation_results['missing_essential_columns']:
            with st.container():
                st.markdown(f"#### 📋 {col}")
                
                # Mostra potenziali corrispondenze se ce ne sono
                if col in validation_results['potential_matches'] and validation_results['potential_matches'][col]:
                    st.markdown("**Possibili corrispondenze:**")
                    for match in validation_results['potential_matches'][col]:
                        confidence = match.get('confidence', 'Sconosciuta')
                        confidence_color = {
                            'Alta': 'green', 
                            'Media': 'orange', 
                            'Bassa': 'red'
                        }.get(confidence, 'grey')
                        
                        st.markdown(f"""
                        - **{match['original_name']}** 
                          <span style='color:{confidence_color};'>(Attendibilità: {confidence})</span>
                        """, unsafe_allow_html=True)
                        
                        if 'sample' in match:
                            st.markdown("  **Esempi di valori:**")
                            st.code(', '.join(str(s) for s in match['sample']))
                
                # Se disponibili, mostra esempi di dati dalle colonne che potrebbero contenere i dati mancanti
                if col in validation_results['missing_columns_data']:
                    col_data = validation_results['missing_columns_data'][col]
                    
                    if col_data['possible_columns']:
                        st.markdown("**Colonne che potrebbero contenere questi dati:**")
                        for col_name, samples in col_data['possible_columns'].items():
                            st.markdown(f"- **{col_name}**: {', '.join(str(s) for s in samples)}")
    
    # 2. Mostra righe problematiche
    if validation_results['problematic_rows']:
        st.markdown("### Righe con dati incompleti")
        for row_info in validation_results['problematic_rows'][:5]:  # Limite a 5 per non sovraccaricare l'UI
            st.markdown(f"**Riga {row_info['row']}:**")
            for col, problems in row_info['problems'].items():
                for problem in problems:
                    st.markdown(f"- {col}: {problem}")
        
        if len(validation_results['problematic_rows']) > 5:
            st.info(f"Mostrate solo le prime 5 righe problematiche su {len(validation_results['problematic_rows'])} totali.")
    
    # 3. Suggerimenti per risolvere i problemi
    st.markdown("### 💡 Suggerimenti per la correzione")
    
    if validation_results['missing_essential_columns']:
        st.markdown("""
        1. **Rinomina le colonne del file Excel** prima di caricarlo:
           - Apri il file in Excel/Calc
           - Modifica i nomi delle colonne per corrispondere esattamente alle colonne richieste
           - Salva il file e caricalo nuovamente
        """)
        
        # Elenco delle colonne essenziali mancanti
        st.markdown("**Assicurati che il file contenga queste colonne:**")
        for col in validation_results['missing_essential_columns']:
            st.markdown(f"- **{col}**")
    
    st.markdown("""
    2. **Scarica il template di esempio** e confrontalo con il tuo file:
       - Verifica la struttura corretta delle colonne
       - Copia i tuoi dati nel template, assicurandoti che i dati corrispondano alle colonne giuste
    """)
    
    # 4. Pulsante per scaricare il template
    st.markdown("---")

def analyze_excel_upload(uploaded_file, debug_container=None):
    """
    Analizza un file Excel caricato dall'utente e restituisce un rapporto dettagliato.
    
    Args:
        uploaded_file: File Excel o CSV caricato tramite st.file_uploader
        debug_container: Container Streamlit per i messaggi di debug (opzionale)
        
    Returns:
        dict: Risultati dell'analisi
    """
    if uploaded_file is None:
        st.warning("Nessun file selezionato per l'analisi.")
        return None
    
    try:
        # Determina il tipo di file in base all'estensione
        file_name = uploaded_file.name.lower()
        is_csv = file_name.endswith('.csv')
        file_type = "CSV" if is_csv else "Excel"
        
        # Leggi il file
        if is_csv:
            # Prova a leggere il file CSV con diverse codifiche e delimitatori
            encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']
            separators = [',', ';', '\t']
            df = None
            
            for encoding in encodings:
                if df is not None:
                    break
                for sep in separators:
                    try:
                        # Riavvolgi il file prima di ogni tentativo
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, encoding=encoding, sep=sep)
                        if not df.empty:
                            break
                    except Exception as e:
                        continue
            
            if df is None:
                st.error(f"⚠️ Analisi fallita: Impossibile leggere il file {file_type}.")
                return None
        else:
            # Per i file Excel, usa il metodo standard
            df = pd.read_excel(uploaded_file)
        
        # Verifica se il DataFrame è vuoto dopo la lettura
        if df.empty:
            st.error(f"⚠️ Analisi fallita: Il file {file_type} caricato è vuoto.")
            return None
            
        # Ora che abbiamo un DataFrame valido, esegui la validazione
        validation_results = validate_excel_structure(df)
        
        # Aggiungi alcune informazioni generali sui dati
        validation_results['file_info'] = {
            'name': uploaded_file.name,
            'type': file_type,
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': list(df.columns)
        }
        
        return validation_results
        
    except Exception as e:
        st.error(f"⚠️ Si è verificato un errore durante l'analisi del file: {str(e)}")
        if debug_container:
            debug_container.error(f"Errore dettagliato: {traceback.format_exc()}")
        return None
