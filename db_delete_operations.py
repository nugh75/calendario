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


def delete_filtered_records(original_df: pd.DataFrame, filtered_df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina tutti i record filtrati dal DataFrame e dal database.
    
    Args:
        original_df: DataFrame originale completo
        filtered_df: DataFrame contenente solo i record filtrati da eliminare
        
    Returns:
        pd.DataFrame: DataFrame aggiornato senza i record eliminati
    """
    if filtered_df.empty:
        st.warning("Nessun record da eliminare con i filtri correnti.")
        return original_df

    try:
        # Creazione logger se disponibile
        try:
            from log_utils import logger
        except ImportError:
            logger = None
            
        # Numero di record da eliminare
        num_records = len(filtered_df)

        # Crea un indice per i record da eliminare
        indices_to_delete = []
        
        # Per ogni record nel DataFrame filtrato, trova il corrispondente indice nel DataFrame originale
        for _, filtered_row in filtered_df.iterrows():
            # Crea una maschera per identificare questo record nel DataFrame originale
            # Utilizziamo colonne chiave che dovrebbero essere uniche quando combinate
            mask = (original_df['Data'] == filtered_row['Data']) & \
                   (original_df['Orario'] == filtered_row['Orario']) & \
                   (original_df['Docente'] == filtered_row['Docente']) & \
                   (original_df['Denominazione Insegnamento'] == filtered_row['Denominazione Insegnamento'])
            
            # Ottieni gli indici dei record corrispondenti
            matching_indices = original_df[mask].index.tolist()
            
            # Aggiungi questi indici alla lista dei record da eliminare
            indices_to_delete.extend(matching_indices)

        # Elimina i record da SQLite se possibile
        try:
            from db_utils import delete_record as delete_sql_record
            
            sqlite_success_count = 0
            for idx in indices_to_delete:
                record_data = original_df.iloc[idx].to_dict()
                if delete_sql_record(record_data):
                    sqlite_success_count += 1
                    
            if logger:
                logger.info(f"Eliminati {sqlite_success_count}/{num_records} record dal database SQLite")
                
        except ImportError:
            if logger:
                logger.warning("Modulo db_utils non disponibile, eliminazione solo dal JSON")
        except Exception as e:
            if logger:
                logger.error(f"Errore nell'eliminazione multipla dei record da SQLite: {str(e)}")
                logger.error(traceback.format_exc())

        # Elimina i record dal DataFrame originale
        updated_df = original_df.drop(indices_to_delete).reset_index(drop=True)
        
        # Salva il DataFrame aggiornato
        from data_operations import save_data
        save_data(updated_df, replace_file=True)
        
        # Conferma
        st.success(f"✅ {num_records} record eliminati con successo!")
        
        return updated_df
        
    except Exception as e:
        error_msg = f"Si è verificato un errore durante l'eliminazione multipla: {str(e)}"
        if 'logger' in locals() and logger:
            logger.error(error_msg)
            logger.error(traceback.format_exc())
        st.error(error_msg)
        return original_df