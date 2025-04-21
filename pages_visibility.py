"""
Modulo per gestire la visibilità delle pagine in base allo stato di autenticazione.
"""

import os
import streamlit as st
from admin_utils import is_admin_logged_in

# Pagine protette che richiedono autenticazione da amministratore
PROTECTED_PAGES = [
    "1_📊_Statistiche.py",
    "2_🛠️_Gestione.py",
    "3_🔍_Gestione_Duplicati.py",
    "4_📋_Report_Completo.py"
]

def hide_protected_pages():
    """
    Nasconde le pagine protette dalla barra laterale se l'utente non è autenticato.
    Questa funzione deve essere chiamata nella pagina principale e in ogni pagina non protetta.
    """
    # Verifica se l'utente è già autenticato
    if not is_admin_logged_in():
        # Crea una cartella temporanea .hidden se non esiste già
        hidden_dir = os.path.join(os.path.dirname(__file__), ".streamlit", "pages", ".hidden")
        os.makedirs(hidden_dir, exist_ok=True)
        
        # Nasconde le pagine protette spostandole nella cartella nascosta
        pages_dir = os.path.join(os.path.dirname(__file__), "pages")
        
        for page in PROTECTED_PAGES:
            source_path = os.path.join(pages_dir, page)
            dest_path = os.path.join(hidden_dir, page)
            
            # Sposta solo se la pagina protetta esiste nella cartella principale
            if os.path.exists(source_path) and not os.path.exists(dest_path):
                try:
                    os.rename(source_path, dest_path)
                except Exception as e:
                    st.error(f"Errore durante il tentativo di nascondere la pagina {page}: {e}")

def show_protected_pages():
    """
    Ripristina la visibilità delle pagine protette quando l'utente si autentica.
    Questa funzione deve essere chiamata dopo un login avvenuto con successo.
    """
    # Verifica se l'utente è autenticato
    if is_admin_logged_in():
        # Percorsi delle directory
        pages_dir = os.path.join(os.path.dirname(__file__), "pages")
        hidden_dir = os.path.join(os.path.dirname(__file__), ".streamlit", "pages", ".hidden")
        
        # Crea la directory nascosta se non esiste
        os.makedirs(hidden_dir, exist_ok=True)
        
        # Ripristina le pagine protette
        for page in PROTECTED_PAGES:
            source_path = os.path.join(hidden_dir, page)
            dest_path = os.path.join(pages_dir, page)
            
            # Ripristina solo se la pagina esiste nella cartella nascosta
            if os.path.exists(source_path) and not os.path.exists(dest_path):
                try:
                    os.rename(source_path, dest_path)
                except Exception as e:
                    st.error(f"Errore durante il tentativo di mostrare la pagina {page}: {e}")
