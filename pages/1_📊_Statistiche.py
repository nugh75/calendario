import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys

# Aggiungi la directory principale al path per poter importare i moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_utils import (
    is_admin_logged_in, upload_excel_file, login_admin, logout_admin
)
from excel_utils import create_sample_excel
from file_utils import save_data
from pages_visibility import hide_protected_pages, show_protected_pages
# Importa le funzioni centralizzate dal nuovo modulo file_utils
from file_utils import (
    load_data as load_data_central, delete_record,
    edit_record, create_new_record
)
# Importa la nuova funzione per le statistiche
from nuova_funzione_statistiche_ore import mostra_statistiche_docenti

# Configurazione pagina
st.set_page_config(
    page_title="Statistiche",
    page_icon="📊",
    layout="wide"
)


# Gestione della visibilità delle pagine protette
if is_admin_logged_in():
    show_protected_pages()
else:
    hide_protected_pages()

# Verifica se l'utente è loggato come amministratore
if not is_admin_logged_in():
    st.warning("🔒 Questa pagina è protetta da password")
    
    # Form di login
    with st.form("login_form_stats"):
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Accedi")
        
        if submit_button:
            if login_admin(password):
                st.success("✅ Accesso effettuato con successo!")
                # Aggiorna la visibilità delle pagine
                show_protected_pages()
                st.rerun()
            else:
                st.error("❌ Password errata")
    
    # Interrompi l'esecuzione se l'utente non è loggato
    st.stop()
else:
    # Logout button nella sidebar
    if st.sidebar.button("🚪 Logout"):
        # Prima nascondi le pagine protette
        hide_protected_pages()
        # Poi esegui il logout
        logout_admin()
        st.rerun()

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

# Aggiungiamo il filtro per dipartimento nella sidebar
if df is not None:
    st.sidebar.markdown("## Filtri")
    dipartimenti_list = ["Tutti"] + sorted(df['Dipartimento'].dropna().unique().tolist())
    selected_dipartimento = st.sidebar.selectbox("Dipartimento:", dipartimenti_list)

# Aggiungi pulsante per ricaricare i dati
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 Ricarica dati"):
        st.experimental_memo.clear()
        st.success("🔄 Dati ricaricati!")
        st.rerun()

if df is not None:
    # Manteniamo solo il tab delle statistiche
    st.header("📊 Statistiche")
    
    # Filtriamo il dataframe in base al dipartimento selezionato
    filtered_df = df.copy()
    if selected_dipartimento != "Tutti":
        filtered_df = filtered_df[filtered_df['Dipartimento'] == selected_dipartimento]
        st.info(f"Dati filtrati per il dipartimento: {selected_dipartimento}")
    
    # Aggiungiamo la colonna delle ore (1 CFU = 4h30m, 0.5 CFU = 2h15m)
    # Prima convertiamo i CFU in formato numerico
    filtered_df['CFU_numeric'] = pd.to_numeric(filtered_df['CFU'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    # Calcoliamo le ore: CFU * 4.5 ore
    filtered_df['Ore'] = filtered_df['CFU_numeric'] * 4.5
    
    # Arrotondiamo ai quarti d'ora (0.25h = 15min)
    filtered_df['Ore'] = (filtered_df['Ore'] / 0.25).round() * 0.25
    
    # Formattiamo le ore in modo leggibile (es. "4h 30m")
    def format_ore(ore):
        ore_intere = int(ore)
        minuti = int((ore - ore_intere) * 60)
        return f"{ore_intere}h {minuti:02d}m"
    
    filtered_df['Ore_formattate'] = filtered_df['Ore'].apply(format_ore)
    
    # Richiamiamo la funzione delle statistiche con i dati filtrati e arricchiti
    mostra_statistiche_docenti(filtered_df)

else:
    st.error("Errore nel caricamento dei dati. Controlla che il file CSV sia presente e formattato correttamente.")

# Manteniamo solo il pulsante logout nella sidebar che è già stato aggiunto sopra