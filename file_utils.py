"""
Utility per la gestione dei file del calendario lezioni.
Questo modulo centralizza tutte le operazioni di lettura, scrittura ed eliminazione dei file.
"""

import os
import pandas as pd
import streamlit as st
import locale
import datetime
from typing import Union, Tuple, Dict, Any, List, Optional

# Costanti per i file
DATA_FOLDER = 'dati'
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

def setup_locale() -> None:
    """Imposta la localizzazione italiana per le date."""
    try:
        locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'it_IT')
        except:
            pass  # Fallback alla locale di default

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
        
    try:
        # Se è un oggetto datetime, formattalo direttamente
        if isinstance(date_obj_or_str, (pd.Timestamp, datetime.datetime)):
            return date_obj_or_str.strftime("%A %d %B %Y").lower()
            
        # Se è una stringa, cerca di convertirla a datetime
        date = pd.to_datetime(date_obj_or_str, errors='coerce')
        if pd.notna(date):
            return date.strftime("%A %d %B %Y").lower()
        
        # Se la stringa è già nel formato italiano, lasciala così
        if isinstance(date_obj_or_str, str) and any(month in date_obj_or_str.lower() for month in 
                                                 ["gennaio", "febbraio", "marzo", "aprile", "maggio", 
                                                  "giugno", "luglio", "agosto", "settembre", 
                                                  "ottobre", "novembre", "dicembre"]):
            return date_obj_or_str.lower()
            
    except Exception as e:
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

