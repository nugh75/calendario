import pandas as pd
import streamlit as st
import os
import traceback


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
    
    # Importa save_data qui per evitare l'importazione circolare
    from data_operations import save_data
    
    # Salva il DataFrame aggiornato con sovrascrittura completa del file
    # (la funzione save_data si occuperà anche del salvataggio in SQLite)
    save_data(df, replace_file=True)
    
    # Conferma
    st.success("Record eliminato con successo!")
    
    return df