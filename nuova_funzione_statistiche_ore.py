import pandas as pd
import streamlit as st
import os
from file_utils import save_data

def mostra_statistiche_docenti(df):
    """
    Funzione migliorata per visualizzare le statistiche per docente,
    con aggiunta della colonna delle ore calcolate dai CFU.
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
    
    # Assicuriamoci che la colonna delle ore sia presente
    if 'Ore' not in stats_df.columns:
        # Calcoliamo le ore: CFU * 4.5 ore
        stats_df['Ore'] = stats_df['CFU_numeric'] * 4.5
        # Arrotondiamo ai quarti d'ora (0.25h = 15min)
        stats_df['Ore'] = (stats_df['Ore'] / 0.25).round() * 0.25
    
    # Formatta le ore se non è già stato fatto
    if 'Ore_formattate' not in stats_df.columns:
        def format_ore(ore):
            ore_intere = int(ore)
            minuti = int((ore - ore_intere) * 60)
            return f"{ore_intere}h {minuti:02d}m"
        stats_df['Ore_formattate'] = stats_df['Ore'].apply(format_ore)
    
    # Usa una versione pulita del dataframe senza duplicati per le statistiche
    stats_df_clean = stats_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Approccio completamente nuovo per il calcolo delle statistiche
    st.subheader("Statistiche Lezioni per Docente")
    
    # Prepariamo un nuovo dataframe ottimizzato per le statistiche
    stat_columns = ['Docente', 'Dipartimento', 'Data', 'Orario', 'Denominazione Insegnamento', 'CFU', 'Ore']
    lezioni_df = stats_df[stat_columns].copy()
    
    # Standardizziamo i valori CFU
    lezioni_df['CFU'] = lezioni_df['CFU'].astype(str).str.replace(',', '.').replace('nan', '0')
    lezioni_df['CFU'] = pd.to_numeric(lezioni_df['CFU'], errors='coerce').fillna(0)
    
    # Rimuoviamo i duplicati
    lezioni_df = lezioni_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Calcolo statistiche per docente
    if not lezioni_df.empty:
        # Raggruppamento e calcolo
        # Aggiungiamo dipartimento al raggruppamento per mantenerlo nelle statistiche
        docenti_stats = lezioni_df.groupby(['Docente', 'Dipartimento']).agg(
            Numero_lezioni=pd.NamedAgg(column='Denominazione Insegnamento', aggfunc='count'),
            Totale_CFU=pd.NamedAgg(column='CFU', aggfunc='sum'),
            Totale_Ore=pd.NamedAgg(column='Ore', aggfunc='sum')
        ).reset_index()
        
        # Rinomina colonne per visualizzazione
        docenti_stats.columns = ['Docente', 'Dipartimento', 'Numero lezioni', 'Totale CFU', 'Totale Ore']
        
        # Arrotonda i valori CFU e ore
        docenti_stats['Totale CFU'] = docenti_stats['Totale CFU'].round(1)
        docenti_stats['Totale Ore'] = docenti_stats['Totale Ore'].round(2)
        
        # Formatta la colonna delle ore totali
        def format_ore_totali(ore):
            ore_intere = int(ore)
            minuti = int((ore - ore_intere) * 60)
            return f"{ore_intere}h {minuti:02d}m"
        
        docenti_stats['Totale Ore Formattate'] = docenti_stats['Totale Ore'].apply(format_ore_totali)
        
        # Ordina per docente
        docenti_stats = docenti_stats.sort_values('Docente')
        
        # Visualizza statistiche con la nuova colonna delle ore e il dipartimento
        display_stats = docenti_stats[['Docente', 'Dipartimento', 'Numero lezioni', 'Totale CFU', 'Totale Ore Formattate']]
        display_stats.columns = ['Docente', 'Dipartimento', 'Numero lezioni', 'Totale CFU', 'Totale Ore']
        st.dataframe(display_stats, use_container_width=True, hide_index=True)
        
        # Calcola e mostra i totali generali
        totale_lezioni = docenti_stats['Numero lezioni'].sum()
        totale_cfu = docenti_stats['Totale CFU'].sum()
        totale_ore_raw = docenti_stats['Totale Ore'].sum()
        totale_ore_fmt = format_ore_totali(totale_ore_raw)
        
        # Mostra il riepilogo totale in un box informativo
        st.success(f"📊 Totale complessivo: {totale_lezioni} lezioni | 🎓 {totale_cfu:.1f} CFU | ⏱️ {totale_ore_fmt} ore")
        
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
            
            # Crea una nuova colonna per le ore formattate e rimuovi la colonna Ore originale
            docente_lezioni = docente_lezioni.copy()
            docente_lezioni['Ore_fmt'] = docente_lezioni['Ore'].apply(format_ore_totali)
            
            # Rinomina colonne per miglior leggibilità e seleziona solo le necessarie
            display_df = docente_lezioni[['Data', 'Orario', 'Dipartimento', 'Denominazione Insegnamento', 'CFU', 'Ore_fmt']]
            display_df.columns = ['Data', 'Orario', 'Dipartimento', 'Insegnamento', 'CFU', 'Ore']
            
            # Visualizza i dettagli
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Mostra il totale CFU e ore per questo docente
            numero_lezioni = len(docente_lezioni)
            totale_cfu = docente_lezioni['CFU'].sum()
            totale_ore_raw = docente_lezioni['Ore'].sum()
            totale_ore_fmt = format_ore_totali(totale_ore_raw)
            st.info(f"📊 {selected_docente}: {numero_lezioni} lezioni | 🎓 {round(totale_cfu, 1)} CFU | ⏱️ {totale_ore_fmt} ore")
    else:
        st.info("Nessuna statistica disponibile sui docenti")
