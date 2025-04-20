# filepath: /mnt/git/calendario/report_utils.py
"""
Utility per generare report avanzati integrati sullo stato del calendario.
Questo modulo fornisce funzioni per generare report completi che integrano analisi dei duplicati,
analisi dei CFU, verifica della completezza e suggerimenti per migliorare la qualità dei dati.
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Union
import datetime
import os
from log_utils import logger
from duplicates_utils import trova_potenziali_duplicati, analizza_cfu_per_classe, analizza_classi_lingue
from completeness_utils import verifica_completezza_dati

def genera_report_completo(df: pd.DataFrame, metodo_duplicati: str = 'completo', 
                          target_cfu: float = 16.0) -> Tuple[str, Dict]:
    """
    Genera un report completo che integra tutte le analisi sul calendario.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        metodo_duplicati: Metodo di ricerca duplicati ('standard', 'avanzato', 'completo')
        target_cfu: Valore target dei CFU per classe di concorso
        
    Returns:
        Tuple[str, Dict]: Testo del report e dizionario con metriche riassuntive
    """
    if df is None or df.empty:
        return "Nessun dato disponibile per generare il report.", {}
    
    # Timestamp per il report
    timestamp = pd.Timestamp.now()
    
    # Metriche principali
    metriche = {}
    metriche['timestamp'] = timestamp
    metriche['data_generazione'] = timestamp.strftime('%d/%m/%Y %H:%M')
    metriche['num_record_totali'] = len(df)
    
    # 1. Verifica duplicati
    gruppi_duplicati = trova_potenziali_duplicati(df, metodo=metodo_duplicati)
    metriche['num_gruppi_duplicati'] = len(gruppi_duplicati)
    
    if metodo_duplicati == 'completo':
        metriche['num_gruppi_standard'] = len([k for k in gruppi_duplicati.keys() if k.startswith('standard|')])
        metriche['num_gruppi_avanzati'] = len([k for k in gruppi_duplicati.keys() if k.startswith('avanzato|')])
    
    # 2. Analisi CFU
    cfu_analisi = analizza_cfu_per_classe(df, target_cfu)
    
    # Conteggio stati CFU
    status_counts = cfu_analisi['Status'].value_counts().to_dict()
    metriche['num_classi_ok'] = status_counts.get('OK', 0)
    metriche['num_classi_eccesso'] = status_counts.get('ECCESSO', 0)
    metriche['num_classi_difetto'] = status_counts.get('DIFETTO', 0)
    metriche['num_classi_totali'] = len(cfu_analisi)
    
    # 3. Analisi classi trasversali
    classi_trasversali = cfu_analisi[cfu_analisi['Is_Trasversale'] == True]
    metriche['num_classi_trasversali'] = len(classi_trasversali)
    
    # 4. Analisi specifica per lingue
    analisi_lingue = None
    if 'Dipartimento' in df.columns:
        df_lingue = df[df['Dipartimento'].str.lower().str.contains('lingue', na=False)]
        if not df_lingue.empty:
            analisi_lingue = analizza_classi_lingue(df, target_cfu)
            metriche['num_classi_lingue'] = len(analisi_lingue)
            problemi_lingue = analisi_lingue[analisi_lingue['Status'] != 'OK']
            metriche['num_classi_lingue_problematiche'] = len(problemi_lingue)
    
    # 5. Verifica completezza
    _, metriche_completezza = verifica_completezza_dati(df, target_cfu_standard=target_cfu)
    metriche['percentuale_completezza'] = metriche_completezza.get('percentuale_completezza', 0)
    metriche['valutazione_completezza'] = metriche_completezza.get('valutazione', 'N/D')
    metriche['cfu_mancanti'] = metriche_completezza.get('cfu_mancanti', 0)
    metriche['cfu_eccesso'] = metriche_completezza.get('cfu_eccesso', 0)
    
    # Genera il testo del report
    report = []
    
    # Intestazione
    report.append("=" * 80)
    report.append(f"REPORT COMPLETO CALENDARIO - {timestamp.strftime('%d/%m/%Y %H:%M')}")
    report.append("=" * 80)
    report.append("")
    
    # Sezione 1: Informazioni generali
    report.append("INFORMAZIONI GENERALI")
    report.append("-" * 80)
    report.append(f"Data generazione: {timestamp.strftime('%d/%m/%Y %H:%M')}")
    report.append(f"Record totali nel calendario: {len(df)}")
    report.append(f"Classi di concorso: {len(cfu_analisi)}")
    if 'Dipartimento' in df.columns:
        dipartimenti = df['Dipartimento'].dropna().unique()
        report.append(f"Dipartimenti: {len(dipartimenti)}")
    report.append("")
    
    # Sezione 2: Completezza dati
    report.append("COMPLETEZZA DEI DATI")
    report.append("-" * 80)
    report.append(f"Percentuale di completezza: {metriche['percentuale_completezza']}% ({metriche['valutazione_completezza']})")
    report.append(f"CFU mancanti totali: {metriche['cfu_mancanti']}")
    report.append(f"CFU in eccesso totali: {metriche['cfu_eccesso']}")
    report.append("")
    
    # Sezione 3: Analisi duplicati
    report.append("ANALISI DUPLICATI")
    report.append("-" * 80)
    report.append(f"Metodo di ricerca utilizzato: {metodo_duplicati}")
    
    if metodo_duplicati == 'completo':
        report.append(f"Gruppi di duplicati standard: {metriche['num_gruppi_standard']}")
        report.append(f"Gruppi di duplicati avanzati: {metriche['num_gruppi_avanzati']}")
        report.append(f"Gruppi totali: {metriche['num_gruppi_duplicati']}")
    else:
        report.append(f"Potenziali gruppi di duplicati trovati: {metriche['num_gruppi_duplicati']}")
    report.append("")
    
    # Sezione 4: Analisi CFU
    report.append("ANALISI CFU PER CLASSE DI CONCORSO")
    report.append("-" * 80)
    report.append(f"Target CFU standard: {target_cfu}")
    report.append(f"Target CFU trasversali: 24.0")
    report.append(f"Classi con CFU corretti: {metriche['num_classi_ok']}")
    report.append(f"Classi con CFU in eccesso: {metriche['num_classi_eccesso']}")
    report.append(f"Classi con CFU in difetto: {metriche['num_classi_difetto']}")
    report.append("")
    
    # Top 5 classi con maggiori problemi
    if 'classi_critiche' in metriche_completezza and metriche_completezza['classi_critiche']:
        report.append("TOP CLASSI CON PROBLEMI")
        report.append("-" * 80)
        
        for i, classe in enumerate(metriche_completezza['classi_critiche'][:5], 1):
            report.append(f"{i}. {classe['Classe']}")
            report.append(f"   Status: {classe['Status']}")
            report.append(f"   Differenza CFU: {classe['Differenza']}")
            report.append(f"   Azione consigliata: {classe['Azione']}")
            report.append("")
    
    # Sezione 5: Focus dipartimento lingue
    if analisi_lingue is not None and not analisi_lingue.empty:
        report.append("FOCUS DIPARTIMENTO LINGUE")
        report.append("-" * 80)
        report.append(f"Classi analizzate: {metriche.get('num_classi_lingue', 0)}")
        report.append(f"Classi con problemi: {metriche.get('num_classi_lingue_problematiche', 0)}")
        
        problemi_lingue = analisi_lingue[analisi_lingue['Status'] != 'OK']
        if not problemi_lingue.empty:
            report.append("\nDettaglio problemi:")
            for i, (_, row) in enumerate(problemi_lingue.iterrows(), 1):
                report.append(f"\n{i}. Classe: {row['Classe']}")
                report.append(f"   Status: {row['Status']}")
                report.append(f"   CFU totali: {row['CFU_Totali']}, Differenza: {row['Differenza']}")
                report.append(f"   Potenziali duplicati: {row['Potenziali_Duplicati']}")
                report.append(f"   Problemi: {row['Problemi']}")
                
                # Se ci sono dettagli sui duplicati, includiamone alcuni
                if row['Potenziali_Duplicati'] > 0:
                    for j, dup in enumerate(row['Dettaglio_Duplicati'][:2], 1):  # Mostriamo solo i primi 2 per brevità
                        report.append(f"   Duplicato {j}: {dup['Data']} {dup['Orario']} - {dup['Num_Duplicati']} record")
        report.append("")
    
    # Sezione 6: Raccomandazioni
    report.append("RACCOMANDAZIONI")
    report.append("-" * 80)
    
    if metriche['num_gruppi_duplicati'] > 0:
        report.append("1. Verificare i potenziali duplicati identificati")
    
    if metriche['num_classi_eccesso'] > 0:
        n = 2 if metriche['num_gruppi_duplicati'] > 0 else 1
        report.append(f"{n}. Controllare le classi con CFU in eccesso (duplicati nascosti)")
    
    if metriche['num_classi_difetto'] > 0:
        n = 1
        if metriche['num_gruppi_duplicati'] > 0:
            n += 1
        if metriche['num_classi_eccesso'] > 0:
            n += 1
        report.append(f"{n}. Aggiungere lezioni mancanti per classi con CFU in difetto")
    
    if 'num_classi_lingue_problematiche' in metriche and metriche['num_classi_lingue_problematiche'] > 0:
        n = 1
        if metriche['num_gruppi_duplicati'] > 0:
            n += 1
        if metriche['num_classi_eccesso'] > 0:
            n += 1
        if metriche['num_classi_difetto'] > 0:
            n += 1
        report.append(f"{n}. Controllare attentamente le classi del dipartimento di lingue")
    
    # Conclusione
    report.append("\n" + "-" * 80)
    report.append(f"Fine report - Generato automaticamente il {timestamp.strftime('%d/%m/%Y')} alle {timestamp.strftime('%H:%M')}")
    
    return "\n".join(report), metriche


def salva_report_file(report_text: str, directory: str = "reports") -> str:
    """
    Salva il report generato in un file di testo.
    
    Args:
        report_text: Testo del report
        directory: Directory dove salvare il report
        
    Returns:
        str: Path del file salvato
    """
    # Assicurati che la directory esista
    os.makedirs(directory, exist_ok=True)
    
    # Crea il nome del file
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_calendario_{timestamp}.txt"
    
    # Path completo
    filepath = os.path.join(directory, filename)
    
    # Scrivi il file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    logger.info(f"Report salvato in: {filepath}")
    return filepath


def visualizza_report_completo(df: pd.DataFrame):
    """
    Visualizza il report completo in un'interfaccia Streamlit.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
    """
    st.title("📋 Report Completo Calendario")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per generare un report")
        return
    
    # Impostazioni per il report
    st.subheader("Impostazioni Report")
    
    col1, col2 = st.columns(2)
    
    with col1:
        metodo_duplicati = st.selectbox(
            "Metodo ricerca duplicati:",
            options=["standard", "avanzato", "completo"],
            format_func=lambda x: {
                "standard": "Standard (Data/Docente/Orario identici)",
                "avanzato": "Avanzato (cerca anche piccole differenze)",
                "completo": "Completo (combina entrambi i metodi)"
            }[x],
            help="Scegli come cercare i potenziali duplicati"
        )
    
    with col2:
        target_cfu = st.slider(
            "Target CFU per classe di concorso:",
            min_value=1.0,
            max_value=30.0,
            value=16.0,
            step=0.5
        )
    
    # Genera il report
    with st.spinner("Generazione report in corso..."):
        report_text, metriche = genera_report_completo(
            df, 
            metodo_duplicati=metodo_duplicati,
            target_cfu=target_cfu
        )
    
    # Visualizza metriche principali
    st.subheader("Riepilogo Generale")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Completezza dati", f"{metriche['percentuale_completezza']}%")
    with col2:
        st.metric("Classi con problemi", metriche['num_classi_eccesso'] + metriche['num_classi_difetto'])
    with col3:
        st.metric("Potenziali duplicati", metriche['num_gruppi_duplicati'])
    
    # Visualizza il testo del report
    st.subheader("Report Dettagliato")
    
    with st.expander("Espandi/Comprimi Report Completo", expanded=True):
        st.text(report_text)
    
    # Opzioni di salvataggio
    st.subheader("Azioni")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Salva report su file", type="primary"):
            filepath = salva_report_file(report_text)
            st.success(f"Report salvato con successo: {filepath}")
    
    with col2:
        st.download_button(
            label="Scarica Report",
            data=report_text,
            file_name=f"report_calendario_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain"
        )
