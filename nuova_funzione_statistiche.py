import pandas as pd
import streamlit as st
import os
from admin_utils import save_dataframe_to_csv

def mostra_statistiche_docenti(df):
    """
    Funzione migliorata per visualizzare le statistiche per docente,
    gestendo correttamente i valori dei CFU con formati diversi (punto o virgola).
    """
    st.subheader("Statistiche per Docente")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per le statistiche")
        return
    
    # Crea una copia del dataframe per le operazioni
    stats_df = df.copy()
    
    # Pulisci e standardizza i valori dei CFU
    stats_df['CFU_clean'] = stats_df['CFU'].astype(str).str.replace(',', '.')
    stats_df['CFU_clean'] = stats_df['CFU_clean'].replace('nan', '0')
    stats_df['CFU_numeric'] = pd.to_numeric(stats_df['CFU_clean'], errors='coerce').fillna(0)
    
    # Nessun codice di rilevamento duplicati qui
    
    # Usa una versione pulita del dataframe senza duplicati per le statistiche
    stats_df_clean = stats_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Approccio completamente nuovo per il calcolo delle statistiche
    st.subheader("Statistiche Lezioni per Docente")
    
    # Prepariamo un nuovo dataframe ottimizzato per le statistiche
    stat_columns = ['Docente', 'Data', 'Orario', 'Denominazione Insegnamento', 'CFU']
    lezioni_df = stats_df[stat_columns].copy()
    
    # Standardizziamo i valori CFU
    lezioni_df['CFU'] = lezioni_df['CFU'].astype(str).str.replace(',', '.').replace('nan', '0')
    lezioni_df['CFU'] = pd.to_numeric(lezioni_df['CFU'], errors='coerce').fillna(0)
    
    # Rimuoviamo i duplicati
    lezioni_df = lezioni_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Calcolo statistiche per docente
    if not lezioni_df.empty:
        # Raggruppamento e calcolo
        docenti_stats = lezioni_df.groupby('Docente').agg(
            Numero_lezioni=pd.NamedAgg(column='Denominazione Insegnamento', aggfunc='count'),
            Totale_CFU=pd.NamedAgg(column='CFU', aggfunc='sum')
        ).reset_index()
        
        # Rinomina colonne per visualizzazione
        docenti_stats.columns = ['Docente', 'Numero lezioni', 'Totale CFU']
        
        # Arrotonda i valori CFU
        docenti_stats['Totale CFU'] = docenti_stats['Totale CFU'].round(1)
        
        # Ordina per docente
        docenti_stats = docenti_stats.sort_values('Docente')
        
        # Visualizza statistiche
        st.dataframe(docenti_stats, use_container_width=True, hide_index=True)
        
        # Lista docenti per selezione
        docenti_list = [""] + sorted(lezioni_df['Docente'].unique().tolist())
        
        # Aggiungi una sezione per vedere i dettagli di un docente specifico
        selected_docente = st.selectbox("Visualizza dettaglio lezioni per docente:", docenti_list)
        
        if selected_docente:
            st.subheader(f"Dettaglio lezioni: {selected_docente}")
            
            # Filtra lezioni del docente selezionato
            docente_lezioni = lezioni_df[lezioni_df['Docente'] == selected_docente]
            
            # Formatta le date per una migliore visualizzazione
            if 'Data' in docente_lezioni.columns and hasattr(docente_lezioni['Data'], 'dt'):
                docente_lezioni['Data'] = docente_lezioni['Data'].dt.strftime('%A %d %B %Y')
            
            # Rinomina colonne per miglior leggibilità
            display_df = docente_lezioni.rename(columns={
                'Denominazione Insegnamento': 'Insegnamento'
            })
            
            # Visualizza i dettagli
            st.dataframe(display_df, use_container_width=True)
            
            # Mostra il totale CFU per questo docente
            totale = display_df['CFU'].sum()
            st.info(f"Totale CFU per {selected_docente}: {round(totale, 1)}")
    else:
        st.info("Nessuna statistica disponibile sui docenti")
