"""
Utility per la gestione delle date del calendario lezioni.
Questo modulo centralizza tutte le operazioni di formattazione e manipolazione delle date.
"""

import pandas as pd
import locale
import datetime
import streamlit as st
from typing import Optional, Tuple

def setup_locale() -> bool:
    """
    Imposta la localizzazione italiana per le date.
    
    Returns:
        bool: True se la localizzazione è stata impostata correttamente, False altrimenti
    """
    # Lista di possibili localizzazioni italiane in ordine di preferenza
    italian_locales = ['it_IT.UTF-8', 'it_IT.utf8', 'it_IT', 'it', 'Italian_Italy']
    
    # Salva la localizzazione corrente per poterla ripristinare in caso di errore
    current_locale = locale.getlocale(locale.LC_TIME)
    
    for loc in italian_locales:
        try:
            locale.setlocale(locale.LC_TIME, loc)
            return True
        except locale.Error:
            continue
    
    try:
        # Fallback: usa la localizzazione di default del sistema
        locale.setlocale(locale.LC_TIME, '')
        # Log dell'avviso
        from log_utils import logger
        logger.warning("Impossibile impostare la localizzazione italiana. Usata localizzazione di default.")
        return False
    except:
        # Ripristina la localizzazione originale se tutte le altre opzioni falliscono
        try:
            locale.setlocale(locale.LC_TIME, current_locale)
        except:
            pass
        return False

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
    
    # Definizione dei nomi dei mesi italiani per la traduzione manuale se necessario
    italian_months = {
        1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 
        6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 
        10: "ottobre", 11: "novembre", 12: "dicembre"
    }
    
    # Definizione dei nomi dei giorni italiani per la traduzione manuale
    italian_days = {
        0: "lunedì", 1: "martedì", 2: "mercoledì", 3: "giovedì",
        4: "venerdì", 5: "sabato", 6: "domenica"
    }
    
    try:
        # 1. Se è un oggetto datetime, procedi direttamente con la formattazione
        if isinstance(date_obj_or_str, (pd.Timestamp, datetime.datetime)):
            date_obj = date_obj_or_str
        else:
            # 2. Se è una stringa, tenta di convertirla in datetime
            try:
                date_obj = pd.to_datetime(date_obj_or_str, errors='raise')
            except:
                # 3. Se la stringa è già in formato italiano, restituiscila normalizzata
                if isinstance(date_obj_or_str, str):
                    date_str_lower = date_obj_or_str.lower()
                    if any(month in date_str_lower for month in italian_months.values()):
                        return date_str_lower
                return None
        
        # Tenta la formattazione standard con localizzazione italiana
        try:
            # Verifica che la localizzazione italiana sia attiva
            locale_test = datetime.datetime(2025, 1, 1).strftime("%B")
            if locale_test.lower() in ["january", "jan", "gennaio", "gen"]:
                # Localizzazione funzionante, usa strftime
                return date_obj.strftime("%A %d %B %Y").lower()
            else:
                # Fallback: formattazione manuale
                raise Exception("Localizzazione non disponibile")
        except:
            # Fallback con traduzione manuale
            day_name = italian_days.get(date_obj.weekday(), "")
            month_name = italian_months.get(date_obj.month, "")
            if day_name and month_name:
                return f"{day_name} {date_obj.day:02d} {month_name} {date_obj.year}"
            else:
                # Ultimo fallback: formato internazionale
                return date_obj.strftime("%d/%m/%Y")
            
    except Exception as e:
        # Log dell'errore
        try:
            from log_utils import logger
            logger.error(f"Errore nella formattazione data: {e}")
        except:
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
