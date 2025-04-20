"""
Pagina Streamlit per la gestione dei record duplicati nel calendario.
"""

import streamlit as st
import pandas as pd
import os
import sys
from pathlib import Path

# Aggiungi la directory principale al path per l'importazione dei moduli
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Importa le utility per i duplicati e altre funzioni necessarie
from duplicates_utils import mostra_confronto_duplicati, elimina_duplicati_esatti, mostra_analisi_cfu
from completeness_utils import mostra_dashboard_completezza
from file_utils import load_data, save_data
from log_utils import logger

st.set_page_config(
    page_title="Gestione Duplicati Calendario",
    page_icon="🔍",
    layout="wide"
)

def main():
    """
    Funzione principale per la gestione dei record duplicati.
    """
    st.title("🔍 Gestione Record Duplicati")
    
    # Sidebar
    with st.sidebar:
        st.header("Informazioni")
        st.info(
            "Questa pagina consente di identificare e gestire record potenzialmente duplicati "
            "nel calendario. I duplicati vengono identificati in base a Data, Docente e Orario identici."
        )
        
        # Aggiungi una descrizione delle funzionalità
        st.markdown("""
        ### Funzionalità:
        
        - **Ricerca Duplicati**: Trova automaticamente record con stessa data, docente e orario.
        - **Confronto Visuale**: Evidenzia le differenze tra i record simili.
        - **Gestione Selettiva**: Scegli quali record eliminare in base alle tue necessità.
        """)
        
        # Aggiungi un pulsante per eliminare i duplicati esatti
        if st.button("Elimina Duplicati Esatti", type="primary"):
            if "calendario_df" in st.session_state:
                df_originale = st.session_state["calendario_df"]
                df_pulito = elimina_duplicati_esatti(df_originale)
                
                # Aggiorna il dataframe nel session state se sono stati rimossi duplicati
                if len(df_pulito) < len(df_originale):
                    num_eliminati = len(df_originale) - len(df_pulito)
                    st.session_state["calendario_df"] = df_pulito
                    
                    # Salva i dati aggiornati
                    save_data(df_pulito)
                    
                    st.success(f"Eliminati {num_eliminati} duplicati esatti.")
                    st.rerun()
                else:
                    st.info("Non sono stati trovati duplicati esatti.")
    
    # Carica i dati
    if "calendario_df" not in st.session_state or st.session_state["calendario_df"] is None:
        df = load_data()
        if df is not None:
            st.session_state["calendario_df"] = df
    else:
        df = st.session_state["calendario_df"]
    
    # Se non ci sono dati, mostra un messaggio e termina
    if df is None or df.empty:
        st.warning("Nessun dato disponibile. Carica prima dei dati nel calendario.")
        return
    
    # Mostra le statistiche generali
    st.subheader("Statistiche Generali")
    st.write(f"Numero totale di record: {len(df)}")
    
    # Crea tab per separare le diverse funzionalità
    tab1, tab2, tab3 = st.tabs(["🔍 Duplicati per Data/Docente/Orario", "📊 Analisi CFU", "🎯 Dashboard Completezza"])
    
    with tab1:
        # Utilizza la funzione di confronto dei duplicati standard
        mostra_confronto_duplicati(df)
    
    with tab2:
        # Utilizza la nuova funzionalità di analisi dei CFU
        target_cfu = st.slider("Target CFU per classe di concorso:", min_value=1.0, max_value=30.0, value=16.0, step=0.5)
        mostra_analisi_cfu(df, target_cfu=target_cfu)
        
        st.markdown("""
        ### Guida all'analisi CFU
        
        - **CFU in ECCESSO**: Classi che superano il target di CFU. Potrebbero contenere duplicati non evidenti con il metodo standard.
        - **CFU in DIFETTO**: Classi con meno CFU del target. Potrebbero mancare lezioni nel calendario.
        - **CFU corretti**: Classi che corrispondono al target di CFU (considerando una piccola tolleranza).
        
        Per le classi con CFU in eccesso, si consiglia di esaminare attentamente le lezioni per identificare eventuali duplicati nascosti. 
        Cerca lezioni con lo stesso docente in date vicine che potrebbero essere inserite erroneamente più volte con piccole differenze.
        """)
    
    with tab3:
        # Utilizza la nuova dashboard di completezza
        target_cfu_dashboard = st.slider("Target CFU per classe di concorso:", min_value=1.0, max_value=30.0, value=16.0, step=0.5, key="target_dashboard")
        mostra_dashboard_completezza(df, target_cfu=target_cfu_dashboard)
    
    # Aggiungi una nota alla fine
    st.markdown("---")
    st.caption("Nota: I record eliminati non possono essere recuperati. Assicurati di avere un backup dei dati.")

if __name__ == "__main__":
    main()
