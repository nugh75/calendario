"""
Utility per la gestione dei link Microsoft Teams.
Questo modulo fornisce funzioni per gestire i link Teams associati agli insegnamenti.
"""

import os
import json
import pandas as pd
import streamlit as st
from typing import Dict, List, Optional, Union

# Costanti per i file
DATA_FOLDER = 'dati'
TEAMS_LINKS_FILE = 'teams_links.json'
TEAMS_LINKS_PATH = os.path.join(DATA_FOLDER, TEAMS_LINKS_FILE)

def load_teams_links() -> Dict[str, str]:
    """
    Carica i link Teams dal file JSON.
    
    Returns:
        dict: Dizionario con insegnamenti come chiavi e link Teams come valori
    """
    try:
        if not os.path.exists(TEAMS_LINKS_PATH):
            # Crea un file vuoto se non esiste
            os.makedirs(DATA_FOLDER, exist_ok=True)
            with open(TEAMS_LINKS_PATH, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            return {}
            
        with open(TEAMS_LINKS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Errore durante il caricamento dei link Teams: {e}")
        return {}

def save_teams_links(teams_links: Dict[str, str]) -> bool:
    """
    Salva i link Teams nel file JSON.
    
    Args:
        teams_links: Dizionario con insegnamenti come chiavi e link Teams come valori
        
    Returns:
        bool: True se il salvataggio è avvenuto con successo, False altrimenti
    """
    try:
        os.makedirs(DATA_FOLDER, exist_ok=True)
        with open(TEAMS_LINKS_PATH, 'w', encoding='utf-8') as f:
            json.dump(teams_links, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Errore durante il salvataggio dei link Teams: {e}")
        return False

def add_teams_link(insegnamento: str, link: str) -> bool:
    """
    Aggiunge un nuovo link Teams o aggiorna quello esistente.
    
    Args:
        insegnamento: Nome dell'insegnamento
        link: Link alla riunione Teams
        
    Returns:
        bool: True se l'operazione è avvenuta con successo, False altrimenti
    """
    try:
        teams_links = load_teams_links()
        teams_links[insegnamento] = link
        return save_teams_links(teams_links)
    except Exception as e:
        st.error(f"Errore durante l'aggiunta/aggiornamento del link Teams: {e}")
        return False

def delete_teams_link(insegnamento: str) -> bool:
    """
    Elimina un link Teams per un insegnamento.
    
    Args:
        insegnamento: Nome dell'insegnamento
        
    Returns:
        bool: True se l'operazione è avvenuta con successo, False altrimenti
    """
    try:
        teams_links = load_teams_links()
        if insegnamento in teams_links:
            del teams_links[insegnamento]
            return save_teams_links(teams_links)
        return True  # Restituisce True anche se l'insegnamento non esiste
    except Exception as e:
        st.error(f"Errore durante l'eliminazione del link Teams: {e}")
        return False

def get_teams_link(insegnamento: str) -> Optional[str]:
    """
    Ottiene il link Teams per un insegnamento specifico.
    
    Args:
        insegnamento: Nome dell'insegnamento
        
    Returns:
        str: Link alla riunione Teams o None se non esiste
    """
    try:
        teams_links = load_teams_links()
        return teams_links.get(insegnamento)
    except Exception as e:
        st.error(f"Errore durante il recupero del link Teams: {e}")
        return None

def apply_teams_links_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applica i link Teams al dataframe del calendario.
    
    Args:
        df: DataFrame del calendario
        
    Returns:
        pd.DataFrame: DataFrame con i link Teams aggiornati
    """
    try:
        # Creiamo una copia per non modificare l'originale
        result_df = df.copy()
        
        # Carica i link Teams
        teams_links = load_teams_links()
        
        # Aggiungi una colonna per i link cliccabili (verrà utilizzata solo per la visualizzazione)
        result_df['Teams_Link_Clickable'] = None
        
        # Per ogni insegnamento comune nel DataFrame
        for index, row in result_df.iterrows():
            insegnamento = row.get('Insegnamento comune', '')
            
            # Se l'insegnamento ha un link Teams personalizzato, usalo
            if insegnamento in teams_links and teams_links[insegnamento]:
                # Conserva il link originale nella colonna Link Teams
                result_df.at[index, 'Link Teams'] = teams_links[insegnamento]
                
                # Crea il link cliccabile nella nuova colonna
                result_df.at[index, 'Teams_Link_Clickable'] = f'<a href="{teams_links[insegnamento]}" target="_blank">Teams</a>'
            elif pd.notna(row.get('Link Teams')) and row.get('Link Teams'):
                # Se già esiste un link Teams nella riga, crea un link cliccabile per esso
                result_df.at[index, 'Teams_Link_Clickable'] = f'<a href="{row["Link Teams"]}" target="_blank">Teams</a>'
        
        return result_df
    except Exception as e:
        st.error(f"Errore durante l'applicazione dei link Teams: {e}")
        return df  # Restituisci il dataframe originale in caso di errore
