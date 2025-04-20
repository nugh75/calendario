"""
Pagina di riepilogo CFU per classi di concorso e percorsi formativi.
Questa pagina mostra statistiche dettagliate sui CFU erogati per ciascuna classe di concorso
e per i diversi percorsi formativi (PeF60, PeF30, ecc.).
"""

import streamlit as st
import pandas as pd
import os
import sys

# Aggiungi la directory principale al path per poter importare i moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importa le funzioni necessarie
from admin_utils import is_admin_logged_in, login_admin, logout_admin
from file_utils import load_data

# Importazione diretta del modulo cfu_riepilogo_utils
try:
    from cfu_riepilogo_utils import mostra_riepilogo_cfu, esporta_riepilogo_excel, mostra_riepilogo_cfu_per_area
except ImportError:
    # Fallback: importa il modulo a runtime con importlib
    import importlib.util
    module_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cfu_riepilogo_utils.py")
    spec = importlib.util.spec_from_file_location("cfu_riepilogo_utils", module_path)
    cfu_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfu_module)
    mostra_riepilogo_cfu = cfu_module.mostra_riepilogo_cfu
    esporta_riepilogo_excel = cfu_module.esporta_riepilogo_excel
    mostra_riepilogo_cfu_per_area = cfu_module.mostra_riepilogo_cfu_per_area

# Configurazione pagina
st.set_page_config(
    page_title="Riepilogo CFU",
    page_icon="📊",
    layout="wide"
)

# Titolo della pagina
st.title("📊 Riepilogo CFU per Classi di Concorso e Percorsi")

# Verifica se l'utente è loggato come amministratore
if not is_admin_logged_in():
    st.warning("🔒 Questa pagina è protetta da password")
    
    # Form di login
    with st.form("login_form_riepilogo"):
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Accedi")
        
        if submit_button:
            if login_admin(password):
                st.success("✅ Accesso effettuato con successo!")
                st.rerun()
            else:
                st.error("❌ Password errata")
    
    # Interrompi l'esecuzione se l'utente non è loggato
    st.info("Questa sezione è riservata agli amministratori.")
    st.stop()
else:
    # Logout button nella sidebar
    if st.sidebar.button("🚪 Logout"):
        logout_admin()
        st.rerun()

# Carica i dati
df = load_data()

if df is None or df.empty:
    st.error("Non è stato possibile caricare i dati.")
    st.stop()

# Filtraggio opzionale
st.sidebar.header("Filtri")

# Filtraggio per data
st.sidebar.subheader("Filtro per data")
date_min = df["Data"].min() if not df.empty else None
date_max = df["Data"].max() if not df.empty else None

if date_min is not None and date_max is not None:
    date_range = st.sidebar.date_input(
        "Intervallo di date",
        [date_min, date_max],
        min_value=date_min,
        max_value=date_max
    )
    
    # Applica il filtro se l'utente ha selezionato un intervallo
    if len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df["Data"] >= pd.Timestamp(start_date)) & (df["Data"] <= pd.Timestamp(end_date))
        filtered_df = df[mask]
    else:
        filtered_df = df.copy()
else:
    filtered_df = df.copy()

# Pulsante per esportare il riepilogo in Excel
st.sidebar.subheader("Esportazione")
if st.sidebar.button("📥 Esporta Riepilogo Excel"):
    with st.spinner("Esportazione in corso..."):
        excel_path = esporta_riepilogo_excel(filtered_df)
        if excel_path:
            # Apri il file per il download
            with open(excel_path, "rb") as file:
                st.sidebar.download_button(
                    label="⬇️ Download Riepilogo Excel",
                    data=file,
                    file_name="riepilogo_cfu.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            st.sidebar.success("✅ Riepilogo esportato con successo!")
        else:
            st.sidebar.error("❌ Si è verificato un errore durante l'esportazione.")

# Crea tabs per le diverse modalità di visualizzazione del riepilogo
tab1, tab2 = st.tabs(["📊 Per Classe di Concorso", "🔍 Per Area Formativa"])

# Tab 1: Riepilogo per Classe di Concorso (visualizzazione originale)
with tab1:
    # Mostra il riepilogo usando la funzione centralizzata
    mostra_riepilogo_cfu(filtered_df)

# Tab 2: Riepilogo per Area Formativa (nuova visualizzazione)
with tab2:
    st.markdown("### Analisi CFU per Aree Formative (DPCM 4 agosto 2023)")
    
    # Nota importante sul filtraggio per classe di concorso
    st.info("""
    ℹ️ **Importante:** L'analisi CFU è più significativa quando filtrata per una specifica classe di concorso.
    
    Nell'interfaccia di selezione qui sotto potrai scegliere una classe di concorso specifica per visualizzare:
    - I CFU disciplinari specifici per quella classe
    - I CFU delle aree trasversali associate (che vengono automaticamente inclusi)
    - L'analisi di conformità rispetto ai requisiti del DPCM per ogni percorso
    """)
    
    st.markdown("""
    Questa analisi verifica la conformità dei CFU erogati rispetto ai requisiti del DPCM 4 agosto 2023, 
    che definisce le seguenti aree formative:
    - **Disciplinare**: Didattiche delle discipline e metodologie delle discipline di riferimento
    - **Trasversale**: Area trasversale, comuni a tutte le classi di concorso
    - **Tirocinio Diretto**: Tirocinio da svolgersi presso le istituzioni scolastiche
    - **Tirocinio Indiretto**: Tirocinio da svolgersi presso l'Università
    """)
    
    # Mostra il riepilogo per area formativa
    mostra_riepilogo_cfu_per_area(filtered_df)

# Aggiungi riferimento alla dashboard nella parte inferiore
st.sidebar.markdown("---")
if st.sidebar.button("↩️ Torna alla Dashboard"):
    st.switch_page("📅_Calendario.py")
