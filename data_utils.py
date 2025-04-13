"""
Utility per la manipolazione dei dati del calendario lezioni.
Questo modulo contiene funzioni per creare, modificare ed eliminare record di dati.
"""

import pandas as pd
import streamlit as st
from typing import Dict, Any, Optional

# Importa le funzioni necessarie da file_utils
from file_utils import (
    save_data, format_date, normalize_code,
    FULL_COLUMNS
)

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
