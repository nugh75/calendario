# filepath: /mnt/git/calendario/pages/4_📋_Report_Completo.py
"""
Pagina Streamlit per la generazione e visualizzazione di report completi sul calendario.
Questo report integra tutte le analisi: duplicati, CFU, completezza dei dati.
"""

import streamlit as st
import pandas as pd
import os
import sys
from pathlib import Path

# Aggiungi la directory principale al path per l'importazione dei moduli
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Importa le utility per i report e altre funzioni necessarie
from report_utils import visualizza_report_completo
from file_utils import load_data
from log_utils import logger
from admin_utils import is_admin_logged_in, login_admin, logout_admin

st.set_page_config(
    page_title="Report Completo Calendario",
    page_icon="📋",
    layout="wide"
)

def main():
    """
    Funzione principale per la generazione di report completi sul calendario.
    """
    st.title("📋 Report Completo Calendario")
    
    # Verifica se l'utente è loggato come amministratore
    if not is_admin_logged_in():
        st.warning("🔒 Questa pagina è protetta da password")
        
        # Form di login
        with st.form("login_form_report"):
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
    
    # Sidebar
    with st.sidebar:
        st.header("Informazioni")
        st.info(
            "Questa pagina consente di generare report completi sul calendario, "
            "integrando analisi dei duplicati, CFU e completezza dati."
        )
        
        # Aggiungi una descrizione delle funzionalità
        st.markdown("""
        ### Funzionalità:
        
        - **Report integrato**: Genera un report che combina tutte le analisi in un unico documento.
        - **Metriche complete**: Visualizza statistiche e metriche su duplicati, CFU e completezza.
        - **Raccomandazioni**: Riceve consigli specifici per migliorare la qualità dei dati.
        - **Salvataggio report**: Salva o scarica il report per consultazioni future.
        """)
        
        # Aggiungi una sezione sulle interpretazioni dei risultati
        with st.expander("Come interpretare i risultati"):
            st.markdown("""
            ### Interpretazione dei risultati:
            
            1. **Duplicati**:
               - I duplicati standard sono record con stessa data, docente e orario
               - I duplicati avanzati sono record simili con piccole differenze
               
            2. **Analisi CFU**:
               - Classi con CFU in eccesso: potrebbero contenere duplicati
               - Classi con CFU in difetto: potrebbero mancare lezioni
               - Le classi trasversali hanno un target di 24 CFU anziché 16
               
            3. **Completezza**:
               - Percentuale > 90%: Ottima
               - Percentuale 80-90%: Buona
               - Percentuale 70-80%: Mediocre
               - Percentuale < 70%: Insufficiente
            """)
    
    # Carica i dati del calendario
    df = None
    try:
        df = load_data()
        if df is None or df.empty:
            st.error("Impossibile caricare i dati del calendario. Verifica che il file esista e sia valido.")
            return
        
        # Memorizza il dataframe nella sessione per poterlo riutilizzare
        st.session_state["calendario_df"] = df
        
    except Exception as e:
        st.error(f"Errore durante il caricamento dei dati: {e}")
        logger.error(f"Errore durante il caricamento dei dati: {e}")
        return
    
    if df is not None:
        # Mostra informazioni generali sul dataset
        st.subheader("Informazioni Generali")
        st.write(f"Record totali nel calendario: {len(df)}")
        
        if 'Dipartimento' in df.columns:
            dipartimenti = df['Dipartimento'].dropna().unique()
            st.write(f"Dipartimenti: {len(dipartimenti)}")
            
        if 'Insegnamento comune' in df.columns:
            classi = df['Insegnamento comune'].unique()
            st.write(f"Classi di concorso: {len(classi)}")
        
        # Linea di separazione
        st.markdown("---")
        
        # Utilizza la funzione di visualizzazione del report completo
        visualizza_report_completo(df)
    
    # Aggiungi una nota alla fine
    st.markdown("---")
    st.caption("I report generati rappresentano un'istantanea dei dati al momento della generazione.")

if __name__ == "__main__":
    main()
