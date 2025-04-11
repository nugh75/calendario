"""
Applicazione principale per il calendario lezioni.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
from admin_utils import (
    is_admin_logged_in, upload_excel_file,
    save_dataframe_to_csv, create_sample_excel, verify_password
)
from file_utils import (
    load_data as load_data_central, delete_record, edit_record, create_new_record, format_date, setup_locale
)

def main():
    """Funzione principale che gestisce l'applicazione."""
    
    # Configurazione della pagina
    st.set_page_config(
        page_title="Calendario Lezioni",
        page_icon="📅",
        layout="wide"
    )
    
    # Inizializzazione della sessione
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'total_records' not in st.session_state:
        st.session_state.total_records = 0
    
    # Caricamento dei dati
    setup_locale()
    df = load_data_central()
    
    # Layout principale
    st.title("📅 Calendario Lezioni")
    st.write("Percorsi di formazione iniziale dei docenti (DPCM 4 agosto 2023)")
    
    # Mostra il conteggio dei record
    if df is not None and 'total_records' in st.session_state:
        st.info(f"📊 Totale record: {st.session_state.total_records}")
    
    # Interfaccia principale
    if df is not None:
        # Sposta i filtri nella sidebar
        with st.sidebar:
            st.markdown("### 🔍 Filtra il Calendario")
            st.write("Utilizza i filtri sottostanti per visualizzare le lezioni di tuo interesse.")
            
            # Filtro per periodo (mese e anno)
            st.sidebar.subheader("📆 Periodo")
            mesi = sorted(df['Mese'].dropna().unique())
            anni = sorted(df['Anno'].dropna().unique())
            
            mese_selected = st.sidebar.multiselect("Seleziona mese:", mesi)
            anno_selected = st.sidebar.multiselect("Seleziona anno:", anni)
            
            # Filtro per insegnamento
            st.sidebar.subheader("📚 Insegnamento")
            insegnamenti = sorted(df['Denominazione Insegnamento'].dropna().unique())
            insegnamento_selected = st.sidebar.multiselect("Seleziona insegnamento:", insegnamenti)
            
            # Filtro per docente
            st.sidebar.subheader("👩‍🏫 Docente")
            docenti = sorted(df['Docente'].dropna().unique())
            docente_selected = st.sidebar.multiselect("Seleziona docente:", docenti)
            
            # Filtri per percorsi formativi
            st.sidebar.subheader("🎓 Percorsi Formativi")
            pef_cols = ["PeF60 all.1", "PeF30 all.2", "PeF36 all.5", "PeF30 art.13"]
            pef_options = {
                "PeF60 (60 CFU)": "PeF60 all.1",
                "PeF30 all.2 (30 CFU)": "PeF30 all.2",
                "PeF36 all.5 (36 CFU)": "PeF36 all.5",
                "PeF30 art.13 (30 CFU)": "PeF30 art.13"
            }
            percorsi_selected = st.sidebar.multiselect("Seleziona percorso:", list(pef_options.keys()))
        
        # Applica i filtri
        filtered_df = df.copy()
        
        # Filtro per mese
        if mese_selected:
            filtered_df = filtered_df[filtered_df['Mese'].isin(mese_selected)]
        
        # Filtro per anno
        if anno_selected:
            filtered_df = filtered_df[filtered_df['Anno'].isin(anno_selected)]
        
        # Filtro per insegnamento
        if insegnamento_selected:
            filtered_df = filtered_df[filtered_df['Denominazione Insegnamento'].isin(insegnamento_selected)]
        
        # Filtro per docente
        if docente_selected:
            filtered_df = filtered_df[filtered_df['Docente'].isin(docente_selected)]
        
        # Filtro per percorsi formativi
        if percorsi_selected:
            mask = pd.Series(False, index=filtered_df.index)
            for percorso in percorsi_selected:
                col_name = pef_options[percorso]
                mask = mask | (filtered_df[col_name] == 'P') | (filtered_df[col_name] == 'D')
            filtered_df = filtered_df[mask]
        
        # Visualizzazione dei risultati
        st.markdown("### 📋 Risultati della Ricerca")
        st.write(f"Trovati {len(filtered_df)} record.")
        
        if not filtered_df.empty:
            # Converti le date per la visualizzazione
            display_df = filtered_df.copy()
            display_df['Data'] = display_df['Data'].apply(format_date)
            
            # Seleziona colonne da visualizzare
            display_columns = ['Data', 'Orario', 'Denominazione Insegnamento', 'Docente', 'Aula', 'Link Teams']
            st.dataframe(display_df[display_columns], use_container_width=True)
        else:
            st.warning("Nessun risultato trovato con i filtri selezionati.")
    else:
        st.error("Impossibile caricare i dati del calendario. Verifica che il file esista nella cartella 'dati'.")

if __name__ == "__main__":
    main()
