"""
Utility per la gestione dei link Microsoft Teams.
Questo modulo fornisce funzioni per gestire i link Teams associati agli insegnamenti.
Ora utilizza SQLite per l'archiviazione con fallback al file JSON.
"""

import os
import json
import pandas as pd
import streamlit as st
from typing import Dict, List, Optional, Union
import traceback

# Costanti per i file (mantenuto per retrocompatibilità)
DATA_FOLDER = 'dati'
TEAMS_LINKS_FILE = 'teams_links.json'
TEAMS_LINKS_PATH = os.path.join(DATA_FOLDER, TEAMS_LINKS_FILE)

# Import del sistema di logging
try:
    from log_utils import logger
    log_available = True
except ImportError:
    log_available = False
    
def log_message(message, level="info"):
    """Funzione helper per il logging"""
    if log_available:
        if level == "info":
            logger.info(message)
        elif level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
    else:
        print(f"[{level.upper()}] {message}")

def load_teams_links() -> Dict[str, str]:
    """
    Carica i link Teams dal database SQLite o, come fallback, dal file JSON.
    
    Returns:
        dict: Dizionario con insegnamenti come chiavi e link Teams come valori
    """
    try:
        # Prima tenta di caricare dal database SQLite
        try:
            from db_utils import get_teams_links
            
            # Log del tentativo
            log_message("Tentativo di caricamento link Teams da SQLite...")
            
            # Carica i link da SQLite
            teams_links = get_teams_links()
            
            # Se ha avuto successo e ci sono dati
            if teams_links:
                log_message(f"Caricati {len(teams_links)} link Teams dal database SQLite")
                return teams_links
                
            log_message("Nessun link Teams trovato nel database, tentativo di caricamento da JSON")
            
        except ImportError:
            # Il modulo db_utils non è disponibile
            log_message("Modulo db_utils non disponibile, utilizzo JSON", "warning")
        except Exception as e:
            # Errore nell'accesso al database
            log_message(f"Errore nel caricamento dei link Teams da SQLite: {str(e)}", "error")
            log_message(traceback.format_exc(), "error")
        
        # Fallback: carica dal file JSON
        if not os.path.exists(TEAMS_LINKS_PATH):
            # Crea un file vuoto se non esiste
            os.makedirs(DATA_FOLDER, exist_ok=True)
            with open(TEAMS_LINKS_PATH, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            return {}
            
        with open(TEAMS_LINKS_PATH, 'r', encoding='utf-8') as f:
            teams_links = json.load(f)
            log_message(f"Caricati {len(teams_links)} link Teams dal file JSON")
            return teams_links
    except Exception as e:
        error_msg = f"Errore durante il caricamento dei link Teams: {e}"
        log_message(error_msg, "error")
        st.error(error_msg)
        return {}

def save_teams_links(teams_links: Dict[str, str]) -> bool:
    """
    Salva i link Teams nel database SQLite e, per retrocompatibilità, nel file JSON.
    
    Args:
        teams_links: Dizionario con insegnamenti come chiavi e link Teams come valori
        
    Returns:
        bool: True se il salvataggio è avvenuto con successo, False altrimenti
    """
    try:
        # Prima tenta di salvare nel database SQLite
        sqlite_success = False
        try:
            from db_utils import save_teams_link
            
            # Log del tentativo
            log_message("Tentativo di salvare i link Teams in SQLite...")
            
            # Salva ogni link nel database
            for insegnamento, link in teams_links.items():
                if save_teams_link(insegnamento, link):
                    sqlite_success = True
                else:
                    log_message(f"Fallito salvataggio del link per '{insegnamento}' in SQLite", "warning")
            
            if sqlite_success:
                log_message(f"Link Teams salvati con successo nel database SQLite")
        except ImportError:
            log_message("Modulo db_utils non disponibile, utilizzo solo JSON", "warning")
        except Exception as e:
            log_message(f"Errore nel salvataggio dei link Teams in SQLite: {str(e)}", "error")
            log_message(traceback.format_exc(), "error")
        
        # Indipendentemente dal risultato di SQLite, salva anche nel JSON per retrocompatibilità
        os.makedirs(DATA_FOLDER, exist_ok=True)
        with open(TEAMS_LINKS_PATH, 'w', encoding='utf-8') as f:
            json.dump(teams_links, f, indent=4)
        log_message(f"Link Teams salvati anche nel file JSON")
        
        return True
    except Exception as e:
        error_msg = f"Errore durante il salvataggio dei link Teams: {e}"
        log_message(error_msg, "error")
        st.error(error_msg)
        return False

def add_teams_link(insegnamento: str, link: str) -> bool:
    """
    Aggiunge un nuovo link Teams o aggiorna quello esistente.
    Utilizza prima il database SQLite e poi aggiorna anche il file JSON.
    
    Args:
        insegnamento: Nome dell'insegnamento
        link: Link alla riunione Teams
        
    Returns:
        bool: True se l'operazione è avvenuta con successo, False altrimenti
    """
    try:
        # Prima, tentativo diretto con SQLite
        sqlite_success = False
        try:
            from db_utils import save_teams_link
            
            # Tenta di salvare direttamente nel database
            if save_teams_link(insegnamento, link):
                log_message(f"Link Teams per '{insegnamento}' aggiunto/aggiornato nel database SQLite")
                sqlite_success = True
        except ImportError:
            log_message("Modulo db_utils non disponibile, utilizzo solo JSON", "warning")
        except Exception as e:
            log_message(f"Errore nell'aggiunta del link Teams in SQLite: {str(e)}", "error")
        
        # Indipendentemente dal risultato di SQLite, aggiorna anche il JSON
        teams_links = load_teams_links()
        teams_links[insegnamento] = link
        json_success = save_teams_links(teams_links)
        
        # L'operazione ha successo se almeno uno dei due metodi ha funzionato
        return sqlite_success or json_success
        
    except Exception as e:
        error_msg = f"Errore durante l'aggiunta/aggiornamento del link Teams: {e}"
        log_message(error_msg, "error")
        st.error(error_msg)
        return False

def delete_teams_link(insegnamento: str) -> bool:
    """
    Elimina un link Teams per un insegnamento.
    Elimina sia dal database SQLite che dal file JSON.
    
    Args:
        insegnamento: Nome dell'insegnamento
        
    Returns:
        bool: True se l'operazione è avvenuta con successo, False altrimenti
    """
    try:
        # Prima, tentativo di eliminazione da SQLite
        sqlite_success = False
        try:
            from db_utils import delete_teams_link
            
            # Tenta di eliminare dal database
            if delete_teams_link(insegnamento):
                log_message(f"Link Teams per '{insegnamento}' eliminato dal database SQLite")
                sqlite_success = True
            else:
                log_message(f"Link Teams per '{insegnamento}' non trovato nel database SQLite")
        except ImportError:
            log_message("Modulo db_utils non disponibile, utilizzo solo JSON", "warning")
        except Exception as e:
            log_message(f"Errore nell'eliminazione del link Teams da SQLite: {str(e)}", "error")
        
        # Elimina anche dal file JSON, indipendentemente dal risultato di SQLite
        teams_links = load_teams_links()
        if insegnamento in teams_links:
            del teams_links[insegnamento]
            json_success = save_teams_links(teams_links)
            if json_success:
                log_message(f"Link Teams per '{insegnamento}' eliminato dal file JSON")
            return sqlite_success or json_success
        else:
            log_message(f"Link Teams per '{insegnamento}' non trovato nel file JSON")
            return sqlite_success or True  # Restituisce True anche se non esiste nel JSON
            
    except Exception as e:
        error_msg = f"Errore durante l'eliminazione del link Teams: {e}"
        log_message(error_msg, "error")
        st.error(error_msg)
        return False

def get_teams_link(insegnamento: str) -> Optional[str]:
    """
    Ottiene il link Teams per un insegnamento specifico.
    Prima cerca nel database SQLite, poi nel file JSON.
    
    Args:
        insegnamento: Nome dell'insegnamento
        
    Returns:
        str: Link alla riunione Teams o None se non esiste
    """
    try:
        # Prima tenta di cercare nel database SQLite
        try:
            from db_utils import get_teams_link as get_db_teams_link
            
            # Tenta di recuperare il link dal database
            link = get_db_teams_link(insegnamento)
            if link:
                log_message(f"Link Teams per '{insegnamento}' trovato nel database SQLite")
                return link
        except ImportError:
            log_message("Modulo db_utils non disponibile, utilizzo solo JSON", "warning")
        except Exception as e:
            log_message(f"Errore nel recupero del link Teams da SQLite: {str(e)}", "error")
        
        # Se non trovato in SQLite o c'è stato un errore, cerca nel JSON
        teams_links = load_teams_links()
        link = teams_links.get(insegnamento)
        if link:
            log_message(f"Link Teams per '{insegnamento}' trovato nel file JSON")
        else:
            log_message(f"Nessun link Teams trovato per '{insegnamento}'")
        
        return link
        
    except Exception as e:
        error_msg = f"Errore durante il recupero del link Teams: {e}"
        log_message(error_msg, "error")
        st.error(error_msg)
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
