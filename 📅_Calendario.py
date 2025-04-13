"""
Applicazione principale per il calendario lezioni.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
from admin_utils import (
    is_admin_logged_in, upload_excel_file,
    save_dataframe_to_csv, verify_password
)
from file_utils import (
    load_data as load_data_central, format_date, setup_locale
)
from excel_utils import create_sample_excel
from data_utils import create_new_record, edit_record 
from file_utils import delete_record
from teams_utils import apply_teams_links_to_dataframe

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
    
    # Interfaccia principale
    if df is not None:
        # Sposta i filtri nella sidebar
        with st.sidebar:
            st.markdown("### 🔍 Filtra il Calendario")
            st.write("Utilizza i filtri sottostanti per visualizzare le lezioni di tuo interesse.")
            
            # Campo di ricerca testuale (prima di tutti gli altri filtri)
            search_term = st.sidebar.text_input("Cerca nei record", 
                                 placeholder="Docente, insegnamento, data...",
                                 key="calendar_search")
            
            # Selettore delle colonne da visualizzare (subito dopo la ricerca)
            st.sidebar.subheader("👁️ Visualizzazione Colonne")
            
            # Definisci tutte le colonne disponibili con etichette user-friendly
            available_columns = {
                'Data': 'Data',
                'Orario': 'Orario',
                'Dipartimento': 'Dipartimento',
                'Classe di concorso': 'Classe di concorso', 
                'Insegnamento comune': 'Insegnamento comune',
                'Codice insegnamento': 'Codice insegnamento',
                'Denominazione Insegnamento': 'Denominazione Insegnamento',
                'Docente': 'Docente',
                'Aula': 'Aula',
                'Link Teams': 'Link Teams', 
                'CFU': 'CFU',
                'Note': 'Note'
            }
            
            # Aggiungi anche le colonne dei percorsi formativi
            pef_options = {
                "PeF60 (60 CFU)": "PeF60 all.1",
                "PeF30 all.2 (30 CFU)": "PeF30 all.2",
                "PeF36 all.5 (36 CFU)": "PeF36 all.5",
                "PeF30 art.13 (30 CFU)": "PeF30 art.13"
            }
            for label, col in pef_options.items():
                available_columns[col] = label
            
            # Colonne predefinite (obbligatorie)
            default_columns = ['Data', 'Orario', 'Denominazione Insegnamento', 'Docente', 'Aula']
            
            # Selezione delle colonne da visualizzare
            if 'selected_columns' not in st.session_state:
                st.session_state.selected_columns = default_columns
                
            columns_to_display = st.sidebar.multiselect(
                "Seleziona le colonne da visualizzare:",
                options=list(available_columns.keys()),
                default=st.session_state.selected_columns,
                format_func=lambda x: available_columns[x]
            )
            
            # Assicurati che ci siano sempre alcune colonne minime selezionate
            if not columns_to_display:
                columns_to_display = default_columns
                st.sidebar.warning("Seleziona almeno una colonna. Sono state ripristinate le colonne predefinite.")
            
            # Aggiorna lo stato della sessione
            st.session_state.selected_columns = columns_to_display
            
            st.sidebar.markdown("---")
            
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
            
            # Filtro per classe di concorso
            st.sidebar.subheader("🎯 Classe di Concorso")
            classi_concorso = sorted(df['Classe di concorso'].dropna().unique())
            classe_concorso_selected = st.sidebar.multiselect("Seleziona classe di concorso:", classi_concorso)
            
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
            
            # Assicurati che ci siano sempre alcune colonne minime selezionate
            if not columns_to_display:
                columns_to_display = default_columns
                st.sidebar.warning("Seleziona almeno una colonna. Sono state ripristinate le colonne predefinite.")
            
            # Aggiorna lo stato della sessione
            st.session_state.selected_columns = columns_to_display
        
        # Applica i filtri
        filtered_df = df.copy()
        
        # Applica il filtro di ricerca testuale (se presente)
        if search_term:
            # Cerca in tutte le colonne di stringhe
            mask = pd.Series(False, index=filtered_df.index)
            for col in filtered_df.columns:
                if filtered_df[col].dtype == 'object':  # Solo colonne di tipo object (stringhe)
                    mask = mask | filtered_df[col].fillna('').astype(str).str.lower().str.contains(search_term.lower())
            filtered_df = filtered_df[mask]
        
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
            
        # Filtro per classe di concorso
        if classe_concorso_selected:
            filtered_df = filtered_df[filtered_df['Classe di concorso'].isin(classe_concorso_selected)]
        
        # Filtro per percorsi formativi
        if percorsi_selected:
            mask = pd.Series(False, index=filtered_df.index)
            for percorso in percorsi_selected:
                col_name = pef_options[percorso]
                mask = mask | (filtered_df[col_name] == 'P') | (filtered_df[col_name] == 'D')
            filtered_df = filtered_df[mask]
        
        # Visualizzazione dei risultati
        st.markdown("### 📋 Risultati della Ricerca")
        
        # Calcola il totale CFU dei record filtrati
        filtered_cfu = 0
        if 'CFU' in filtered_df.columns:
            # Assicurati che tutti i valori CFU siano numerici
            filtered_df['CFU'] = pd.to_numeric(filtered_df['CFU'], errors='coerce')
            filtered_cfu = filtered_df['CFU'].fillna(0).sum()
        
        # Calcola il tempo totale in ore decimali
        tempo_totale_decimale = filtered_cfu * 4.5
        
        # Converti in formato ore:minuti con arrotondamento ai quarti d'ora
        tempo_ore = int(tempo_totale_decimale)
        tempo_minuti_decimale = (tempo_totale_decimale - tempo_ore) * 60
        
        # Arrotonda ai quarti d'ora (0, 15, 30, 45)
        if tempo_minuti_decimale < 7.5:
            tempo_minuti = 0
        elif tempo_minuti_decimale < 22.5:
            tempo_minuti = 15
        elif tempo_minuti_decimale < 37.5:
            tempo_minuti = 30
        elif tempo_minuti_decimale < 52.5:
            tempo_minuti = 45
        else:
            tempo_minuti = 0
            tempo_ore += 1
            
        tempo_sessagesimale = f"{tempo_ore}:{tempo_minuti:02d}"
        
        # Mostra il conteggio delle lezioni filtrate, il loro totale CFU e il tempo in formato sessagesimale
        st.info(f"📊 Lezioni selezionate: {len(filtered_df)} | 🎓 CFU selezionati: {filtered_cfu:.1f} | ⏱️ Ore totali: {tempo_sessagesimale}")
        
        if not filtered_df.empty:
            # Converti le date per la visualizzazione
            display_df = filtered_df.copy()
            display_df['Data'] = display_df['Data'].apply(format_date)
            
            # Applica i link Teams cliccabili al dataframe
            display_df = apply_teams_links_to_dataframe(display_df)
            
            # Usa le colonne selezionate dall'utente
            view_cols = st.session_state.selected_columns.copy()
            
            # Se sono selezionati percorsi formativi specifici, assicurati che le loro colonne siano incluse
            if percorsi_selected:
                # Mappa dei percorsi selezionati alle rispettive colonne
                pef_cols_map = {
                    "PeF60 (60 CFU)": "PeF60 all.1",
                    "PeF30 all.2 (30 CFU)": "PeF30 all.2", 
                    "PeF36 all.5 (36 CFU)": "PeF36 all.5",
                    "PeF30 art.13 (30 CFU)": "PeF30 art.13"
                }
                
                percorsi_cols = [pef_cols_map[percorso] for percorso in percorsi_selected]
                
                # Aggiungi le colonne dei percorsi selezionati se non sono già incluse
                for col in percorsi_cols:
                    if col not in view_cols:
                        view_cols.append(col)
            
            # Gestisce la visualizzazione dei link Teams
            # Purtroppo st.dataframe non supporta HTML direttamente, quindi dobbiamo usare un approccio alternativo
            
            # Mostra il dataframe normalmente
            st.dataframe(display_df[view_cols], use_container_width=True, height=400)
            
            # Se ci sono link Teams, fornisci istruzioni su come aprirli
            if 'Link Teams' in view_cols:
                st.info("ℹ️ I link Teams sono disponibili nella colonna 'Link Teams'. Copia e incolla il link nel tuo browser per aprire la riunione Teams.")
                
            # Aggiungi una separazione visiva
            st.markdown("---")
            
            # Mostra il conteggio totale dei record e CFU in fondo alla pagina
            if 'total_records' in st.session_state:
                total_cfu = st.session_state.get('total_cfu', 0)
                
                # Calcola il tempo totale in formato sessagesimale anche per il totale generale
                tot_tempo_decimale = total_cfu * 4.5
                tot_tempo_ore = int(tot_tempo_decimale)
                tot_tempo_minuti_decimale = (tot_tempo_decimale - tot_tempo_ore) * 60
                
                # Arrotonda ai quarti d'ora (0, 15, 30, 45)
                if tot_tempo_minuti_decimale < 7.5:
                    tot_tempo_minuti = 0
                elif tot_tempo_minuti_decimale < 22.5:
                    tot_tempo_minuti = 15
                elif tot_tempo_minuti_decimale < 37.5:
                    tot_tempo_minuti = 30
                elif tot_tempo_minuti_decimale < 52.5:
                    tot_tempo_minuti = 45
                else:
                    tot_tempo_minuti = 0
                    tot_tempo_ore += 1
                
                tot_tempo_sessagesimale = f"{tot_tempo_ore}:{tot_tempo_minuti:02d}"
                
                st.caption(f"📊 Totale record nel calendario: {st.session_state.total_records} | 🎓 Totale CFU nel calendario: {total_cfu:.1f} | ⏱️ Ore totali: {tot_tempo_sessagesimale}")
        else:
            st.warning("Nessun risultato trovato con i filtri selezionati.")
    else:
        st.error("Impossibile caricare i dati del calendario. Verifica che il file esista nella cartella 'dati'.")

if __name__ == "__main__":
    main()
