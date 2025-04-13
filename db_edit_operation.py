import pandas as pd
import streamlit as st
import traceback
import os
import time
from data_utils import normalize_code

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
    
    # Crea una copia locale del record per la modifica (usando valori semplici, non oggetti pandas)
    new_record = {
        'Data': pd.to_datetime(date_str) if date_str else None,
        'Orario': record['Orario'],
        'Dipartimento': record['Dipartimento'],
        'Classe di concorso': record['Classe di concorso'],
        'Insegnamento comune': record['Insegnamento comune'],
        'PeF60 all.1': record['PeF60 all.1'],
        'PeF30 all.2': record['PeF30 all.2'],
        'PeF36 all.5': record['PeF36 all.5'],
        'PeF30 art.13': record['PeF30 art.13'],
        'Codice insegnamento': record['Codice insegnamento'],
        'Denominazione Insegnamento': record['Denominazione Insegnamento'],
        'Docente': record['Docente'],
        'Aula': record['Aula'],
        'Link Teams': record['Link Teams'],
        'CFU': str(record['CFU']) if pd.notna(record['CFU']) else "",
        'Note': record['Note']
    }
    
    # Preparazione dei campi da modificare
    col1, col2 = st.columns(2)
    
    with col1:
        new_record['Data'] = st.date_input(
            "Data", 
            value=new_record['Data'] if new_record['Data'] is not None else None,
            format="YYYY-MM-DD",
            key=f"date_{index}"
        )
        
        new_record['Orario'] = st.text_input(
            "Orario (es. 14:30-16:45)", 
            value=new_record['Orario'], 
            key=f"orario_{index}"
        )
        
        new_record['Dipartimento'] = st.text_input(
            "Dipartimento", 
            value=new_record['Dipartimento'], 
            key=f"dipartimento_{index}"
        )
        
        new_record['Classe di concorso'] = st.text_input(
            "Classe di concorso", 
            value=new_record['Classe di concorso'], 
            key=f"classe_{index}"
        )
        
        new_record['Insegnamento comune'] = st.text_input(
            "Insegnamento comune", 
            value=new_record['Insegnamento comune'], 
            key=f"insegnamento_comune_{index}"
        )
        
        new_record['PeF60 all.1'] = st.text_input(
            "PeF60 all.1", 
            value=new_record['PeF60 all.1'], 
            key=f"pef60_{index}"
        )
        
        new_record['PeF30 all.2'] = st.text_input(
            "PeF30 all.2", 
            value=new_record['PeF30 all.2'], 
            key=f"pef30_all2_{index}"
        )
        
        new_record['PeF36 all.5'] = st.text_input(
            "PeF36 all.5", 
            value=new_record['PeF36 all.5'], 
            key=f"pef36_{index}"
        )
        
    with col2:
        new_record['PeF30 art.13'] = st.text_input(
            "PeF30 art.13", 
            value=new_record['PeF30 art.13'], 
            key=f"pef30_art13_{index}"
        )
        
        new_record['Codice insegnamento'] = st.text_input(
            "Codice insegnamento", 
            value=new_record['Codice insegnamento'], 
            key=f"codice_{index}"
        )
        
        new_record['Denominazione Insegnamento'] = st.text_input(
            "Denominazione Insegnamento", 
            value=new_record['Denominazione Insegnamento'], 
            key=f"denominazione_{index}"
        )
        
        new_record['Docente'] = st.text_input(
            "Docente", 
            value=new_record['Docente'], 
            key=f"docente_{index}"
        )
        
        new_record['Aula'] = st.text_input(
            "Aula", 
            value=new_record['Aula'], 
            key=f"aula_{index}"
        )
        
        new_record['Link Teams'] = st.text_input(
            "Link Teams", 
            value=new_record['Link Teams'], 
            key=f"link_{index}"
        )
        
        new_record['CFU'] = st.text_input(
            "CFU", 
            value=new_record['CFU'], 
            key=f"cfu_{index}"
        )
        
        new_record['Note'] = st.text_area(
            "Note", 
            value=new_record['Note'], 
            key=f"note_{index}"
        )
    
    # Salvataggio delle modifiche
    st.markdown("---")
    
    # Contenitore per i messaggi di stato
    status_container = st.empty()
    
    # Pulsante per salvare le modifiche
    if st.button("Salva modifiche", key=f"save_{index}", type="primary"):
        try:
            # Estrai i componenti dalla data
            giorno, mese, anno = None, None, None
            if pd.notna(new_record['Data']):
                giorno = new_record['Data'].strftime("%A").capitalize()
                mese = new_record['Data'].strftime("%B").capitalize()
                anno = str(new_record['Data'].year)
            
            # Aggiungi i componenti della data
            new_record['Giorno'] = giorno
            new_record['Mese'] = mese
            new_record['Anno'] = anno
            
            # Normalizza il codice insegnamento
            new_record['Codice insegnamento'] = normalize_code(new_record['Codice insegnamento'])
            
            # Converti CFU in numero
            new_record['CFU'] = float(new_record['CFU']) if new_record['CFU'] and new_record['CFU'].strip() else None
            
            # Aggiorna il record nel dataframe
            for col, val in new_record.items():
                if col in df.columns:  # Verifica che la colonna esista nel DataFrame
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
                    status_container.success("✅ Record aggiornato con successo nel database SQLite!")
                else:
                    status_container.warning("⚠️ Aggiornamento SQLite non riuscito, ma i dati sono stati salvati in memoria.")
            except ImportError:
                # Il modulo db_utils non è disponibile
                status_container.info("Modulo db_utils non disponibile, i dati sono stati salvati solo in memoria.")
            except Exception as e:
                # Errore nell'aggiornamento SQLite
                status_container.error(f"Errore nell'aggiornamento SQLite: {str(e)}")
                
            # Salva il DataFrame aggiornato nel file JSON per retrocompatibilità
            try:
                from data_operations import save_data
                save_data(df, replace_file=True)
                st.success("Record aggiornato con successo! Dati salvati correttamente.")
            except Exception as save_err:
                st.warning(f"Il record è stato aggiornato in memoria, ma ci sono stati problemi nel salvataggio completo: {str(save_err)}")
        
        except Exception as e:
            status_container.error(f"Si è verificato un errore durante il salvataggio: {str(e)}")
            st.error(traceback.format_exc())
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
                
        # Non salviamo qui il DataFrame, perché verrà salvato dopo dalla funzione chiamante
        # che ha una vista più globale dei dati
        
        success_msg = "Record aggiornato con successo!"
        if sqlite_success:
            success_msg += " (Salvato in SQLite)"
            
        st.success(success_msg)
    
    return df