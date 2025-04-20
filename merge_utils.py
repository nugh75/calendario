"""
Utility per il merge (unione) di record duplicati nel calendario.
Questo modulo fornisce funzioni per unire record duplicati in un unico record più completo,
combinando le informazioni presenti nei diversi record.
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional, Union
import datetime
from log_utils import logger

def merge_duplicati(duplicati_df: pd.DataFrame, colonne_chiave: List[str] = None) -> Tuple[pd.Series, List[int]]:
    """
    Unisce due o più record duplicati in un unico record, combinando i valori
    dai record originali in modo intelligente.
    
    Args:
        duplicati_df: DataFrame contenente i record duplicati da unire
        colonne_chiave: Lista di colonne da considerare come chiavi identificative 
                     (default: Data, Orario, Docente, Denominazione Insegnamento)
                     
    Returns:
        Tuple[pd.Series, List[int]]: Tuple contenente:
            - il record unito come pd.Series
            - lista degli indici dei record originali (tutti tranne uno che verrà mantenuto)
    """
    if duplicati_df is None or duplicati_df.empty:
        return None, []
    
    # Se abbiamo un solo record, non c'è nulla da unire
    if len(duplicati_df) == 1:
        return duplicati_df.iloc[0], []
    
    # Se non specificate, usa le colonne chiave predefinite
    if colonne_chiave is None:
        colonne_chiave = ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento']
    
    # Crea una copia del DataFrame per non modificare l'originale
    df = duplicati_df.copy()
    
    # Dizionario per contenere i valori uniti
    record_unito = {}
    
    # Colonne per le quali vogliamo tenere il valore non vuoto
    colonne_non_vuote = [
        'Aula', 'Link Teams', 'Note', 'CFU', 'Dipartimento', 
        'Insegnamento comune', 'Codice insegnamento'
    ]
    
    # Colonne per le quali vogliamo mantenere valori numerici più alti
    colonne_max = ['CFU_numeric'] if 'CFU_numeric' in df.columns else []
    
    # Per ogni colonna nel DataFrame
    for colonna in df.columns:
        # Per le colonne chiave, tutti i valori dovrebbero essere identici
        # Usiamo il primo valore non nullo
        if colonna in colonne_chiave:
            values = df[colonna].dropna()
            record_unito[colonna] = values.iloc[0] if not values.empty else None
            continue
        
        # Per le colonne che devono essere non vuote, prendi il primo valore non nullo
        if colonna in colonne_non_vuote:
            # Converti in stringhe, rimuovi valori vuoti e "nan"
            values = df[colonna].astype(str)
            values = values[~values.isin(['nan', 'None', '', 'NaN', 'none'])]
            
            if not values.empty:
                # Se abbiamo più di un valore non vuoto, prendi il più lungo
                if len(values) > 1:
                    record_unito[colonna] = max(values, key=len)
                else:
                    record_unito[colonna] = values.iloc[0]
            else:
                record_unito[colonna] = None
            continue
            
        # Per le colonne numeriche dove vogliamo il massimo, prendi il valore massimo
        if colonna in colonne_max:
            record_unito[colonna] = df[colonna].max()
            continue
            
        # Per tutte le altre colonne, usa il primo valore non nullo
        values = df[colonna].dropna()
        record_unito[colonna] = values.iloc[0] if not values.empty else None
    
    # Crea una Series dal dizionario
    record_merged = pd.Series(record_unito)
    
    # Determina quali record eliminare (tutti tranne il primo)
    indices_to_delete = duplicati_df.index.tolist()[1:]
    
    # Log dell'operazione
    logger.info(f"Uniti {len(duplicati_df)} record duplicati in un unico record")
    
    return record_merged, indices_to_delete

def applica_merge(df: pd.DataFrame, indici_gruppo: List[int], record_unito: pd.Series) -> pd.DataFrame:
    """
    Applica il merge al DataFrame originale, sostituendo i record duplicati con il record unito.
    
    Args:
        df: DataFrame originale
        indici_gruppo: Lista di indici dei record nel gruppo di duplicati
        record_unito: Record risultante dal merge
        
    Returns:
        pd.DataFrame: DataFrame aggiornato con il record unito
    """
    if df is None or df.empty or not indici_gruppo:
        return df
    
    # Crea una copia del DataFrame per non modificare l'originale
    df_result = df.copy()
    
    # Indice del primo record nel gruppo (che verrà sostituito con il record unito)
    primo_indice = indici_gruppo[0]
    
    # Indici dei record da eliminare (tutti tranne il primo)
    indici_da_eliminare = indici_gruppo[1:]
    
    # Sostituzione del primo record con il record unito
    for colonna in record_unito.index:
        if colonna in df_result.columns:
            df_result.at[primo_indice, colonna] = record_unito[colonna]
    
    # Eliminazione degli altri record duplicati
    df_result = df_result.drop(indici_da_eliminare)
    
    # Reset dell'indice
    df_result = df_result.reset_index(drop=True)
    
    return df_result

def scegli_valori_per_merge(df_duplicati: pd.DataFrame) -> Dict[str, Dict[int, Union[str, float, datetime.date]]]:
    """
    Prepara un dizionario con i valori disponibili per ogni campo nei record duplicati,
    da utilizzare in un'interfaccia utente per permettere la selezione manuale.
    
    Args:
        df_duplicati: DataFrame con i record duplicati
        
    Returns:
        Dict: Dizionario strutturato come {campo: {indice_record: valore}}
    """
    if df_duplicati is None or df_duplicati.empty:
        return {}
    
    valori_per_campo = {}
    
    # Per ogni colonna nel DataFrame
    for colonna in df_duplicati.columns:
        valori = {}
        
        # Per ogni record, estrai il valore di questa colonna
        for idx, row in df_duplicati.iterrows():
            val = row[colonna]
            
            # Converti date e timestamp in un formato leggibile
            if isinstance(val, (pd.Timestamp, datetime.date, datetime.datetime)):
                val = val.strftime('%d/%m/%Y') if hasattr(val, 'strftime') else str(val)
            
            # Se il valore è NaN o None, usa una stringa vuota
            if pd.isna(val) or val is None:
                val = ""
            else:
                val = str(val)
            
            # Aggiungi al dizionario
            valori[idx] = val
        
        # Filtra le colonne con valori effettivi (non vuoti o tutti uguali)
        valori_non_vuoti = {k: v for k, v in valori.items() if v.strip()}
        
        # Verifica se abbiamo almeno un valore non vuoto
        if valori_non_vuoti:
            # Verifica se tutti i valori non vuoti sono identici
            valori_unici = set(valori_non_vuoti.values())
            if len(valori_unici) > 1:
                # Se abbiamo valori diversi, includiamo questa colonna
                valori_per_campo[colonna] = valori
    
    return valori_per_campo

def merge_con_selezione(df_duplicati: pd.DataFrame, selezioni: Dict[str, int]) -> pd.Series:
    """
    Crea un record unificato a partire da record duplicati, utilizzando le selezioni
    manuali per ogni campo.
    
    Args:
        df_duplicati: DataFrame contenente i record duplicati
        selezioni: Dizionario con {campo: indice_record} per ogni campo
        
    Returns:
        pd.Series: Record unito con i valori selezionati
    """
    if df_duplicati is None or df_duplicati.empty:
        return None
    
    # Crea un dizionario per il record unito
    record_unito = {}
    
    # Per ogni colonna nel DataFrame
    for colonna in df_duplicati.columns:
        # Se è stata fatta una selezione per questa colonna
        if colonna in selezioni and selezioni[colonna] in df_duplicati.index:
            # Usa il valore selezionato
            record_unito[colonna] = df_duplicati.at[selezioni[colonna], colonna]
        else:
            # Altrimenti prendi il primo valore non nullo
            values = df_duplicati[colonna].dropna()
            record_unito[colonna] = values.iloc[0] if not values.empty else None
    
    # Crea una Series dal dizionario
    return pd.Series(record_unito)
