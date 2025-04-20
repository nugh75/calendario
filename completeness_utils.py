# filepath: /mnt/git/calendario/completeness_utils.py
"""
Utility per la verifica della completezza dei dati nel calendario.
Questo modulo fornisce funzioni per verificare la completezza dei dati rispetto ai requisiti
di CFU per ogni classe di concorso.
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Union
from log_utils import logger
from duplicates_utils import analizza_cfu_per_classe


def verifica_completezza_dati(df: pd.DataFrame, target_cfu_standard: float = 16.0) -> Tuple[pd.DataFrame, Dict]:
    """
    Verifica la completezza dei dati del calendario rispetto ai requisiti di CFU.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        target_cfu_standard: Valore target standard dei CFU (default: 16.0)
        
    Returns:
        Tuple[pd.DataFrame, Dict]: DataFrame con l'analisi di completezza e dizionario con metriche
    """
    if df is None or df.empty:
        return pd.DataFrame(), {}
    
    # Esegui l'analisi dei CFU
    cfu_analisi = analizza_cfu_per_classe(df, target_cfu=target_cfu_standard)
    
    # Conteggi per stato
    metriche = {}
    metriche['totale_classi'] = len(cfu_analisi)
    metriche['classi_ok'] = len(cfu_analisi[cfu_analisi['Status'] == 'OK'])
    metriche['classi_eccesso'] = len(cfu_analisi[cfu_analisi['Status'] == 'ECCESSO'])
    metriche['classi_difetto'] = len(cfu_analisi[cfu_analisi['Status'] == 'DIFETTO'])
    metriche['percentuale_completezza'] = round((metriche['classi_ok'] / metriche['totale_classi']) * 100, 1) if metriche['totale_classi'] > 0 else 0
    
    # Calcola potenziali CFU mancanti/in eccesso
    cfu_analisi['CFU_Diff_Abs'] = cfu_analisi['Differenza'].abs()
    metriche['cfu_mancanti'] = round(cfu_analisi[cfu_analisi['Status'] == 'DIFETTO']['Differenza'].abs().sum(), 1)
    metriche['cfu_eccesso'] = round(cfu_analisi[cfu_analisi['Status'] == 'ECCESSO']['Differenza'].sum(), 1)
    
    # Identifica le classi con le maggiori discrepanze
    classi_critiche = []
    
    # Top 5 classi con più CFU mancanti
    top_mancanti = cfu_analisi[cfu_analisi['Status'] == 'DIFETTO'].sort_values(by='CFU_Diff_Abs', ascending=False).head(5)
    for _, row in top_mancanti.iterrows():
        classe = row['Insegnamento comune']
        target = row['Target_CFU']
        attuali = row['CFU_numeric']
        diff = row['Differenza']
        classi_critiche.append({
            'Classe': classe,
            'Status': 'DIFETTO',
            'CFU_Attuale': attuali,
            'Target': target,
            'Differenza': diff,
            'Azione': f"Aggiungere circa {abs(round(diff))} CFU",
            'Priorità': 'Alta' if abs(diff) > 3 else 'Media'
        })
    
    # Top 5 classi con più CFU in eccesso
    top_eccessi = cfu_analisi[cfu_analisi['Status'] == 'ECCESSO'].sort_values(by='CFU_Diff_Abs', ascending=False).head(5)
    for _, row in top_eccessi.iterrows():
        classe = row['Insegnamento comune']
        target = row['Target_CFU']
        attuali = row['CFU_numeric']
        diff = row['Differenza']
        classi_critiche.append({
            'Classe': classe,
            'Status': 'ECCESSO',
            'CFU_Attuale': attuali,
            'Target': target,
            'Differenza': diff,
            'Azione': f"Verificare {round(diff)} CFU potenzialmente duplicati",
            'Priorità': 'Alta' if diff > 3 else 'Media'
        })
        
    # Aggiungi le classi critiche alle metriche
    metriche['classi_critiche'] = classi_critiche
    
    # Valutazione complessiva
    metriche['valutazione'] = "Ottima"
    if metriche['percentuale_completezza'] < 90:
        metriche['valutazione'] = "Buona"
    if metriche['percentuale_completezza'] < 80:
        metriche['valutazione'] = "Mediocre"
    if metriche['percentuale_completezza'] < 70:
        metriche['valutazione'] = "Insufficiente"
    
    return cfu_analisi, metriche


def genera_report_completezza(df: pd.DataFrame, metriche: Dict) -> str:
    """
    Genera un report di completezza dei dati in formato testo.
    
    Args:
        df: DataFrame con analisi di completezza
        metriche: Dizionario con le metriche di completezza
        
    Returns:
        str: Testo del report
    """
    linee_report = []
    
    linee_report.append("REPORT COMPLETEZZA DATI CALENDARIO")
    linee_report.append("=================================")
    linee_report.append(f"Data generazione: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")
    linee_report.append(f"Classi analizzate: {metriche['totale_classi']}")
    linee_report.append("")
    
    linee_report.append("VALUTAZIONE COMPLESSIVA")
    linee_report.append("----------------------")
    linee_report.append(f"Completezza: {metriche['percentuale_completezza']}% ({metriche['valutazione']})")
    linee_report.append(f"Classi con CFU corretti: {metriche['classi_ok']} su {metriche['totale_classi']}")
    linee_report.append(f"Classi con CFU in eccesso: {metriche['classi_eccesso']}")
    linee_report.append(f"Classi con CFU in difetto: {metriche['classi_difetto']}")
    linee_report.append(f"CFU totali mancanti: {metriche['cfu_mancanti']}")
    linee_report.append(f"CFU totali in eccesso: {metriche['cfu_eccesso']}")
    linee_report.append("")
    
    linee_report.append("CLASSI CRITICHE")
    linee_report.append("--------------")
    if 'classi_critiche' in metriche and metriche['classi_critiche']:
        for i, classe in enumerate(metriche['classi_critiche'], 1):
            linee_report.append(f"{i}. {classe['Classe']}")
            linee_report.append(f"   Status: {classe['Status']}")
            linee_report.append(f"   CFU Attuali: {classe['CFU_Attuale']} / Target: {classe['Target']}")
            linee_report.append(f"   Differenza: {classe['Differenza']}")
            linee_report.append(f"   Azione consigliata: {classe['Azione']} (Priorità {classe['Priorità']})")
            linee_report.append("")
    else:
        linee_report.append("Nessuna classe critica identificata.")
    
    linee_report.append("")
    linee_report.append("RACCOMANDAZIONI")
    linee_report.append("--------------")
    
    if metriche['classi_difetto'] > 0:
        linee_report.append(f"1. Verificare le {metriche['classi_difetto']} classi con CFU in difetto:")
        linee_report.append("   - Potrebbero mancare lezioni")
        linee_report.append("   - Verificare che tutte le lezioni siano state caricate correttamente")
        linee_report.append("   - Controllare che i CFU siano stati impostati correttamente")
    
    if metriche['classi_eccesso'] > 0:
        n = 2 if metriche['classi_difetto'] > 0 else 1
        linee_report.append(f"{n}. Verificare le {metriche['classi_eccesso']} classi con CFU in eccesso:")
        linee_report.append("   - Potrebbero esserci lezioni duplicate")
        linee_report.append("   - Utilizzare lo strumento di ricerca duplicati avanzato")
        linee_report.append("   - Verificare lezioni con date vicine o docenti simili")
    
    return "\n".join(linee_report)


def mostra_dashboard_completezza(df: pd.DataFrame, target_cfu: float = 16.0):
    """
    Visualizza una dashboard per la verifica della completezza dei dati.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        target_cfu: Valore target dei CFU per ogni classe di concorso (default: 16.0)
    """
    st.subheader("🎯 Dashboard Completezza Dati")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per l'analisi di completezza")
        return
    
    # Esegui analisi di completezza
    _, metriche = verifica_completezza_dati(df, target_cfu_standard=target_cfu)
    
    # Dashboard principale
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Visualizza l'indicatore di completezza
        completezza = metriche['percentuale_completezza']
        st.subheader("Completezza Complessiva")
        
        # Determina il colore in base alla percentuale
        if completezza >= 90:
            colore = "green"
        elif completezza >= 80:
            colore = "orange"
        elif completezza >= 70:
            colore = "yellow"
        else:
            colore = "red"
            
        # Visualizza la percentuale con un design accattivante
        st.markdown(f"""
        <div style="text-align: center;">
            <div style="font-size: 60px; font-weight: bold; color: {colore}; text-shadow: 1px 1px 3px rgba(0,0,0,0.2);">
                {completezza}%
            </div>
            <div style="font-size: 24px; color: #555; margin-top: -10px;">
                {metriche['valutazione']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Aggiungi indicatori visivi di stato
        st.markdown("### Distribuzione Classi")
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric(label="✅ CFU corretti", value=metriche['classi_ok'])
        with col_b:
            st.metric(label="⚠️ CFU in eccesso", value=metriche['classi_eccesso'])
        with col_c:
            st.metric(label="❌ CFU in difetto", value=metriche['classi_difetto'])
            
    with col2:
        st.subheader("Azioni consigliate")
        
        # Mostra le classi critiche
        if 'classi_critiche' in metriche and metriche['classi_critiche']:
            for classe in metriche['classi_critiche']:
                with st.expander(f"{classe['Classe']} ({classe['Status']})"):
                    st.markdown(f"""
                    **CFU Attuali:** {classe['CFU_Attuale']}  
                    **CFU Target:** {classe['Target']}  
                    **Differenza:** {classe['Differenza']}  
                    **Azione:** {classe['Azione']}  
                    **Priorità:** {classe['Priorità']}
                    """)
        else:
            st.info("Nessuna classe critica identificata.")
    
    # Aggiungi sezione per il download del report
    st.markdown("---")
    report_text = genera_report_completezza(df, metriche)
    st.download_button(
        label="📄 Scarica Report Completezza",
        data=report_text,
        file_name=f"report_completezza_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        help="Scarica un report dettagliato sulla completezza dei dati"
    )