def create_sample_excel():
    """
    Crea un file Excel di esempio con la struttura corretta per l'importazione.
    
    Returns:
        str: Percorso del file Excel creato
    """
    # Crea un DataFrame di esempio con le colonne necessarie
    sample_data = {col: [] for col in FULL_COLUMNS}
    df = pd.DataFrame(sample_data)
    
    # Aggiungi una riga di esempio
    example_row = {
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
        'CFU': '0.5',
        'Note': '',
        'Giorno': 'Lunedì',
        'Mese': 'Aprile',
        'Anno': '2025'
    }
    df = pd.concat([df, pd.DataFrame([example_row])], ignore_index=True)
    
    # Salva il DataFrame in un file Excel
    template_path = os.path.join(DATA_FOLDER, 'template_calendario.xlsx')
    df.to_excel(template_path, index=False)
    
    return template_path

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
    
    Returns:
        pd.DataFrame: Dataframe contenente i dati del calendario, o None in caso di errore
    """
    setup_locale()

    # Controlla se il file dati.csv esiste
    if not os.path.exists(DEFAULT_CSV_PATH):
        # Se dati.csv non esiste, cerca un altro file CSV come fallback
        csv_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')]
        if not csv_files:
            st.error("Nessun file CSV trovato nella cartella 'dati'")
            return None
        # Usa il file più recente come fallback
        file_path = os.path.join(DATA_FOLDER, sorted(csv_files)[-1])
    else:
        file_path = DEFAULT_CSV_PATH
    
    try:
        # Carica il CSV
        df = pd.read_csv(file_path, delimiter=';', encoding='utf-8', skiprows=3)
        
        # Rinomina le colonne per chiarezza
        if len(df.columns) >= len(FULL_COLUMNS):
            df.columns = FULL_COLUMNS
        else:
            # Se ci sono meno colonne del previsto
            df.columns = FULL_COLUMNS[:len(df.columns)]
            # Aggiungi colonne mancanti
            for col in FULL_COLUMNS[len(df.columns):]:
                df[col] = None
        
        # Pulizia dei dati
        # Filtra le righe che hanno almeno l'orario compilato e non vuoto
        df = df[df['Orario'].notna() & (df['Orario'] != '')]
        
        # Rimuovi i decimali dai codici insegnamento
        if 'Codice insegnamento' in df.columns:
            df['Codice insegnamento'] = df['Codice insegnamento'].apply(normalize_code)
        
        # Converti le date e gestisci gli errori
        df['Data'] = df['Data'].apply(parse_date)
        
        # Rimuovi le righe con date non valide
        df = df.dropna(subset=['Data'])
        
        # Estrai e aggiorna le colonne di Giorno, Mese e Anno
        df['Giorno'] = df['Data'].dt.strftime('%A')
        df['Mese'] = df['Data'].dt.strftime('%B')
        df['Anno'] = df['Data'].dt.year.astype(str)  # Anno come stringa
        
        # Aggiorna il conteggio dei record nella sessione
        st.session_state['total_records'] = len(df)
        
        return df
        
    except Exception as e:
        st.error(f"Errore durante il caricamento dei dati: {e}")
        return None

def save_data(df: pd.DataFrame, replace_file: bool = False) -> str:
    """
    Salva un dataframe nel file CSV standard del calendario.
    
    Args:
        df: DataFrame da salvare
        replace_file: Se True, sovrascrive completamente il file esistente invece di concatenare i dati
        
    Returns:
        str: Percorso del file salvato
    """
    os.makedirs(DATA_FOLDER, exist_ok=True)
    
    try:
        # Assicurati che il dataframe abbia tutte le colonne necessarie
        for col in FULL_COLUMNS:
            if col not in df.columns:
                df[col] = None
        
        # Leggi il file esistente se presente e se non stiamo sostituendo completamente il file
        if os.path.exists(DEFAULT_CSV_PATH) and not replace_file:
            existing_df = pd.read_csv(DEFAULT_CSV_PATH, delimiter=';', encoding='utf-8', skiprows=3)
            
            # Assicurati che il dataframe esistente abbia tutte le colonne richieste
            if len(existing_df.columns) == len(FULL_COLUMNS):
                existing_df.columns = FULL_COLUMNS
            else:
                # Se il numero di colonne non corrisponde, sistemale
                existing_cols = min(len(existing_df.columns), len(FULL_COLUMNS))
                existing_df.columns = FULL_COLUMNS[:existing_cols]
                
                # Aggiungi le colonne mancanti
                for col in FULL_COLUMNS[existing_cols:]:
                    existing_df[col] = None
            
            # Standardizza le date in entrambi i dataframe
            existing_df['Data'] = existing_df['Data'].apply(format_date)
            df['Data'] = df['Data'].apply(format_date)
            
            # Log di debug
            st.info(f"Record esistenti: {len(existing_df)}, Nuovi record: {len(df)}")
            
            # Combina i dati
            df = pd.concat([existing_df, df], ignore_index=True)

        # Pulizia dei dati
        df = df.dropna(how='all')  # Rimuovi righe vuote
        
        # Rimuovi duplicati basati su colonne chiave
        df = df.drop_duplicates(
            subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'], 
            keep='last'
        )
            
        # Normalizza i codici insegnamento
        if 'Codice insegnamento' in df.columns:
            df['Codice insegnamento'] = df['Codice insegnamento'].apply(normalize_code)

        # Ordina il dataframe per data e orario
        df['Data_temp'] = pd.to_datetime(df['Data'], format='%A %d %B %Y', errors='coerce')
        df = df.sort_values(['Data_temp', 'Orario'])
        df = df.drop('Data_temp', axis=1)

        # Aggiungi le intestazioni per il formato standard
        with open(DEFAULT_CSV_PATH, 'w', encoding='utf-8') as f:
            for header in CSV_HEADERS:
                f.write(header)

        # Aggiorna Giorno, Mese e Anno dalle date
        for idx, row in df.iterrows():
            giorno, mese, anno = extract_date_components(row['Data'])
            df.at[idx, 'Giorno'] = giorno
            df.at[idx, 'Mese'] = mese
            df.at[idx, 'Anno'] = anno
            
        # Riordina le colonne
        df = df[FULL_COLUMNS]
            
        # Salva il dataframe
        df.to_csv(DEFAULT_CSV_PATH, mode='a', index=False, sep=';', encoding='utf-8')
        
        st.success(f"Dati salvati correttamente nel file {DEFAULT_CSV_FILE}")
        
    except Exception as e:
        st.error(f"Errore durante il salvataggio dei dati: {e}")
        
    return DEFAULT_CSV_PATH

def delete_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """
    Elimina un record dal DataFrame e aggiorna il file.
    
    Args:
        df: DataFrame contenente i dati
        index: Indice del record da eliminare
        
    Returns:
        pd.DataFrame: DataFrame aggiornato senza il record eliminato
    """
    if index < 0 or index >= len(df):
        st.error(f"Errore: indice record non valido ({index}). Deve essere tra 0 e {len(df)-1}")
        return df
        
    # Elimina il record
    df = df.drop(df.index[index]).reset_index(drop=True)
    
    # Salva il DataFrame aggiornato con sovrascrittura completa del file
    save_data(df, replace_file=True)
    
    # Conferma
    st.success("Record eliminato con successo!")
    
    return df

def process_excel_upload(uploaded_file) -> pd.DataFrame:
    """
    Processa un file Excel caricato dall'utente.
    
    Args:
        uploaded_file: File Excel caricato tramite st.file_uploader
        
    Returns:
        pd.DataFrame: DataFrame con i dati del file, o None in caso di errore
    """
    if uploaded_file is None:
        return None
        
    try:
        setup_locale()
        
        # Leggi il file Excel
        df = pd.read_excel(uploaded_file, skiprows=3)
        
        # Gestisci le colonne
        if len(df.columns) <= len(BASE_COLUMNS):
            # Se ci sono meno colonne del previsto
            df.columns = BASE_COLUMNS[:len(df.columns)]
            # Aggiungi colonne mancanti
            for col in BASE_COLUMNS[len(df.columns):]:
                df[col] = None
        else:
            # Se ci sono più colonne del previsto
            df = df.iloc[:, :len(BASE_COLUMNS)]
            df.columns = BASE_COLUMNS
        
        # Pulizia dei dati
        df = df[df['Orario'].notna() & (df['Orario'] != '')]
        
        # Processa le date
        date_info = []
        for date_str in df['Data']:
            if pd.isna(date_str):
                date_info.append({
                    'data': None,
                    'giorno': None,
                    'mese': None,
                    'anno': None
                })
                continue
                
            try:
                # Prova prima il formato ISO
                date = pd.to_datetime(date_str)
                date_info.append({
                    'data': date.strftime("%A %d %B %Y").lower(),
                    'giorno': date.strftime("%A").capitalize(),
                    'mese': date.strftime("%B").capitalize(),
                    'anno': str(date.year)
                })
            except:
                try:
                    # Se è già nel formato italiano
                    date = pd.to_datetime(date_str, format="%A %d %B %Y")
                    date_info.append({
                        'data': date_str.lower(),
                        'giorno': date.strftime("%A").capitalize(),
                        'mese': date.strftime("%B").capitalize(),
                        'anno': str(date.year)
                    })
                except:
                    date_info.append({
                        'data': None,
                        'giorno': None,
                        'mese': None,
                        'anno': None
                    })
        
        # Aggiorna il DataFrame con le informazioni di data
        date_info_df = pd.DataFrame(date_info)
        df['Data'] = date_info_df['data']
        df['Giorno'] = date_info_df['giorno']
        df['Mese'] = date_info_df['mese']
        df['Anno'] = date_info_df['anno']
        
        return df
    except Exception as e:
        st.error(f"Errore durante la lettura del file: {e}")
        return None

def edit_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """
    Modifica un singolo record del calendario e lo salva automaticamente.
    
    Args:
        df: DataFrame contenente i dati
        index: Indice del record da modificare
        
    Returns:
        pd.DataFrame: DataFrame aggiornato con le modifiche
    """
    st.subheader(f"Modifica record #{index + 1}")
    
    if index < 0 or index >= len(df):
        st.error(f"Indice non valido: {index}")
        return df
    
    record = df.iloc[index].copy()
    
    # Layout a colonne per i campi del form
    col1, col2 = st.columns(2)
    
    with col1:
        # Usa il formato data originale per la visualizzazione e modifica
        data_str = record['Data'].strftime('%A %d %B %Y') if pd.notna(record['Data']) else ""
        new_data = st.text_input("Data (formato: lunedì 14 aprile 2025)", value=data_str, key=f"data_{index}")
        
        new_orario = st.text_input("Orario (formato: 00:00-00:00)", value=record['Orario'] if pd.notna(record['Orario']) else "", key=f"orario_{index}")
        
        new_dipartimento = st.text_input("Dipartimento", value=record['Dipartimento'] if pd.notna(record['Dipartimento']) else "", key=f"dipartimento_{index}")
        
        new_classe_concorso = st.text_input("Classe di concorso", value=record['Classe di concorso'] if pd.notna(record['Classe di concorso']) else "", key=f"classe_concorso_{index}")
        
        new_insegnamento_comune = st.text_input("Insegnamento comune", value=record['Insegnamento comune'] if pd.notna(record['Insegnamento comune']) else "", key=f"insegnamento_comune_{index}")
        
        new_codice = st.text_input("Codice insegnamento", value=record['Codice insegnamento'] if pd.notna(record['Codice insegnamento']) else "", key=f"codice_{index}")
        
        new_denominazione = st.text_input("Denominazione Insegnamento", value=record['Denominazione Insegnamento'] if pd.notna(record['Denominazione Insegnamento']) else "", key=f"denominazione_{index}")
        
        new_docente = st.text_input("Docente", value=record['Docente'] if pd.notna(record['Docente']) else "", key=f"docente_{index}")
    
    with col2:
        new_pef60 = st.selectbox("PeF60 all.1", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF60 all.1']) if pd.notna(record['PeF60 all.1']) and record['PeF60 all.1'] in ['P', 'D', '---'] else 2, key=f"pef60_{index}")
        
        new_pef30_all2 = st.selectbox("PeF30 all.2", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF30 all.2']) if pd.notna(record['PeF30 all.2']) and record['PeF30 all.2'] in ['P', 'D', '---'] else 2, key=f"pef30_all2_{index}")
        
        new_pef36 = st.selectbox("PeF36 all.5", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF36 all.5']) if pd.notna(record['PeF36 all.5']) and record['PeF36 all.5'] in ['P', 'D', '---'] else 2)
        
        new_pef30_art13 = st.selectbox("PeF30 art.13", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF30 art.13']) if pd.notna(record['PeF30 art.13']) and record['PeF30 art.13'] in ['P', 'D', '---'] else 2, key=f"pef30_art13_{index}")
        
        new_aula = st.text_input("Aula", value=record['Aula'] if pd.notna(record['Aula']) else "", key=f"aula_{index}")
        
        new_link = st.text_input("Link Teams", value=record['Link Teams'] if pd.notna(record['Link Teams']) else "", key=f"link_teams_{index}")
        
        new_cfu = st.text_input("CFU", value=record['CFU'] if pd.notna(record['CFU']) else "", key=f"cfu_{index}")
        
        new_note = st.text_area("Note", value=record['Note'] if pd.notna(record['Note']) else "", key=f"note_{index}")
    
    # Pulsanti per salvare o annullare
    col1, col2 = st.columns(2)
    with col1:
        save = st.button("Salva modifiche", key=f"save_button_{index}")
    with col2:
        cancel = st.button("Annulla", key=f"cancel_button_{index}")
    
    if save:
        # Aggiorna i dati del record
        try:
            # Usa la funzione centralizzata per il parsing delle date
            parsed_date = parse_date(new_data)
            if parsed_date is None:
                st.error("Formato data non valido!")
                return df
                
            df.at[index, 'Data'] = parsed_date
            
            # Estrai e aggiorna Giorno, Mese, Anno usando la funzione centralizzata
            giorno, mese, anno = extract_date_components(format_date(parsed_date))
            df.at[index, 'Giorno'] = giorno
            df.at[index, 'Mese'] = mese
            df.at[index, 'Anno'] = anno
            
        except Exception as e:
            st.error(f"Errore nell'elaborazione della data: {e}")
            return df
        
        # Aggiorna gli altri campi
        df.at[index, 'Orario'] = new_orario
        df.at[index, 'Dipartimento'] = new_dipartimento
        df.at[index, 'Classe di concorso'] = new_classe_concorso
        df.at[index, 'Insegnamento comune'] = new_insegnamento_comune
        df.at[index, 'PeF60 all.1'] = new_pef60
        df.at[index, 'PeF30 all.2'] = new_pef30_all2
        df.at[index, 'PeF36 all.5'] = new_pef36
        df.at[index, 'PeF30 art.13'] = new_pef30_art13
        df.at[index, 'Codice insegnamento'] = new_codice
        df.at[index, 'Denominazione Insegnamento'] = new_denominazione
        df.at[index, 'Docente'] = new_docente
        df.at[index, 'Aula'] = new_aula
        df.at[index, 'Link Teams'] = new_link
        df.at[index, 'CFU'] = new_cfu
        df.at[index, 'Note'] = new_note
        
        # Salva automaticamente i cambiamenti utilizzando la funzione centralizzata
        save_data(df)
        
        st.success("Record aggiornato e salvato con successo!")
    
    if cancel:
        st.experimental_rerun()
    
    return df

def create_new_record(df: pd.DataFrame) -> pd.DataFrame:
    """
    Crea un nuovo record nel calendario e lo salva automaticamente.
    
    Args:
        df: DataFrame contenente i dati attuali
        
    Returns:
        pd.DataFrame: DataFrame aggiornato con il nuovo record
    """
    st.subheader("Aggiungi nuovo record")
    
    # Inizializza le variabili per il riutilizzo dei dati
    continue_iteration = st.session_state.get('continue_iteration', False)
    last_record = st.session_state.get('last_record', {})
    
    # Aggiunta della funzionalità per selezionare un record esistente come base
    use_existing_record = False
    selected_record_idx = None
    
    # Mostriamo l'opzione solo se ci sono record nel DataFrame
    if len(df) > 0:
        col1, col2 = st.columns([1, 3])
        with col1:
            use_existing_record = st.checkbox("Usa record esistente", key="use_existing_record")
        
        # Se l'utente ha selezionato di usare un record esistente
        if use_existing_record:
            # Filtra i record esistenti
            with col2:
                search_term = st.text_input("Cerca record (docente, insegnamento, data, etc.)", key="search_existing")
            
            if search_term:
                # Cerca in tutte le colonne di stringhe
                mask = pd.Series(False, index=df.index)
                for col in df.columns:
                    if df[col].dtype == 'object':  # Solo colonne di tipo object (stringhe)
                        mask = mask | df[col].fillna('').astype(str).str.lower().str.contains(search_term.lower())
                filtered_df = df[mask]
            else:
                filtered_df = df
            
            # Mostra i record filtrati per consentirne la selezione
            if len(filtered_df) > 0:
                # Prepara i record per la visualizzazione
                filtered_df['Data_str'] = filtered_df['Data'].apply(format_date)
                
                # Mostra le colonne rilevanti per la selezione
                view_cols = ['Data_str', 'Orario', 'Denominazione Insegnamento', 'Docente']
                st.dataframe(filtered_df[view_cols], use_container_width=True, height=200)
                
                # Crea le opzioni per il selectbox
                record_options = [f"{i+1}. {format_date(filtered_df.iloc[i]['Data'])} - {filtered_df.iloc[i]['Orario']} - {filtered_df.iloc[i]['Denominazione Insegnamento']} ({filtered_df.iloc[i]['Docente']})" 
                                for i in range(len(filtered_df))]
                
                # Selectbox per selezionare il record
                selected_record = st.selectbox("Seleziona il record da cui importare i dati:", 
                                             record_options, 
                                             key="select_record_base")
                
                if selected_record:
                    # Ottieni l'indice del record selezionato
                    selected_record_idx = filtered_df.index[record_options.index(selected_record)]
                    
                    # Usa i dati dal record selezionato
                    record_to_use = df.iloc[selected_record_idx].copy()
                    
                    # Aggiorna il last_record con i dati del record selezionato
                    last_record = record_to_use.to_dict()
                    st.success(f"Importati i dati dal record: {selected_record}")
                    # Imposta il flag per indicare che stiamo usando un record selezionato
                    continue_iteration = True
            else:
                if search_term:
                    st.warning("Nessun record trovato con questi criteri di ricerca.")
                else:
                    st.info("Inserisci un termine di ricerca per trovare un record da utilizzare.")
    
    # Se si sta continuando l'iterazione, prepara i dati dal record precedente
    if continue_iteration:
        # Reimposta il flag
        st.session_state.continue_iteration = False
        
        # Recupera i valori dal record precedente
        default_date = last_record.get('Data', None)
        default_orario = last_record.get('Orario', '')
        default_dipartimento = last_record.get('Dipartimento', '')
        default_classe_concorso = last_record.get('Classe di concorso', '')
        default_insegnamento_comune = last_record.get('Insegnamento comune', '')
        default_codice = last_record.get('Codice insegnamento', '')
        default_denominazione = last_record.get('Denominazione Insegnamento', '')
        default_docente = last_record.get('Docente', '')
        default_pef60 = last_record.get('PeF60 all.1', '---')
        default_pef30_all2 = last_record.get('PeF30 all.2', '---')
        default_pef36 = last_record.get('PeF36 all.5', '---')
        default_pef30_art13 = last_record.get('PeF30 art.13', '---')
        default_aula = last_record.get('Aula', '')
        default_link = last_record.get('Link Teams', '')
        default_cfu = last_record.get('CFU', '')
        default_note = last_record.get('Note', '')
        
        st.info("I campi sono stati precompilati con i dati del record selezionato")
    else:
        # Valori predefiniti vuoti se non si sta continuando l'iterazione
        default_date = None
        default_orario = ''
        default_dipartimento = ''
        default_classe_concorso = ''
        default_insegnamento_comune = ''
        default_codice = ''
        default_denominazione = ''
        default_docente = ''
        default_pef60 = '---'
        default_pef30_all2 = '---'
        default_pef36 = '---'
        default_pef30_art13 = '---'
        default_aula = ''
        default_link = ''
        default_cfu = ''
        default_note = ''
    
    # Usa una chiave unica per il form
    form_key = "new_record_form"
    
    # Crea un form per raggruppare tutti i campi di input
    with st.form(key=form_key):
        # Layout a colonne per i campi del form
        col1, col2 = st.columns(2)
        
        with col1:
            # Utilizza date_input per selezionare la data con un calendario
            selected_date = st.date_input(
                "Data", 
                value=default_date,
                format="DD/MM/YYYY",
                help="Seleziona la data della lezione"
            )
            
            new_orario = st.text_input("Orario (formato: 00:00-00:00)", value=default_orario)
            
            new_dipartimento = st.text_input("Dipartimento", value=default_dipartimento)
            
            new_classe_concorso = st.text_input("Classe di concorso", value=default_classe_concorso)
            
            new_insegnamento_comune = st.text_input("Insegnamento comune", value=default_insegnamento_comune)
            
            new_codice = st.text_input("Codice insegnamento", value=default_codice)
            
            new_denominazione = st.text_input("Denominazione Insegnamento", value=default_denominazione)
            
            new_docente = st.text_input("Docente", value=default_docente)
        
        with col2:
            new_pef60 = st.selectbox("PeF60 all.1", options=['P', 'D', '---'], index=['P', 'D', '---'].index(default_pef60) if default_pef60 in ['P', 'D', '---'] else 2)
            
            new_pef30_all2 = st.selectbox("PeF30 all.2", options=['P', 'D', '---'], index=['P', 'D', '---'].index(default_pef30_all2) if default_pef30_all2 in ['P', 'D', '---'] else 2)
            
            new_pef36 = st.selectbox("PeF36 all.5", options=['P', 'D', '---'], index=['P', 'D', '---'].index(default_pef36) if default_pef36 in ['P', 'D', '---'] else 2)
            
            new_pef30_art13 = st.selectbox("PeF30 art.13", options=['P', 'D', '---'], index=['P', 'D', '---'].index(default_pef30_art13) if default_pef30_art13 in ['P', 'D', '---'] else 2)
            
            new_aula = st.text_input("Aula", value=default_aula)
            
            new_link = st.text_input("Link Teams", value=default_link)
            
            new_cfu = st.text_input("CFU", value=default_cfu)
            
            new_note = st.text_area("Note", value=default_note)
        
        # Pulsante di submit del form
        submit_button = st.form_submit_button(label="Salva nuovo record")
    
    # Pulsante per annullare (fuori dal form)
    if st.button("Annulla"):
        st.experimental_rerun()
        return df
    
    if submit_button:
        # Mostra un messaggio di caricamento
        with st.spinner("Salvataggio del nuovo record in corso..."):
            try:
                # Verifica se la data è stata selezionata
                if selected_date is None:
                    st.error("Seleziona una data valida!")
                    return df
                
                # Verifica se almeno il campo orario è stato compilato
                if not new_orario or new_orario.strip() == "":
                    st.error("Il campo Orario è obbligatorio!")
                    return df
                    
                # Imposta la locale per i nomi in italiano
                setup_locale()
                    
                # Converti la data selezionata in un oggetto datetime pandas
                parsed_date = pd.Timestamp(selected_date)
                
                # Estrai i componenti della data
                giorno = parsed_date.strftime("%A").capitalize()
                mese = parsed_date.strftime("%B").capitalize()
                anno = str(parsed_date.year)
                
                # Crea il nuovo record con tutti i campi necessari
                new_record = {
                    'Data': parsed_date,
                    'Orario': new_orario,
                    'Dipartimento': new_dipartimento,
                    'Classe di concorso': new_classe_concorso,
                    'Insegnamento comune': new_insegnamento_comune,
                    'PeF60 all.1': new_pef60,
                    'PeF30 all.2': new_pef30_all2,
                    'PeF36 all.5': new_pef36,
                    'PeF30 art.13': new_pef30_art13,
                    'Codice insegnamento': new_codice,
                    'Denominazione Insegnamento': new_denominazione,
                    'Docente': new_docente,
                    'Aula': new_aula,
                    'Link Teams': new_link,
                    'CFU': new_cfu,
                    'Note': new_note,
                    'Giorno': giorno,
                    'Mese': mese,
                    'Anno': anno
                }
                
                # Debug: mostra i valori del nuovo record
                st.info(f"Data: {parsed_date}, Giorno: {giorno}, Mese: {mese}, Anno: {anno}")
                
                # Aggiungi il record al dataframe
                new_df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
                
                # Salva automaticamente il dataframe aggiornato
                save_data(new_df, replace_file=True)
                
                st.success("Nuovo record aggiunto e salvato con successo!")
                
                # Chiedi all'utente se desidera continuare ad aggiungere record
                if "continue_adding" not in st.session_state:
                    st.session_state.continue_adding = True
                
                # Salva il record corrente in session_state per un eventuale riutilizzo
                st.session_state.last_record = new_record.copy()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Aggiungi un altro record", key="add_another"):
                        st.session_state.continue_adding = True
                        # Ricarica la pagina per ripulire il form
                        st.experimental_rerun()
                with col2:
                    if st.button("Continuare l'iterazione?", key="btn_continue_iteration"):
                        st.session_state.continue_adding = True
                        st.session_state.continue_iteration = True
                        # Salva i dati dell'ultimo record per poterli riutilizzare
                        st.session_state.last_record = new_record.copy()
                        # Ricarica la pagina mantenendo i dati dell'ultimo record
                        st.experimental_rerun()
                with col3:
                    if st.button("Termina inserimento", key="finish_adding"):
                        st.session_state.continue_adding = False
                        
                # Ritorniamo il dataframe aggiornato
                return new_df
                
            except Exception as e:
                st.error(f"Errore durante l'aggiunta del record: {e}")
                import traceback
                st.error(f"Dettaglio: {traceback.format_exc()}")
    
    return df

def create_sample_excel():
    """
    Crea un file Excel di esempio con la struttura corretta per l'importazione.
    
    Returns:
        str: Percorso del file Excel creato
    """
    # Crea un DataFrame di esempio con le colonne necessarie
    sample_data = {col: [] for col in FULL_COLUMNS}
    df = pd.DataFrame(sample_data)
    
    # Aggiungi una riga di esempio
    example_row = {
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
        'CFU': '0.5',
        'Note': '',
        'Giorno': 'Lunedì',
        'Mese': 'Aprile',
        'Anno': '2025'
    }
    df = pd.concat([df, pd.DataFrame([example_row])], ignore_index=True)
    
    # Salva il DataFrame in un file Excel
    template_path = os.path.join(DATA_FOLDER, 'template_calendario.xlsx')
    df.to_excel(template_path, index=False)
    
    return template_path

def duplicate_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """
    Duplica un record esistente e permette di modificarlo prima di salvarlo.
    
    Args:
        df: DataFrame contenente i dati
        index: Indice del record da duplicare
        
    Returns:
        pd.DataFrame: DataFrame aggiornato con il record duplicato
    """
    # Chiavi di sessione per questo form
    session_prefix = f"dup_{index}_"
    form_id = f"duplicate_form_{index}"
    
    # Controlla se è attivo un processo di duplicazione per questo record
    if f"duplicating_{index}" not in st.session_state:
        # Prima volta che apriamo il form, inizializza i dati
        st.session_state[f"duplicating_{index}"] = True
        
        # Ottieni il record da duplicare
        record = df.iloc[index].copy()
        
        # Stampiamo i valori del record originale per debug
        st.write("Valori del record originale:")
        st.write(f"Denominazione: {record['Denominazione Insegnamento']}")
        st.write(f"Docente: {record['Docente']}")
        st.write(f"Dipartimento: {record['Dipartimento']}")
        st.write(f"Classe di concorso: {record['Classe di concorso']}")
        st.write(f"CFU: {record['CFU']}")
        
        # Imposta i valori predefiniti
        try:
            # Per la data, impostiamo la data corrente come default (può essere cambiata dall'utente)
            st.session_state[f"{session_prefix}date"] = datetime.datetime.now().date()
            
            # Per l'orario, lasciamolo vuoto per inserimento manuale
            st.session_state[f"{session_prefix}orario"] = ""
            
            # Copia TUTTI i campi dal record originale senza tentativi di conversione che potrebbero fallire
            # Campi principali
            st.session_state[f"{session_prefix}dipartimento"] = record['Dipartimento'] if pd.notna(record['Dipartimento']) else ""
            st.session_state[f"{session_prefix}classe_concorso"] = record['Classe di concorso'] if pd.notna(record['Classe di concorso']) else ""
            st.session_state[f"{session_prefix}insegnamento_comune"] = record['Insegnamento comune'] if pd.notna(record['Insegnamento comune']) else ""
            st.session_state[f"{session_prefix}codice"] = record['Codice insegnamento'] if pd.notna(record['Codice insegnamento']) else ""
            st.session_state[f"{session_prefix}denominazione"] = record['Denominazione Insegnamento'] if pd.notna(record['Denominazione Insegnamento']) else ""
            st.session_state[f"{session_prefix}docente"] = record['Docente'] if pd.notna(record['Docente']) else ""
            
            # Campi PeF - Manteniamo i valori originali senza forzare il formato
            st.session_state[f"{session_prefix}pef60"] = record['PeF60 all.1'] if pd.notna(record['PeF60 all.1']) else "---"
            st.session_state[f"{session_prefix}pef30_all2"] = record['PeF30 all.2'] if pd.notna(record['PeF30 all.2']) else "---"
            st.session_state[f"{session_prefix}pef36"] = record['PeF36 all.5'] if pd.notna(record['PeF36 all.5']) else "---"
            st.session_state[f"{session_prefix}pef30_art13"] = record['PeF30 art.13'] if pd.notna(record['PeF30 art.13']) else "---"
            
            # Altri campi
            st.session_state[f"{session_prefix}aula"] = record['Aula'] if pd.notna(record['Aula']) else ""
            st.session_state[f"{session_prefix}link"] = record['Link Teams'] if pd.notna(record['Link Teams']) else ""
            st.session_state[f"{session_prefix}cfu"] = record['CFU'] if pd.notna(record['CFU']) else ""
            st.session_state[f"{session_prefix}note"] = record['Note'] if pd.notna(record['Note']) else ""
        except Exception as e:
            st.warning(f"Errore nell'inizializzazione dei campi: {e}")
    
    st.subheader(f"Duplica record #{index + 1}")
    
    if index < 0 or index >= len(df):
        st.error(f"Indice non valido: {index}")
        if f"duplicating_{index}" in st.session_state:
            del st.session_state[f"duplicating_{index}"]
        return df
    
    # Prepara le opzioni per i menu a tendina
    pef_options = ['P', 'D', '---']
    
    # Aggiungiamo una form per dare struttura e logica all'interfaccia
    with st.form(key=f"duplicate_form_{form_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Data con date_input (NON MODIFICARE il valore dopo)
            selected_date = st.date_input(
                "Data", 
                value=st.session_state.get(f"{session_prefix}date", datetime.datetime.now().date()),
                format="DD/MM/YYYY",
                help="Seleziona la data della lezione",
                key=f"{session_prefix}date_input"
            )
            
            # Altri campi del form
            orario = st.text_input(
                "Orario (formato: 00:00-00:00)", 
                value=st.session_state.get(f"{session_prefix}orario", ""),
                key=f"{session_prefix}orario_input"
            )
            
            dipartimento = st.text_input(
                "Dipartimento", 
                value=st.session_state.get(f"{session_prefix}dipartimento", ""),
                key=f"{session_prefix}dipartimento_input"
            )
            
            classe_concorso = st.text_input(
                "Classe di concorso", 
                value=st.session_state.get(f"{session_prefix}classe_concorso", ""),
                key=f"{session_prefix}classe_concorso_input"
            )
            
            insegnamento_comune = st.text_input(
                "Insegnamento comune", 
                value=st.session_state.get(f"{session_prefix}insegnamento_comune", ""),
                key=f"{session_prefix}insegnamento_comune_input"
            )
            
            codice = st.text_input(
                "Codice insegnamento", 
                value=st.session_state.get(f"{session_prefix}codice", ""),
                key=f"{session_prefix}codice_input"
            )
            
            denominazione = st.text_input(
                "Denominazione Insegnamento", 
                value=st.session_state.get(f"{session_prefix}denominazione", ""),
                key=f"{session_prefix}denominazione_input"
            )
            
            docente = st.text_input(
                "Docente", 
                value=st.session_state.get(f"{session_prefix}docente", ""),
                key=f"{session_prefix}docente_input"
            )
        
        with col2:
            # Menu a tendina con indici corretti
            pef60 = st.selectbox(
                "PeF60 all.1", 
                options=pef_options, 
                index=pef_options.index(st.session_state.get(f"{session_prefix}pef60", "---")),
                key=f"{session_prefix}pef60_select"
            )
            
            pef30_all2 = st.selectbox(
                "PeF30 all.2", 
                options=pef_options, 
                index=pef_options.index(st.session_state.get(f"{session_prefix}pef30_all2", "---")),
                key=f"{session_prefix}pef30_all2_select"
            )
            
            pef36 = st.selectbox(
                "PeF36 all.5", 
                options=pef_options, 
                index=pef_options.index(st.session_state.get(f"{session_prefix}pef36", "---")),
                key=f"{session_prefix}pef36_select"
            )
            
            pef30_art13 = st.selectbox(
                "PeF30 art.13", 
                options=pef_options, 
                index=pef_options.index(st.session_state.get(f"{session_prefix}pef30_art13", "---")),
                key=f"{session_prefix}pef30_art13_select"
            )
            
            aula = st.text_input(
                "Aula", 
                value=st.session_state.get(f"{session_prefix}aula", ""),
                key=f"{session_prefix}aula_input"
            )
            
            link = st.text_input(
                "Link Teams", 
                value=st.session_state.get(f"{session_prefix}link", ""),
                key=f"{session_prefix}link_input"
            )
            
            cfu = st.text_input(
                "CFU", 
                value=st.session_state.get(f"{session_prefix}cfu", ""),
                key=f"{session_prefix}cfu_input"
            )
            
            note = st.text_area(
                "Note", 
                value=st.session_state.get(f"{session_prefix}note", ""),
                key=f"{session_prefix}note_input"
            )
        
        # Pulsante di invio del form
        submitted = st.form_submit_button("Salva come nuovo record")
    
    # Pulsante per annullare (fuori dal form)
    if st.button("Annulla", key=f"cancel_btn_{form_id}"):
        # Pulisci lo stato della sessione
        if f"duplicating_{index}" in st.session_state:
            del st.session_state[f"duplicating_{index}"]
            
        # Pulisci tutti i valori dalla sessione
        for key in list(st.session_state.keys()):
            if key.startswith(session_prefix):
                del st.session_state[key]
                
        st.rerun()
    
    if submitted:
        # Crea un nuovo record
        try:
            # Converti la data selezionata in datetime
            if selected_date is None:
                st.error("Seleziona una data valida!")
                return df
                
            # Imposta la locale per ottenere i nomi italiani
            setup_locale()
            
            # Converti la data selezionata in un oggetto datetime pandas
            parsed_date = pd.Timestamp(selected_date)
            
            # Estrai i componenti della data
            giorno = parsed_date.strftime("%A").capitalize()
            mese = parsed_date.strftime("%B").capitalize()
            anno = str(parsed_date.year)
            
            # Crea il nuovo record con tutti i campi necessari
            new_record = {
                'Data': parsed_date,
                'Orario': orario,
                'Dipartimento': dipartimento,
                'Classe di concorso': classe_concorso,
                'Insegnamento comune': insegnamento_comune,
                'PeF60 all.1': pef60,
                'PeF30 all.2': pef30_all2,
                'PeF36 all.5': pef36,
                'PeF30 art.13': pef30_art13,
                'Codice insegnamento': codice,
                'Denominazione Insegnamento': denominazione,
                'Docente': docente,
                'Aula': aula,
                'Link Teams': link,
                'CFU': cfu,
                'Note': note,
                'Giorno': giorno,
                'Mese': mese,
                'Anno': anno
            }
            
            # Aggiungi il record al dataframe
            new_df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
            
            # Salva il dataframe aggiornato
            save_data(new_df, replace_file=True)
            
            # Messaggio di successo
            st.success("Record duplicato e salvato con successo!")
            
            # Pulisci lo stato della sessione
            if f"duplicating_{index}" in st.session_state:
                del st.session_state[f"duplicating_{index}"]
                
            # Pulisci tutti i valori dalla sessione
            for key in list(st.session_state.keys()):
                if key.startswith(session_prefix):
                    del st.session_state[key]
            
            # Restituisci subito il nuovo dataframe invece di fare rerun
            return new_df
            
        except Exception as e:
            st.error(f"Errore durante la duplicazione del record: {e}")
            import traceback
            st.error(f"Dettaglio: {traceback.format_exc()}")
    
    # Se non è stato premuto il pulsante di salvataggio, restituisci il DataFrame originale
    return df

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
    
    # Tab per visualizzare i record
    with admin_tabs[0]:
        st.subheader("Elenco Records")
        
        # Funzionalità di ricerca
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            search_term = st.text_input("Cerca nei record (docente, insegnamento, data, etc.)", key="admin_search")
        with search_col2:
            search_button = st.button("Cerca")
        
        # Filtra i risultati in base alla ricerca
        display_df = df.copy()
        if search_term:
            # Cerca in tutte le colonne di stringhe
            mask = pd.Series(False, index=display_df.index)
            for col in display_df.columns:
                if display_df[col].dtype == 'object':  # Solo colonne di tipo object (stringhe)
                    mask = mask | display_df[col].fillna('').astype(str).str.lower().str.contains(search_term.lower())
            display_df = display_df[mask]
            st.info(f"Trovati {len(display_df)} record corrispondenti alla ricerca.")
        
        # Mostra i record
        if len(display_df) > 0:
            # Mostra tutte le colonne rilevanti
            view_cols = ['Data', 'Orario', 'Dipartimento', 'Classe di concorso', 'Insegnamento comune', 
                      'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
                      'Codice insegnamento', 'Denominazione Insegnamento', 'Docente', 'Aula', 
                      'Link Teams', 'CFU', 'Note']
            
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
