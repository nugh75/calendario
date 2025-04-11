"""
Pagina di amministrazione per il calendario lezioni.
Permette di visualizzare, aggiungere, modificare ed eliminare i record del calendario.
"""

import streamlit as st
import pandas as pd
from file_utils import load_data, admin_interface

def show_admin_page():
    """Mostra la pagina di amministrazione del calendario"""
    
    st.set_page_config(
        page_title="Amministrazione Calendario Lezioni",
        page_icon="📅",
        layout="wide",
    )
    
    st.title("📅 Amministrazione Calendario Lezioni")
    
    # Verifica credenziali di accesso
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        show_login()
    else:
        show_admin_interface()
    
def show_login():
    """Mostra la schermata di login"""
    
    st.header("Accesso Amministrazione")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Accedi")
        
        if submitted:
            # Per una prima implementazione semplice, usa credenziali codificate
            # In produzione, usare un metodo più sicuro
            if username == "admin" and password == "calendario2024":
                st.session_state.authenticated = True
                st.experimental_rerun()
            else:
                st.error("Credenziali non valide")

def show_admin_interface():
    """Mostra l'interfaccia di amministrazione dopo il login"""
    
    # Pulsante per disconnettersi
    col1, col2 = st.columns([9, 1])
    with col2:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.experimental_rerun()
    
    # Carica i dati
    df = load_data()
    
    if df is not None:
        # Utilizza l'interfaccia di amministrazione centralizzata
        df = admin_interface(df)
    else:
        st.error("Impossibile caricare i dati del calendario")
    
if __name__ == "__main__":
    show_admin_page()
