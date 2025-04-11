import pandas as pd
import streamlit as st
import os
import bcrypt
from typing import List, Dict, Any, Union

# Importa le utility centralizzate per la gestione dei file
from file_utils import (
    load_data, save_data, delete_record, process_excel_upload,
    create_sample_excel as create_sample_excel_central,
    DEFAULT_CSV_PATH, DATA_FOLDER
)

# Costanti
# Password hardcoded per semplificare l'autenticazione
ADMIN_PASSWORD = "2025pef"

def verify_password(password: str) -> bool:
    """Verifica la password dell'amministratore."""
    return password == ADMIN_PASSWORD

def login_admin(password):
    """Verifica le credenziali e imposta lo stato di autenticazione."""
    if verify_password(password):
        st.session_state.authenticated = True
        st.session_state.admin_logged_in = True
        return True
    return False

def logout_admin():
    """Disconnette l'amministratore."""
    st.session_state.authenticated = False
    st.session_state.admin_logged_in = False
    return True

def is_admin_logged_in():
    """Verifica se l'amministratore è autenticato."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = st.session_state.authenticated
    return st.session_state.authenticated

def upload_excel_file(uploaded_file=None):
    """
    Processa un file Excel caricato.
    
    Args:
        uploaded_file: File Excel caricato tramite st.file_uploader
    
    Returns:
        DataFrame: Il dataframe caricato dal file Excel, o None in caso di errore
    """
    if uploaded_file is None:
        uploaded_file = st.file_uploader("Carica il file Excel", type=["xlsx", "xls"])
        if uploaded_file is None:
            return None
    
    try:
        df = process_excel_upload(uploaded_file)
        if df is not None and not df.empty:
            return df
        return None
    except Exception as e:
        st.error(f"Errore durante il caricamento del file: {e}")
        return None

def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida i dati importati e rimuove righe non valide.
    """
    # Rimuovi righe con valori mancanti nelle colonne essenziali
    df = df.dropna(subset=['Data', 'Orario', 'Dipartimento', 'Docente'])
    
    # Rimuovi righe con date non valide
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    df = df.dropna(subset=['Data'])
    
    return df

def save_dataframe_to_csv(df: pd.DataFrame, path: str = 'dati') -> str:
    """
    Funzione wrapper che chiama la funzione centralizzata save_data.
    """
    # Utilizza la funzione centralizzata di salvataggio
    return save_data(df)

def create_sample_excel():
    """
    Wrapper per la funzione centralizzata create_sample_excel.
    
    Returns:
        str: Percorso del file Excel creato
    """
    return create_sample_excel_central()
