"""
Utility generiche per la gestione dei dati del calendario lezioni.
Questo modulo contiene funzioni di supporto generali come normalizzazione e validazione.
"""

import os
import pandas as pd
import streamlit as st
from typing import Optional, Union, Any, List, Dict
from date_utils import format_date

# Costanti per le colonne
BASE_COLUMNS = [
    'Data', 'Orario', 'Dipartimento',
    'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
    'Denominazione Insegnamento', 'Docente',
    'Aula', 'Link Teams', 'CFU', 'Note'
]

FULL_COLUMNS = BASE_COLUMNS + ['Giorno', 'Mese', 'Anno']

# La funzione normalize_code è stata rimossa perché la colonna "codice insegnamento" non è più utilizzata

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
        new_insegnamento_comune = st.text_input("Insegnamento comune")
        
        # Opzioni per i campi PeF: valori ammissibili sono solo "D", "P" o "---"
        pef_options = ["---", "D", "P"]
        
        new_pef60 = st.selectbox("PeF60 all.1", options=pef_options)
        new_pef30_all2 = st.selectbox("PeF30 all.2", options=pef_options)
        new_pef36 = st.selectbox("PeF36 all.5", options=pef_options)
    
    with col2:
        new_pef30_art13 = st.selectbox("PeF30 art.13", options=pef_options)
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
            'Insegnamento comune': new_insegnamento_comune,
            'PeF60 all.1': new_pef60,
            'PeF30 all.2': new_pef30_all2,
            'PeF36 all.5': new_pef36,
            'PeF30 art.13': new_pef30_art13,
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
        from db_operations import save_data
        save_data(df)
        
        success_msg = "Nuovo record aggiunto con successo!"
        if sqlite_success:
            success_msg += " (Salvato nel database SQLite e nel file JSON)"
        else:
            success_msg += " (Salvato solo nel file JSON)"
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
    st.info("Modifica i campi e poi clicca sul pulsante 'Salva modifiche'")
    
    # Converti la data in formato datetime comprensibile
    date_obj = record['Data'] if pd.notna(record['Data']) else None
    date_str = date_obj.strftime('%Y-%m-%d') if date_obj else None
    
    # Preparazione dei campi da modificare
    col1, col2 = st.columns(2)
    
    with col1:
        edit_date = st.date_input("Data", 
                                value=pd.to_datetime(date_str) if date_str else pd.Timestamp.now(),
                                format="YYYY-MM-DD")
        edit_orario = st.text_input("Orario", value=record['Orario'] if pd.notna(record['Orario']) else "")
        edit_dipartimento = st.text_input("Dipartimento", value=record['Dipartimento'] if pd.notna(record['Dipartimento']) else "")
        edit_insegnamento_comune = st.text_input("Insegnamento comune", value=record['Insegnamento comune'] if pd.notna(record['Insegnamento comune']) else "")
        edit_pef60 = st.text_input("PeF60 all.1", value=record['PeF60 all.1'] if pd.notna(record['PeF60 all.1']) else "")
        edit_pef30_all2 = st.text_input("PeF30 all.2", value=record['PeF30 all.2'] if pd.notna(record['PeF30 all.2']) else "")
        edit_pef36 = st.text_input("PeF36 all.5", value=record['PeF36 all.5'] if pd.notna(record['PeF36 all.5']) else "")
    
    with col2:
        edit_pef30_art13 = st.text_input("PeF30 art.13", value=record['PeF30 art.13'] if pd.notna(record['PeF30 art.13']) else "")
        edit_denominazione = st.text_input("Denominazione Insegnamento", value=record['Denominazione Insegnamento'] if pd.notna(record['Denominazione Insegnamento']) else "")
        edit_docente = st.text_input("Docente", value=record['Docente'] if pd.notna(record['Docente']) else "")
        edit_aula = st.text_input("Aula", value=record['Aula'] if pd.notna(record['Aula']) else "")
        edit_link = st.text_input("Link Teams", value=record['Link Teams'] if pd.notna(record['Link Teams']) else "")
        edit_cfu = st.text_input("CFU", value=record['CFU'] if pd.notna(record['CFU']) else "")
        edit_note = st.text_area("Note", value=record['Note'] if pd.notna(record['Note']) else "")
    
    # Pulsante per salvare le modifiche
    if st.button("Salva modifiche"):
        # Verifica che i campi obbligatori siano compilati
        if not edit_date or not edit_orario or not edit_docente or not edit_denominazione:
            st.error("Errore: i campi Data, Orario, Docente e Denominazione Insegnamento sono obbligatori.")
            return df
        
        # Estrai i componenti dalla data
        try:
            giorno = edit_date.strftime("%A").capitalize()
            mese = edit_date.strftime("%B").capitalize()
            anno = str(edit_date.year)
        except Exception as e:
            st.error(f"Errore nella formattazione della data: {e}")
            return df
        
        # Crea un dizionario con i valori modificati
        edited_record = {
            'Data': pd.to_datetime(edit_date),
            'Orario': edit_orario,
            'Dipartimento': edit_dipartimento,
            'Insegnamento comune': edit_insegnamento_comune,
            'PeF60 all.1': edit_pef60,
            'PeF30 all.2': edit_pef30_all2,
            'PeF36 all.5': edit_pef36,
            'PeF30 art.13': edit_pef30_art13,
            'Denominazione Insegnamento': edit_denominazione,
            'Docente': edit_docente,
            'Aula': edit_aula,
            'Link Teams': edit_link,
            'CFU': float(edit_cfu) if edit_cfu.strip() else None,
            'Note': edit_note,
            'Giorno': giorno,
            'Mese': mese,
            'Anno': anno
        }
        
        # Tentativo diretto di aggiornamento nel database SQLite
        sqlite_success = False
        try:
            from db_utils import update_record, delete_record as delete_sql_record
            
            # Per aggiornare un record, eliminiamo il vecchio e inseriamo il nuovo
            old_record_data = df.iloc[index].to_dict()
            
            # Prima elimina il record esistente
            delete_success = delete_sql_record(old_record_data)
            
            # Poi inserisci il nuovo record
            if delete_success:
                if update_record(edited_record):
                    sqlite_success = True
                    try:
                        from log_utils import logger
                        logger.info(f"Record {index} aggiornato con successo nel database SQLite")
                    except ImportError:
                        pass
        except ImportError:
            # Il modulo db_utils non è disponibile o non ha la funzione update_record
            try:
                from log_utils import logger
                logger.warning("Modulo db_utils non supporta update_record, utilizzo solo JSON")
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
        
        # Aggiorna il record nel DataFrame in memoria
        df.iloc[index] = edited_record
        
        # Salva il DataFrame aggiornato nel file JSON
        from db_operations import save_data
        save_data(df, replace_file=True)
        
        success_msg = f"Record {index} aggiornato con successo!"
        if sqlite_success:
            success_msg += " (Aggiornato nel database SQLite e nel file JSON)"
        else:
            success_msg += " (Aggiornato solo nel file JSON)"
        st.success(success_msg)
            
    return df
