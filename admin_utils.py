import pandas as pd
import streamlit as st
import os
import bcrypt
import datetime
from typing import List, Dict, Any, Union

# Costanti
ADMIN_PASSWORD_HASH = bcrypt.hashpw("2025pef".encode(), bcrypt.gensalt())

def verify_password(password: str) -> bool:
    """Verifica la password dell'amministratore."""
    return bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH)

def login_admin() -> bool:
    """Gestisce il login dell'amministratore."""
    st.subheader("Login Amministratore")
    
    password = st.text_input("Password", type="password", key="admin_login_password")
    login_button = st.button("Login", key="admin_login_button")
    
    if login_button:
        if verify_password(password):
            st.session_state.admin_logged_in = True
            return True
        else:
            st.error("Password errata!")
            return False
    
    return False

def logout_admin() -> None:
    """Logout dell'amministratore."""
    st.session_state.admin_logged_in = False

def is_admin_logged_in() -> bool:
    """Controlla se l'amministratore è loggato."""
    return st.session_state.get('admin_logged_in', False)

def upload_excel_file() -> Union[pd.DataFrame, None]:
    """Gestisce l'upload di un file Excel."""
    uploaded_file = st.file_uploader("Carica il file Excel", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        try:
            # Leggi il file Excel
            df = pd.read_excel(uploaded_file, skiprows=3)
            
            # Rinomina le colonne - Assicurati che ci siano tutte le 16 colonne di base
            base_columns = [
                'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
                'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
                'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
                'Aula', 'Link Teams', 'CFU', 'Note'
            ]
            
            # Assegna le colonne e gestisci il caso in cui ci siano colonne mancanti o troppe
            if len(df.columns) <= len(base_columns):
                # Se ci sono meno colonne del previsto, assegna solo le prime disponibili
                df.columns = base_columns[:len(df.columns)]
                # Aggiungi colonne mancanti con valori nulli
                for col in base_columns[len(df.columns):]:
                    df[col] = None
            else:
                # Se ci sono più colonne del previsto, assegna le prime 16 e ignora il resto
                df = df.iloc[:, :len(base_columns)]
                df.columns = base_columns
            
            # Imposta la localizzazione italiana per le date
            import locale
            try:
                locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
            except:
                try:
                    locale.setlocale(locale.LC_TIME, 'it_IT')
                except:
                    pass

            # Pulizia dei dati
            df = df[df['Orario'].notna() & (df['Orario'] != '')]
            
            # Gestione delle date
            def format_date(date_str):
                if pd.isna(date_str):
                    return None
                try:
                    # Prova prima il formato ISO
                    date = pd.to_datetime(date_str)
                    # Converti in formato italiano
                    formatted_date = date.strftime("%A %d %B %Y").lower()
                    
                    # Aggiungi le colonne Giorno, Mese e Anno
                    return {
                        'data': formatted_date,
                        'giorno': date.strftime("%A").capitalize(),
                        'mese': date.strftime("%B").capitalize(),
                        'anno': date.year
                    }
                except:
                    try:
                        # Se è già nel formato italiano, estraiamo le componenti
                        date = pd.to_datetime(date_str, format="%A %d %B %Y")
                        return {
                            'data': date_str.lower(),
                            'giorno': date.strftime("%A").capitalize(),
                            'mese': date.strftime("%B").capitalize(),
                            'anno': date.year
                        }
                    except:
                        return {
                            'data': None,
                            'giorno': None,
                            'mese': None,
                            'anno': None
                        }

            # Applica la formattazione delle date e crea le nuove colonne
            date_info = df['Data'].apply(format_date)
            df['Data'] = date_info.apply(lambda x: x['data'])
            df['Giorno'] = date_info.apply(lambda x: x['giorno'])
            df['Mese'] = date_info.apply(lambda x: x['mese'])
            df['Anno'] = date_info.apply(lambda x: x['anno'])
            
            return df
        except Exception as e:
            st.error(f"Errore durante la lettura del file: {e}")
            return None
    
    return None

def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """Valida i dati importati e rimuove righe non valide."""
    # Controlla che tutte le colonne richieste siano presenti
    required_columns = [
        'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
        'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
        'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
        'Aula', 'Link Teams', 'CFU', 'Note'
    ]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Colonna mancante: {col}")

    # Rimuovi righe con valori mancanti nelle colonne essenziali
    df = df.dropna(subset=['Data', 'Orario', 'Dipartimento', 'Docente'])

    # Converti la colonna Data in formato datetime standard
    df['Data'] = pd.to_datetime(df['Data'], format='%Y-%m-%d', errors='coerce')

    # Rimuovi righe con date non valide
    df = df.dropna(subset=['Data'])

    return df

def save_dataframe_to_csv(df: pd.DataFrame, path: str = 'dati') -> str:
    """Salva il dataframe come file CSV nella cartella dati."""
    os.makedirs(path, exist_ok=True)

    # Usa sempre lo stesso nome file per mantenere tutti i dati insieme
    file_name = "dati.csv"
    file_path = os.path.join(path, file_name)

    try:
        # Assicurati che il dataframe abbia tutte le colonne necessarie
        required_columns = [
            'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
            'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
            'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
            'Aula', 'Link Teams', 'CFU', 'Note', 'Giorno', 'Mese', 'Anno'
        ]
        
        # Verifica che tutte le colonne richieste siano presenti
        for col in required_columns:
            if col not in df.columns:
                df[col] = None
        
        # Leggi il file esistente se presente
        if os.path.exists(file_path):
            existing_df = pd.read_csv(file_path, delimiter=';', encoding='utf-8', skiprows=3)
            
            # Assicurati che il dataframe esistente abbia tutte le colonne richieste
            if len(existing_df.columns) == len(required_columns):
                existing_df.columns = required_columns
            else:
                # Se il numero di colonne non corrisponde, fissa le colonne esistenti
                existing_cols = min(len(existing_df.columns), len(required_columns))
                existing_df.columns = required_columns[:existing_cols]
                
                # Aggiungi le colonne mancanti
                for col in required_columns[existing_cols:]:
                    existing_df[col] = None
            
            # Standardizza le date nei dataframe esistente e nuovo
            def format_date(date_str):
                if pd.isna(date_str):
                    return None
                try:
                    # Prova prima il formato ISO
                    date = pd.to_datetime(date_str)
                    # Converti in formato italiano
                    return date.strftime("%A %d %B %Y").lower()
                except:
                    try:
                        # Se è già nel formato italiano, lascialo così
                        pd.to_datetime(date_str, format="%A %d %B %Y")
                        return date_str.lower()
                    except:
                        return None

            # Standardizza le date nei dataframe esistente e nuovo se necessario
            if 'Data' in existing_df.columns and 'Data' in df.columns:
                existing_df['Data'] = existing_df['Data'].apply(format_date)
                df['Data'] = df['Data'].apply(format_date)

            # Combina i dati esistenti con i nuovi dati
            df = pd.concat([existing_df, df], ignore_index=True)

        # Rimuovi righe completamente vuote
        df = df.dropna(how='all')
        
        # Rimuovi duplicati basati su colonne chiave
        df = df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'], keep='last')
            
        # Assicurati che i codici insegnamento siano trattati come stringhe senza decimali
        if 'Codice insegnamento' in df.columns:
            df['Codice insegnamento'] = df['Codice insegnamento'].astype(str).apply(
                lambda x: x.split('.')[0] if '.' in x else x
            )

        # Ordina il dataframe per data e orario
        df['Data_temp'] = pd.to_datetime(df['Data'], format='%A %d %B %Y', errors='coerce')
        df = df.sort_values(['Data_temp', 'Orario'])
        df = df.drop('Data_temp', axis=1)

        # Aggiungi le intestazioni necessarie per il formato standard
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Calendario lezioni;;;;;;;;;;;;;;\n")
            f.write("Percorsi di formazione iniziale dei docenti                   ;;;;;;;;;;;;;;;\n")
            f.write("(DPCM 4 agosto 2023);;;;;;;;;;;;;;;\n")

        # Assicurati che ci siano tutte le 19 colonne, incluse Giorno, Mese, Anno
        if 'Giorno' not in df.columns:
            df['Giorno'] = ''
        if 'Mese' not in df.columns:
            df['Mese'] = ''
        if 'Anno' not in df.columns:
            df['Anno'] = ''
            
        # Aggiorna Giorno, Mese e Anno dalle date
        def extract_date_parts(date_str):
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
            except:
                return None, None, None
        
        for idx, row in df.iterrows():
            giorno, mese, anno = extract_date_parts(row['Data'])
            df.at[idx, 'Giorno'] = giorno
            df.at[idx, 'Mese'] = mese
            df.at[idx, 'Anno'] = anno
            
        # Riordina le colonne per assicurarti che siano tutte presenti nell'ordine corretto
        columns_order = [
            'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
            'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
            'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
            'Aula', 'Link Teams', 'CFU', 'Note', 'Giorno', 'Mese', 'Anno'
        ]
        
        # Assicurati che tutte le colonne necessarie siano presenti
        for col in columns_order:
            if col not in df.columns:
                df[col] = ''
                
        df = df[columns_order]
            
        # Salva il dataframe
        df.to_csv(file_path, mode='a', index=False, sep=';', encoding='utf-8')
        
        st.success("Dati salvati correttamente nel file dati.csv")
        
    except Exception as e:
        st.error(f"Errore durante il salvataggio dei dati: {e}")
        
    return file_path

def edit_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """Modifica un singolo record del calendario."""
    st.subheader(f"Modifica record #{index + 1}")
    
    record = df.iloc[index].copy()
    
    # Layout a colonne per i campi del form
    col1, col2 = st.columns(2)
    
    with col1:
        # Usa il formato data originale per la visualizzazione e modifica
        data_str = record['Data'].strftime('%A %d %B %Y') if pd.notna(record['Data']) else ""
        new_data = st.text_input("Data (formato: lunedì 14 aprile 2025)", value=data_str)
        
        new_orario = st.text_input("Orario (formato: 00:00-00:00)", value=record['Orario'] if pd.notna(record['Orario']) else "")
        
        new_dipartimento = st.text_input("Dipartimento", value=record['Dipartimento'] if pd.notna(record['Dipartimento']) else "")
        
        new_classe_concorso = st.text_input("Classe di concorso", value=record['Classe di concorso'] if pd.notna(record['Classe di concorso']) else "")
        
        new_insegnamento_comune = st.text_input("Insegnamento comune", value=record['Insegnamento comune'] if pd.notna(record['Insegnamento comune']) else "")
        
        new_codice = st.text_input("Codice insegnamento", value=record['Codice insegnamento'] if pd.notna(record['Codice insegnamento']) else "")
        
        new_denominazione = st.text_input("Denominazione Insegnamento", value=record['Denominazione Insegnamento'] if pd.notna(record['Denominazione Insegnamento']) else "")
        
        new_docente = st.text_input("Docente", value=record['Docente'] if pd.notna(record['Docente']) else "")
    
    with col2:
        new_pef60 = st.selectbox("PeF60 all.1", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF60 all.1']) if pd.notna(record['PeF60 all.1']) and record['PeF60 all.1'] in ['P', 'D', '---'] else 2)
        
        new_pef30_all2 = st.selectbox("PeF30 all.2", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF30 all.2']) if pd.notna(record['PeF30 all.2']) and record['PeF30 all.2'] in ['P', 'D', '---'] else 2)
        
        new_pef36 = st.selectbox("PeF36 all.5", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF36 all.5']) if pd.notna(record['PeF36 all.5']) and record['PeF36 all.5'] in ['P', 'D', '---'] else 2)
        
        new_pef30_art13 = st.selectbox("PeF30 art.13", options=['P', 'D', '---'], index=['P', 'D', '---'].index(record['PeF30 art.13']) if pd.notna(record['PeF30 art.13']) and record['PeF30 art.13'] in ['P', 'D', '---'] else 2)
        
        new_aula = st.text_input("Aula", value=record['Aula'] if pd.notna(record['Aula']) else "")
        
        new_link = st.text_input("Link Teams", value=record['Link Teams'] if pd.notna(record['Link Teams']) else "")
        
        new_cfu = st.text_input("CFU", value=record['CFU'] if pd.notna(record['CFU']) else "")
        
        new_note = st.text_area("Note", value=record['Note'] if pd.notna(record['Note']) else "")
    
    # Pulsanti per salvare o annullare
    col1, col2 = st.columns(2)
    with col1:
        save = st.button("Salva modifiche")
    with col2:
        cancel = st.button("Annulla")
    
    if save:
        # Aggiorna i dati del record
        try:
            df.at[index, 'Data'] = pd.to_datetime(new_data, format='%A %d %B %Y')
        except:
            st.error("Formato data non valido!")
            return df
        
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
        
        st.success("Record aggiornato con successo!")
    
    if cancel:
        st.experimental_rerun()
    
    return df

def create_new_record(df: pd.DataFrame) -> pd.DataFrame:
    """Crea un nuovo record nel calendario."""
    st.subheader("Aggiungi nuovo record")
    
    # Layout a colonne per i campi del form
    col1, col2 = st.columns(2)
    
    with col1:
        new_data = st.text_input("Data (formato: lunedì 14 aprile 2025)")
        
        new_orario = st.text_input("Orario (formato: 00:00-00:00)")
        
        new_dipartimento = st.text_input("Dipartimento")
        
        new_classe_concorso = st.text_input("Classe di concorso")
        
        new_insegnamento_comune = st.text_input("Insegnamento comune")
        
        new_codice = st.text_input("Codice insegnamento")
        
        new_denominazione = st.text_input("Denominazione Insegnamento")
        
        new_docente = st.text_input("Docente")
    
    with col2:
        new_pef60 = st.selectbox("PeF60 all.1", options=['P', 'D', '---'], index=2)
        
        new_pef30_all2 = st.selectbox("PeF30 all.2", options=['P', 'D', '---'], index=2)
        
        new_pef36 = st.selectbox("PeF36 all.5", options=['P', 'D', '---'], index=2)
        
        new_pef30_art13 = st.selectbox("PeF30 art.13", options=['P', 'D', '---'], index=2)
        
        new_aula = st.text_input("Aula")
        
        new_link = st.text_input("Link Teams")
        
        new_cfu = st.text_input("CFU")
        
        new_note = st.text_area("Note")
    
    # Pulsanti per salvare o annullare
    col1, col2 = st.columns(2)
    with col1:
        save = st.button("Salva nuovo record")
    with col2:
        cancel = st.button("Annulla")
    
    if save:
        # Crea un nuovo record
        try:
            new_record = {
                'Data': pd.to_datetime(new_data, format='%A %d %B %Y'),
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
            }
            
            # Aggiungi il record al dataframe
            df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
            
            st.success("Nuovo record aggiunto con successo!")
        except Exception as e:
            st.error(f"Errore durante l'aggiunta del record: {e}")
    
    if cancel:
        st.experimental_rerun()
    
    return df

def delete_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """Elimina un record dal calendario."""
    # Elimina il record utilizzando iloc per accedere all'indice posizionale invece dell'indice etichetta
    df = df.drop(df.index[index]).reset_index(drop=True)
    st.success("Record eliminato con successo!")
    
    return df

def create_sample_excel():
    """Crea un file Excel di esempio per il caricamento."""
    # Crea un dataframe vuoto con le colonne richieste
    columns = [
        'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
        'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
        'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
        'Aula', 'Link Teams', 'CFU', 'Note'
    ]
    
    # Crea dati di esempio con formato data corretto
    # Usiamo date reali e le formatiamo correttamente
    from datetime import datetime
    
    # Ottieni le date e formattale correttamente in italiano
    date1 = datetime(2025, 5, 5)  # 5 maggio 2025
    date2 = datetime(2025, 5, 5)
    
    import locale
    try:
        # Prova a impostare la localizzazione italiana
        locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    except:
        try:
            # Se fallisce, prova con una localizzazione più generica
            locale.setlocale(locale.LC_TIME, 'it_IT')
        except:
            # Se anche questa fallisce, usiamo l'inglese
            locale.setlocale(locale.LC_TIME, '')
    
    # Formatta le date in italiano
    date_format = "%A %d %B %Y"
    date1_str = date1.strftime(date_format).lower()  # Tutto minuscolo come nell'esempio
    date2_str = date2.strftime(date_format).lower()
    
    data = [
        [date1_str, '14:30-16:45', 'Area Trasversale - Canale A', 'A054', 'Trasversale A', 
         'D', 'D', 'D', '---', '22911115', 'Educazione linguistica', 'Nuzzo Elena', '', '', '0,5', ''],
        [date2_str, '16:45-19:00', 'Area Trasversale - Canale A', 'A054', 'Trasversale A', 
         'D', 'D', 'D', '---', '22911115', 'Educazione linguistica', 'Cortés Velásquez Diego', '', '', '0,5', ''],
    ]
    
    df = pd.DataFrame(data, columns=columns)
    
    # Salva il dataframe come file Excel
    file_path = os.path.join('dati', 'esempio_caricamento.xlsx')
    os.makedirs('dati', exist_ok=True)
    
    # Crea il writer Excel
    writer = pd.ExcelWriter(file_path, engine='openpyxl')
    
    # Aggiungi le intestazioni necessarie prima del dataframe
    workbook = writer.book
    worksheet = workbook.create_sheet("Calendario", 0)
    
    # Aggiungi le intestazioni
    worksheet.cell(row=1, column=1, value="Calendario lezioni")
    worksheet.cell(row=2, column=1, value="Percorsi di formazione iniziale dei docenti")
    worksheet.cell(row=3, column=1, value="(DPCM 4 agosto 2023)")
    
    # Aggiungi le intestazioni delle colonne
    for col_num, column_title in enumerate(columns, 1):
        worksheet.cell(row=4, column=col_num, value=column_title)
    
    # Aggiungi i dati
    for row_num, row_data in enumerate(data, 5):
        for col_num, cell_value in enumerate(row_data, 1):
            worksheet.cell(row=row_num, column=col_num, value=cell_value)
    
    # Salva il file
    writer.close()
    
    return file_path
