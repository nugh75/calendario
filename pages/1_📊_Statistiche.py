import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys

# Aggiungi la directory principale al path per poter importare i moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_utils import (
    is_admin_logged_in, upload_excel_file, save_dataframe_to_csv,
    create_sample_excel
)
# Importa le funzioni centralizzate dal nuovo modulo file_utils
from file_utils import (
    load_data as load_data_central, delete_record,
    edit_record, create_new_record
)
# Importa la nuova funzione per le statistiche
from nuova_funzione_statistiche import mostra_statistiche_docenti

# Configurazione pagina
st.set_page_config(
    page_title="Statistiche",
    page_icon="📊",
    layout="wide"
)

# Titolo della pagina con icona
st.title("📊 Statistiche")

# Verifica se l'utente è loggato come amministratore
from admin_utils import login_admin, logout_admin

if not is_admin_logged_in():
    st.warning("🔒 Questa pagina è protetta da password")
    
    # Form di login
    with st.form("login_form_stats"):
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Accedi")
        
        if submit_button:
            if login_admin(password):
                st.success("✅ Accesso effettuato con successo!")
                st.experimental_rerun()
            else:
                st.error("❌ Password errata")
    
    # Interrompi l'esecuzione se l'utente non è loggato
    st.stop()
else:
    # Logout button
    if st.sidebar.button("🚪 Logout"):
        logout_admin()
        st.experimental_rerun()

# Funzione locale che chiama la versione centralizzata
def load_data():
    # Usa la funzione centralizzata da file_utils.py
    df = load_data_central()
    
    # Aggiungi informazioni di debug sul numero di record caricati
    if df is not None:
        st.session_state['admin_page_records'] = len(df)
        st.session_state['admin_data_loading_time'] = datetime.now().strftime("%H:%M:%S")
        
    return df

# Carica i dati
df = load_data()

# Aggiungi box informativo per mostrare il numero di record caricati
if df is not None:
    st.sidebar.info(f"Record caricati: {len(df)} - [{datetime.now().strftime('%H:%M:%S')}]")

# Aggiungi pulsante per ricaricare i dati
if st.button("🔄 Ricarica dati"):
    st.experimental_memo.clear()
    st.success("🔄 Dati ricaricati!")
    st.rerun()

if df is not None:
    # Manteniamo solo il tab delle statistiche
    st.header("📊 Statistiche")
    
    # Richiamiamo direttamente la funzione delle statistiche
    mostra_statistiche_docenti(df)
    
    if df is None:
        st.info("Nessuna statistica disponibile sui docenti")

else:
    st.error("Errore nel caricamento dei dati. Controlla che il file CSV sia presente e formattato correttamente.")

# Aggiungi solo il pulsante logout nella sidebar
st.sidebar.markdown("---")
if is_admin_logged_in():
    if st.sidebar.button("📤 Logout"):
        # Esegui il logout usando la funzione centralizzata
        from admin_utils import logout_admin
        logout_admin()
        st.rerun()
