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
            
            # Filtro per periodo (mese e intervallo di date)
            st.sidebar.subheader("📆 Periodo")
            mesi = sorted(df['Mese'].dropna().unique())
            
            # Filtro per mese
            mese_selected = st.sidebar.multiselect("Seleziona mese:", mesi)
            
            # Filtro per intervallo di date
            st.sidebar.write("Oppure seleziona un intervallo di date:")
            
            # Determina le date minime e massime nel dataset
            min_date = df['Data'].min().date() if not df['Data'].empty else datetime.now().date()
            max_date = df['Data'].max().date() if not df['Data'].empty else datetime.now().date()
            
            # Filtro per intervallo di date
            date_start = st.sidebar.date_input(
                "Data inizio:",
                value=min_date,
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY"
            )
            
            date_end = st.sidebar.date_input(
                "Data fine:",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY"
            )
            
            # Checkbox per attivare il filtro per data
            use_date_range = st.sidebar.checkbox("Filtra per intervallo di date")
            
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
        
        # Filtro per intervallo di date (se attivato)
        if use_date_range:
            # Converti date_start e date_end in oggetti Timestamp per confrontarli con df['Data']
            date_start_ts = pd.Timestamp(date_start)
            date_end_ts = pd.Timestamp(date_end)
            
            # Applica il filtro per intervallo di date
            filtered_df = filtered_df[(filtered_df['Data'] >= date_start_ts) & 
                                     (filtered_df['Data'] <= date_end_ts)]
        
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
            
            # Colonne base che saranno sempre visualizzate
            base_cols = ['Data', 'Orario', 'Dipartimento', 'Classe di concorso', 'Insegnamento comune', 
                      'Codice insegnamento', 'Denominazione Insegnamento', 'Docente', 'Aula', 
                      'Link Teams', 'CFU', 'Note']
            
            # Colonne dei percorsi formativi
            pef_cols_map = {
                "PeF60 (60 CFU)": "PeF60 all.1",
                "PeF30 all.2 (30 CFU)": "PeF30 all.2", 
                "PeF36 all.5 (36 CFU)": "PeF36 all.5",
                "PeF30 art.13 (30 CFU)": "PeF30 art.13"
            }
            
            # Seleziona colonne da visualizzare in base ai percorsi selezionati
            view_cols = base_cols.copy()
            
            # Se nessun percorso è selezionato, mostra tutte le colonne dei percorsi
            if not percorsi_selected:
                view_cols = base_cols[:5] + list(pef_cols_map.values()) + base_cols[5:]
            else:
                # Aggiungi solo le colonne dei percorsi selezionati
                percorsi_cols = [pef_cols_map[percorso] for percorso in percorsi_selected]
                
                # Inserisci le colonne dei percorsi nella posizione corretta (dopo 'Insegnamento comune')
                view_cols = base_cols[:5] + percorsi_cols + base_cols[5:]
            
            st.dataframe(display_df[view_cols], use_container_width=True, height=400)
        else:
            st.warning("Nessun risultato trovato con i filtri selezionati.")
    else:
        st.error("Impossibile caricare i dati del calendario. Verifica che il file esista nella cartella 'dati'.")

if __name__ == "__main__":
    main()
