"""
Utility per identificare e gestire record potenzialmente duplicati nel calendario.
Questo modulo fornisce funzioni per identificare e gestire record che potrebbero essere duplicati
con differenze impercettibili in alcuni campi.
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Union
import difflib
import numpy as np
import os
from log_utils import logger
from merge_utils import merge_duplicati, applica_merge, scegli_valori_per_merge, merge_con_selezione
from cfu_riepilogo_utils import _filtra_classi_multiple

def trova_potenziali_duplicati(df: pd.DataFrame, metodo: str = 'standard') -> Dict[str, pd.DataFrame]:
    """
    Identifica record potenzialmente duplicati basati su vari criteri.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        metodo: Metodo di ricerca dei duplicati. Opzioni:
                - 'standard': cerca duplicati con stessa Data, Docente e Orario
                - 'avanzato': usa criteri più flessibili per trovare duplicati simili
                - 'completo': combina entrambi i metodi
        
    Returns:
        Dict[str, pd.DataFrame]: Dizionario con gruppi di potenziali duplicati
    """
    if df is None or df.empty:
        return {}
    
    # Crea una copia del dataframe per le operazioni
    working_df = df.copy()
    
    # Assicuriamoci che la colonna Data sia in formato stringa per il raggruppamento
    if 'Data' in working_df.columns and hasattr(working_df['Data'], 'dt'):
        working_df['Data_str'] = working_df['Data'].dt.strftime('%Y-%m-%d')
    else:
        working_df['Data_str'] = working_df['Data'].astype(str)
    
    gruppi_duplicati = {}
    
    if metodo in ['standard', 'completo']:
        # METODO STANDARD: stessa Data, Docente e Orario
        # Crea una chiave di raggruppamento
        working_df['gruppo_key'] = working_df['Data_str'] + '|' + working_df['Docente'].astype(str) + '|' + working_df['Orario'].astype(str)
        
        # Trova gruppi con più di un record
        gruppi = working_df.groupby('gruppo_key')
        gruppi_duplicati_standard = {k: g for k, g in gruppi if len(g) > 1}
        
        # Aggiungi un prefisso al gruppo key per identificare il metodo
        gruppi_duplicati.update({f"standard|{k}": g for k, g in gruppi_duplicati_standard.items()})
    
    if metodo in ['avanzato', 'completo']:
        # METODO AVANZATO: cerca anche piccole differenze
        # Questo metodo identifica duplicati potenziali anche quando ci sono piccole differenze
        
        # 1. Raggruppamento per Docente e per vicinanza di Date (±3 giorni)
        # Per ogni docente, raggruppiamo le lezioni e cerchiamo date vicine
        for docente, gruppo_docente in working_df.groupby('Docente'):
            if len(gruppo_docente) < 2:  # Serve almeno 2 record per un duplicato
                continue
                
            # Convertire le date in timestamp per confronto numerico
            if hasattr(gruppo_docente['Data'], 'dt'):
                gruppo_docente = gruppo_docente.copy()
                gruppo_docente['data_ts'] = gruppo_docente['Data'].astype(int) / 10**9  # Timestamp in secondi
            else:
                continue  # Se non possiamo convertire a timestamp, saltiamo
            
            # Ordina per data
            gruppo_docente = gruppo_docente.sort_values(by='data_ts')
            
            # Cerca lezioni con date vicine (entro 3 giorni)
            for i in range(len(gruppo_docente)):
                for j in range(i+1, len(gruppo_docente)):
                    rec_i = gruppo_docente.iloc[i]
                    rec_j = gruppo_docente.iloc[j]
                    
                    # Differenza in giorni
                    diff_giorni = abs(rec_j['data_ts'] - rec_i['data_ts']) / (60*60*24)
                    
                    if diff_giorni <= 3:  # Entro 3 giorni
                        # Cerca anche somiglianza in altri campi importanti
                        # Verifica se sono lezioni simili (stesso insegnamento o simile)
                        insegnamento_i = str(rec_i.get('Denominazione Insegnamento', '')).lower()
                        insegnamento_j = str(rec_j.get('Denominazione Insegnamento', '')).lower()
                        
                        # Calcola somiglianza tra stringhe (ratio tra 0 e 1)
                        similarita = difflib.SequenceMatcher(None, insegnamento_i, insegnamento_j).ratio()
                        
                        # Se hanno docente, date vicine e insegnamenti simili, potrebbero essere duplicati
                        if similarita > 0.6:  # Soglia di somiglianza
                            # Crea una chiave per questo gruppo
                            gruppo_key = f"avanzato|{rec_i['Data_str']}~{rec_j['Data_str']}|{docente}"
                            
                            # Crea un DataFrame con i due record
                            duplicati_df = pd.DataFrame([rec_i, rec_j])
                            
                            # Aggiungi al dizionario dei gruppi
                            gruppi_duplicati[gruppo_key] = duplicati_df
        
        # 2. Cerca record con stesso insegnamento, stessa data ma orari vicini (possibili errori di battitura)
        if 'Denominazione Insegnamento' in working_df.columns:
            for (data, insegnamento), gruppo in working_df.groupby(['Data_str', 'Denominazione Insegnamento']):
                if len(gruppo) < 2:
                    continue
                
                # Se sono per lo stesso giorno e insegnamento
                # Controlliamo gli orari per vedere se sono vicini
                try:
                    # Converti orari in minuti per confronto numerico
                    gruppo['orario_minuti'] = gruppo['Orario'].apply(lambda x: 
                        int(str(x).split(':')[0]) * 60 + int(str(x).split(':')[1]) 
                        if ':' in str(x) else 0)
                    
                    # Ordina per orario
                    gruppo = gruppo.sort_values('orario_minuti')
                    
                    # Cerca lezioni con orari vicini (entro 90 minuti)
                    for i in range(len(gruppo)):
                        for j in range(i+1, len(gruppo)):
                            rec_i = gruppo.iloc[i]
                            rec_j = gruppo.iloc[j]
                            
                            diff_minuti = abs(rec_j['orario_minuti'] - rec_i['orario_minuti'])
                            
                            if diff_minuti <= 90:  # Entro 90 minuti
                                # Crea una chiave per questo gruppo
                                gruppo_key = f"avanzato|{data}|{rec_i['Orario']}~{rec_j['Orario']}|{insegnamento[:30]}"
                                
                                # Crea un DataFrame con i due record
                                duplicati_df = pd.DataFrame([rec_i, rec_j])
                                
                                # Aggiungi al dizionario dei gruppi
                                gruppi_duplicati[gruppo_key] = duplicati_df
                except Exception as e:
                    # In caso di errori nel confronto orari, procedi comunque
                    logger.warning(f"Errore nel confronto orari per lezione: {e}")
                    continue
    
    return gruppi_duplicati

def evidenzia_differenze(str1: str, str2: str) -> Tuple[str, str]:
    """
    Evidenzia le differenze tra due stringhe per mostrare visivamente cosa è cambiato.
    
    Args:
        str1: Prima stringa
        str2: Seconda stringa
        
    Returns:
        Tuple[str, str]: Le due stringhe con le differenze evidenziate in HTML
    """
    matcher = difflib.SequenceMatcher(None, str1, str2)
    str1_html = []
    str2_html = []
    
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            str1_html.append(str1[i1:i2])
            str2_html.append(str2[j1:j2])
        elif op == 'insert':
            str2_html.append(f"<span style='background-color: #CCFFCC'>{str2[j1:j2]}</span>")
        elif op == 'delete':
            str1_html.append(f"<span style='background-color: #FFCCCC'>{str1[i1:i2]}</span>")
        elif op == 'replace':
            str1_html.append(f"<span style='background-color: #FFCCCC'>{str1[i1:i2]}</span>")
            str2_html.append(f"<span style='background-color: #CCFFCC'>{str2[j1:j2]}</span>")
    
    return ''.join(str1_html), ''.join(str2_html)

def confronta_record(record1: pd.Series, record2: pd.Series) -> Dict[str, Tuple[str, str, bool]]:
    """
    Confronta due record e restituisce le differenze formattate.
    
    Args:
        record1: Primo record
        record2: Secondo record
        
    Returns:
        Dict[str, Tuple[str, str, bool]]: Dizionario con le differenze evidenziate per ogni campo
                                        e un flag che indica se il campo è diverso
    """
    differenze = {}
    
    for campo in record1.index:
        # Converti entrambi i valori in stringhe per confronto
        val1 = str(record1[campo]) if pd.notna(record1[campo]) else ""
        val2 = str(record2[campo]) if pd.notna(record2[campo]) else ""
        
        # Verifica se i campi sono diversi
        if val1 != val2:
            val1_html, val2_html = evidenzia_differenze(val1, val2)
            differenze[campo] = (val1_html, val2_html, True)
        else:
            differenze[campo] = (val1, val2, False)
    
    return differenze

def genera_report_duplicati(df: pd.DataFrame, gruppi_duplicati: Dict[str, pd.DataFrame]) -> str:
    """
    Genera un report di testo con i dettagli dei potenziali record duplicati.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        gruppi_duplicati: Dizionario con gruppi di potenziali duplicati
        
    Returns:
        str: Testo del report
    """
    if not gruppi_duplicati:
        return "Non sono stati trovati record potenzialmente duplicati."
    
    linee_report = []
    linee_report.append("REPORT DUPLICATI NEL CALENDARIO")
    linee_report.append("=============================")
    linee_report.append(f"Data generazione: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")
    linee_report.append(f"Numero totale di record analizzati: {len(df)}")
    linee_report.append(f"Gruppi di potenziali duplicati trovati: {len(gruppi_duplicati)}")
    linee_report.append("")
    
    for i, (gruppo_key, gruppo_df) in enumerate(gruppi_duplicati.items(), 1):
        # Estrai le informazioni dal gruppo
        parts = gruppo_key.split('|')
        if len(parts) >= 3:
            data, docente, orario = parts[:3]
        else:
            data, docente, orario = "N/D", "N/D", "N/D"
        
        linee_report.append(f"GRUPPO {i}: Data: {data}, Docente: {docente}, Orario: {orario}")
        linee_report.append("-" * 80)
        linee_report.append(f"Numero di record nel gruppo: {len(gruppo_df)}")
        
        # Analizza le differenze tra i record
        if len(gruppo_df) == 2:
            # Confronto tra due record
            record1 = gruppo_df.iloc[0]
            record2 = gruppo_df.iloc[1]
            
            linee_report.append("\nDifferenze tra i record:")
            
            for campo in record1.index:
                val1 = str(record1[campo]) if pd.notna(record1[campo]) else ""
                val2 = str(record2[campo]) if pd.notna(record2[campo]) else ""
                
                if val1 != val2:
                    linee_report.append(f"  Campo '{campo}':")
                    linee_report.append(f"    Record 1: {val1}")
                    linee_report.append(f"    Record 2: {val2}")
        else:
            # Confronto multiplo quando ci sono più di 2 record
            # Trova i campi che hanno almeno una differenza nel gruppo
            campi_diversi = set()
            for i in range(len(gruppo_df)):
                for j in range(i+1, len(gruppo_df)):
                    record1 = gruppo_df.iloc[i]
                    record2 = gruppo_df.iloc[j]
                    
                    for campo in record1.index:
                        val1 = str(record1[campo]) if pd.notna(record1[campo]) else ""
                        val2 = str(record2[campo]) if pd.notna(record2[campo]) else ""
                        
                        if val1 != val2:
                            campi_diversi.add(campo)
            
            if campi_diversi:
                linee_report.append("\nCampi che differiscono tra i record:")
                for campo in sorted(campi_diversi):
                    linee_report.append(f"  Campo '{campo}':")
                    
                    for idx, row in gruppo_df.iterrows():
                        val = str(row[campo]) if pd.notna(row[campo]) else "N/A"
                        linee_report.append(f"    Record {idx}: {val}")
            else:
                linee_report.append("\nNessuna differenza significativa rilevata nei campi.")
        
        # Aggiungi una riga vuota per separare i gruppi
        linee_report.append("\n" + "=" * 80 + "\n")
    
    return "\n".join(linee_report)


def mostra_confronto_duplicati(df: pd.DataFrame):
    """
    Interfaccia Streamlit per confrontare e gestire potenziali record duplicati.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
    """
    st.header("🔍 Confronto e Gestione Duplicati")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per il confronto dei duplicati")
        return
    
    # Impostazioni di ricerca duplicati
    st.subheader("Impostazioni ricerca duplicati")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        metodo_ricerca = st.selectbox(
            "Metodo di ricerca:",
            options=["standard", "avanzato", "completo"],
            format_func=lambda x: {
                "standard": "Standard (Data/Docente/Orario identici)",
                "avanzato": "Avanzato (cerca anche piccole differenze)",
                "completo": "Completo (combina entrambi i metodi)"
            }[x],
            help="Scegli come cercare i potenziali duplicati"
        )
    
    with col2:
        st.markdown("""
        - **Standard**: Trova record con stessa data, docente e orario
        - **Avanzato**: Cerca anche record con piccole differenze (date vicine, orari simili)
        - **Completo**: Applica entrambe le metodologie per un'analisi più approfondita
        """)
    
    # Trova i potenziali duplicati con il metodo selezionato
    gruppi_duplicati = trova_potenziali_duplicati(df, metodo=metodo_ricerca)
    
    # Se non ci sono duplicati
    if not gruppi_duplicati:
        st.success("🎉 Non sono stati trovati record potenzialmente duplicati")
        return
    
    # Suddividi i gruppi per tipo di rilevamento
    gruppi_standard = {k: v for k, v in gruppi_duplicati.items() if k.startswith('standard|')}
    gruppi_avanzati = {k: v for k, v in gruppi_duplicati.items() if k.startswith('avanzato|')}
    
    # Mostra conteggi per tipo
    if metodo_ricerca == "completo":
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"Trovati {len(gruppi_standard)} gruppi con metodo standard")
        with col2:
            st.info(f"Trovati {len(gruppi_avanzati)} gruppi con metodo avanzato")
    else:
        st.info(f"Trovati {len(gruppi_duplicati)} gruppi di potenziali record duplicati")
    
    # Pulsanti per le azioni disponibili
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Pulsante per aggiornare l'analisi dei duplicati
        if st.button("🔄 Aggiorna analisi", 
                    help="Esegui nuovamente l'analisi per verificare la presenza di duplicati",
                    type="primary"):
            st.success("Analisi duplicati aggiornata")
            st.rerun()
    
    with col2:
        report_text = genera_report_duplicati(df, gruppi_duplicati)
        st.download_button(
            label="📄 Scarica Report",
            data=report_text,
            file_name=f"report_duplicati_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            help="Scarica un report dettagliato di tutti i potenziali duplicati"
        )
    
    # Crea una lista di gruppi per la selezione
    gruppi_keys = list(gruppi_duplicati.keys())
    
    # Mostra un selettore per i gruppi di duplicati
    gruppo_selezionato = None
    
    # Formatta le chiavi per renderle più leggibili
    formatted_keys = []
    for k in gruppi_keys:
        # Determina se è un gruppo standard o avanzato
        tipo = "Standard"
        if k.startswith("avanzato|"):
            tipo = "Avanzato"
        
        # Rimuove il prefisso del tipo
        parts = k.split('|')[1:]
        
        if len(parts) >= 3:
            # Per gruppi standard
            if '~' not in k:
                formatted_keys.append(f"[{tipo}] Data: {parts[0]}, Docente: {parts[1]}, Orario: {parts[2]}")
            # Per gruppi avanzati con date simili
            elif '~' in parts[0]:
                date = parts[0].split('~')
                formatted_keys.append(f"[{tipo}] Date: {date[0]}~{date[1]}, Docente: {parts[1]}")
            # Per gruppi avanzati con orari simili
            elif '~' in parts[1]:
                orari = parts[1].split('~')
                formatted_keys.append(f"[{tipo}] Data: {parts[0]}, Orari: {orari[0]}~{orari[1]}, {parts[2][:30]}")
            else:
                formatted_keys.append(f"[{tipo}] {' | '.join(parts)}")
        else:
            formatted_keys.append(f"[{tipo}] {' | '.join(parts)}")
    
    # Crea un mapping tra le chiavi formattate e quelle originali
    key_mapping = dict(zip(formatted_keys, gruppi_keys))
    
    # Seleziona il gruppo da visualizzare
    selected_formatted_key = st.selectbox(
        "Seleziona un gruppo di potenziali duplicati da esaminare:",
        [""] + formatted_keys
    )
    
    if selected_formatted_key:
        gruppo_selezionato = key_mapping[selected_formatted_key]
        selected_df = gruppi_duplicati[gruppo_selezionato]
        
        st.subheader(f"Confronto dei record duplicati ({len(selected_df)} record)")
        
        # Aggiunta tabs per separare le azioni di Eliminazione e Merge
        tab_elimina, tab_merge = st.tabs(["🗑️ Elimina record", "🔄 Unisci record"])
        
        # TAB 1: ELIMINAZIONE DEI RECORD
        with tab_elimina:
            # Permetti all'utente di scegliere quali record eliminare
            with st.form(key="eliminate_duplicates_form"):
                st.write("Seleziona i record da eliminare:")
                
                # Crea un checkbox per ogni record
                to_delete = []
                for idx, row in selected_df.iterrows():
                    # Mostra un riassunto del record
                    data_val = row['Data'].strftime('%d/%m/%Y') if hasattr(row['Data'], 'strftime') else row['Data']
                    docente_val = row['Docente']
                    orario_val = row['Orario']
                    denominazione_val = row['Denominazione Insegnamento'] if 'Denominazione Insegnamento' in row else "N/A"
                    
                    checkbox_label = f"{data_val} - {docente_val} - {orario_val} - {denominazione_val}"
                    deleted = st.checkbox(f"Elimina: {checkbox_label}", key=f"del_{idx}")
                    
                    if deleted:
                        to_delete.append(idx)
                
                # Pulsante per confermare l'eliminazione
                submit = st.form_submit_button("Elimina Record Selezionati")
                
                if submit and to_delete:
                    # Log dell'operazione
                    logger.info(f"Eliminazione di {len(to_delete)} record duplicati dal gruppo {gruppo_selezionato}")
                    
                    # Elimina i record selezionati
                    df_aggiornato = df.drop(to_delete)
                    
                    # Aggiorna il dataframe nel session state
                    st.session_state['calendario_df'] = df_aggiornato
                    
                    # Aggiorna i gruppi di duplicati
                    gruppi_duplicati = trova_potenziali_duplicati(df_aggiornato)
                    
                    st.success(f"Eliminati {len(to_delete)} record duplicati")
                    st.rerun()
        
        # TAB 2: MERGE DEI RECORD
        with tab_merge:
            st.write("Unisci i record duplicati in un unico record combinato:")
            
            # Mostra opzioni per il merge
            merge_option = st.radio(
                "Modalità di unione:",
                ["Automatica", "Selettiva"],
                help="Automatica: combina automaticamente i valori migliori dai record. Selettiva: permette di scegliere manualmente quale valore mantenere per ciascun campo."
            )
            
            # Unione automatica
            if merge_option == "Automatica":
                with st.form(key="merge_auto_form"):
                    st.write("L'unione automatica combinerà i record utilizzando:")
                    st.write("- I valori non vuoti per campi come Aula, Link Teams, Note, ecc.")
                    st.write("- Il valore più completo (più lungo) quando ci sono più opzioni")
                    st.write("- Il valore massimo per campi numerici come CFU")
                    
                    # Pulsante per confermare il merge automatico
                    auto_merge_submit = st.form_submit_button("Unisci Record Automaticamente")
                    
                    if auto_merge_submit:
                        # Esegui il merge automatico
                        record_unito, indici_da_eliminare = merge_duplicati(selected_df)
                        
                        if record_unito is not None:
                            # Applica il merge al dataframe originale
                            df_aggiornato = applica_merge(df, selected_df.index.tolist(), record_unito)
                            
                            # Aggiorna il dataframe nel session state
                            st.session_state['calendario_df'] = df_aggiornato
                            
                            st.success(f"Uniti {len(selected_df)} record duplicati in un unico record")
                            
                            # Visualizza anteprima del record unito
                            with st.expander("Dettagli del record unito"):
                                # Formatta alcune colonne chiave per visualizzazione
                                data_val = record_unito['Data'].strftime('%d/%m/%Y') if hasattr(record_unito['Data'], 'strftime') else record_unito['Data']
                                
                                st.markdown(f"**Data**: {data_val}")
                                st.markdown(f"**Docente**: {record_unito['Docente']}")
                                st.markdown(f"**Orario**: {record_unito['Orario']}")
                                st.markdown(f"**Denominazione Insegnamento**: {record_unito.get('Denominazione Insegnamento', 'N/A')}")
                                
                                if 'Aula' in record_unito:
                                    st.markdown(f"**Aula**: {record_unito['Aula']}")
                                
                                if 'CFU' in record_unito:
                                    st.markdown(f"**CFU**: {record_unito['CFU']}")
                            
                            # Aggiorna la UI
                            st.rerun()
            
            # Unione selettiva
            else:
                # Prepara i valori disponibili per ogni campo
                valori_per_campo = scegli_valori_per_merge(selected_df)
                
                if not valori_per_campo:
                    st.info("Non ci sono campi con valori diversi da unire.")
                else:
                    with st.form(key="merge_selective_form"):
                        st.write("Seleziona quale valore mantenere per ogni campo:")
                        
                        # Per ogni campo con valori diversi, mostra un radio button per scegliere
                        selezioni = {}
                        
                        for campo, valori in valori_per_campo.items():
                            st.write(f"**{campo}**")
                            
                            # Crea opzioni per questo campo
                            options = []
                            labels = []
                            
                            for idx, val in valori.items():
                                if val:  # Se il valore non è vuoto
                                    options.append(idx)
                                    labels.append(f"Record {idx}: {val}")
                            
                            if options:
                                selected_idx = st.radio(
                                    f"Seleziona il valore per '{campo}'",
                                    options=range(len(options)),
                                    format_func=lambda i: labels[i],
                                    key=f"sel_{campo}"
                                )
                                selezioni[campo] = options[selected_idx]
                        
                        # Pulsante per confermare il merge selettivo
                        selective_merge_submit = st.form_submit_button("Unisci Record con Valori Selezionati")
                        
                        if selective_merge_submit:
                            # Esegui il merge selettivo
                            record_unito = merge_con_selezione(selected_df, selezioni)
                            
                            if record_unito is not None:
                                # Applica il merge al dataframe originale
                                df_aggiornato = applica_merge(df, selected_df.index.tolist(), record_unito)
                                
                                # Aggiorna il dataframe nel session state
                                st.session_state['calendario_df'] = df_aggiornato
                                
                                st.success(f"Uniti {len(selected_df)} record duplicati in un unico record con i valori selezionati")
                                
                                # Aggiorna la UI
                                st.rerun()
        
        # Mostra i dettagli delle differenze tra i record
        st.subheader("Dettaglio delle differenze")
        
        if len(selected_df) == 2:
            # Confronto diretto tra due record
            record1 = selected_df.iloc[0]
            record2 = selected_df.iloc[1]
            
            differenze = confronta_record(record1, record2)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("Record 1")
            with col2:
                st.write("Record 2")
            
            for campo, (val1, val2, diverso) in differenze.items():
                if diverso:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**{campo}**: {val1}", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"**{campo}**: {val2}", unsafe_allow_html=True)
        else:
            # Confronto multiplo quando ci sono più di 2 record
            st.write("Confronto campi che differiscono tra i record:")
            
            # Trova i campi che hanno almeno una differenza nel gruppo
            campi_diversi = set()
            for i in range(len(selected_df)):
                for j in range(i+1, len(selected_df)):
                    record1 = selected_df.iloc[i]
                    record2 = selected_df.iloc[j]
                    
                    for campo in record1.index:
                        val1 = str(record1[campo]) if pd.notna(record1[campo]) else ""
                        val2 = str(record2[campo]) if pd.notna(record2[campo]) else ""
                        
                        if val1 != val2:
                            campi_diversi.add(campo)
            
            # Mostra solo i campi che hanno differenze
            if campi_diversi:
                for campo in campi_diversi:
                    st.write(f"**Campo: {campo}**")
                    
                    for idx, row in selected_df.iterrows():
                        val = str(row[campo]) if pd.notna(row[campo]) else "N/A"
                        st.write(f"Record {idx}: {val}")
                    
                    st.write("---")
            else:
                st.write("Nessuna differenza significativa rilevata nei campi.")

def elimina_duplicati_esatti(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elimina i duplicati esattamente identici dal DataFrame.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        
    Returns:
        pd.DataFrame: DataFrame ripulito dai duplicati esatti
    """
    if df is None or df.empty:
        return df
    
    # Conta i duplicati prima dell'eliminazione
    num_righe_prima = len(df)
    
    # Elimina i duplicati esattamente identici
    df_unique = df.drop_duplicates()
    
    # Conta quanti duplicati sono stati eliminati
    num_duplicati = num_righe_prima - len(df_unique)
    
    if num_duplicati > 0:
        logger.info(f"Eliminati {num_duplicati} record duplicati esatti")
    
    return df_unique


def analizza_cfu_per_classe(df: pd.DataFrame, target_cfu: float = 16.0) -> pd.DataFrame:
    """
    Analizza il totale dei CFU per ogni classe di concorso, identificando quelle che
    hanno più o meno CFU rispetto al target appropriato.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        target_cfu: Valore target di default per i CFU per classe di concorso (default: 16.0)
        
    Returns:
        pd.DataFrame: DataFrame con l'analisi dei CFU per classe di concorso
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # Crea una copia del dataframe per le operazioni
    working_df = df.copy()
    
    # Filtra escludendo i record con classi di concorso multiple (es. A001-A007)
    working_df = _filtra_classi_multiple(working_df)
    
    # Pulisci e standardizza i valori dei CFU
    if 'CFU_numeric' not in working_df.columns:
        working_df['CFU_clean'] = working_df['CFU'].astype(str).str.replace(',', '.')
        working_df['CFU_clean'] = working_df['CFU_clean'].replace('nan', '0')
        working_df['CFU_numeric'] = pd.to_numeric(working_df['CFU_clean'], errors='coerce').fillna(0)
    
    # Calcola i CFU totali per ogni classe di concorso
    cfu_per_classe = working_df.groupby('Insegnamento comune')['CFU_numeric'].sum().reset_index()
    
    # Aggiungi informazioni sul tipo di classe (trasversale o regolare)
    cfu_per_classe['Target_CFU'] = target_cfu
    
    # Identifica le classi trasversali (che hanno target 24 CFU)
    # Lista delle possibili classi trasversali (potrebbe essere necessario adattarla)
    classi_trasversali = ['Trasversale', 'Insegnamenti trasversali', 'Obiettivi trasversali']
    
    # Flag per classi trasversali
    cfu_per_classe['Is_Trasversale'] = cfu_per_classe['Insegnamento comune'].isin(classi_trasversali)
    
    # Se il nome della classe contiene "trasvers" (case insensitive), considerala trasversale
    cfu_per_classe['Is_Trasversale'] = cfu_per_classe['Is_Trasversale'] | cfu_per_classe['Insegnamento comune'].str.lower().str.contains('trasvers', na=False)
    
    # Imposta il target appropriato basato sul tipo di classe
    cfu_per_classe.loc[cfu_per_classe['Is_Trasversale'], 'Target_CFU'] = 24.0
    
    # Calcola la differenza rispetto al target appropriato per ciascuna classe
    cfu_per_classe['Differenza'] = cfu_per_classe['CFU_numeric'] - cfu_per_classe['Target_CFU']
    
    # Aggiungi colonne per identificare facilmente le anomalie
    cfu_per_classe['Status'] = 'OK'
    cfu_per_classe.loc[cfu_per_classe['Differenza'] > 0.1, 'Status'] = 'ECCESSO'
    cfu_per_classe.loc[cfu_per_classe['Differenza'] < -0.1, 'Status'] = 'DIFETTO'
    
    # Calcola il numero di lezioni per classe
    lezioni_per_classe = working_df.groupby('Insegnamento comune').size().reset_index(name='Num_Lezioni')
    cfu_per_classe = pd.merge(cfu_per_classe, lezioni_per_classe, on='Insegnamento comune', how='left')
    
    # Ordina per stato (prima le anomalie) e poi per classe
    cfu_per_classe['Status_Ord'] = cfu_per_classe['Status'].map({'ECCESSO': 0, 'DIFETTO': 1, 'OK': 2})
    cfu_per_classe = cfu_per_classe.sort_values(['Status_Ord', 'Insegnamento comune'])
    cfu_per_classe = cfu_per_classe.drop('Status_Ord', axis=1)
    
    # Arrotonda i valori numerici per una migliore leggibilità
    cfu_per_classe['CFU_numeric'] = cfu_per_classe['CFU_numeric'].round(1)
    cfu_per_classe['Differenza'] = cfu_per_classe['Differenza'].round(1)
    
    return cfu_per_classe


def analizza_classi_lingue(df: pd.DataFrame, target_cfu: float = 16.0) -> pd.DataFrame:
    """
    Analisi specifica per le classi di lingue, che potrebbero avere più problemi di duplicati.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        target_cfu: Valore target dei CFU per ogni classe di concorso (default: 16.0)
        
    Returns:
        pd.DataFrame: DataFrame con l'analisi dettagliata per le classi di lingue
    """
    if df is None or df.empty:
        return pd.DataFrame()
        
    # Crea una copia del dataframe per le operazioni
    working_df = df.copy()
    
    # Filtra escludendo i record con classi di concorso multiple (es. A001-A007)
    working_df = _filtra_classi_multiple(working_df)
    
    # Verifica se la colonna Dipartimento esiste
    if 'Dipartimento' not in working_df.columns:
        return pd.DataFrame()
    
    # Filtra per il dipartimento di lingue
    df_lingue = working_df[working_df['Dipartimento'].str.lower().str.contains('lingue', na=False)]
    
    if df_lingue.empty:
        return pd.DataFrame()
    
    # Prepara il dataframe per l'analisi
    if 'CFU_numeric' not in df_lingue.columns:
        df_lingue['CFU_clean'] = df_lingue['CFU'].astype(str).str.replace(',', '.')
        df_lingue['CFU_clean'] = df_lingue['CFU_clean'].replace('nan', '0')
        df_lingue['CFU_numeric'] = pd.to_numeric(df_lingue['CFU_clean'], errors='coerce').fillna(0)
    
    # Ottieni le classi di concorso di lingue
    classi_lingue = df_lingue['Insegnamento comune'].unique()
    
    # Analisi per ogni classe di lingua
    risultati = []
    
    for classe in classi_lingue:
        # Filtra per classe
        df_classe = df_lingue[df_lingue['Insegnamento comune'] == classe]
        
        # Calcola i CFU totali per la classe
        cfu_totali = df_classe['CFU_numeric'].sum()
        
        # Calcola il numero di lezioni
        num_lezioni = len(df_classe)
        
        # Verifica se ci sono duplicati potenziali
        # Raggruppa per data e orario per trovare lezioni nello stesso giorno/ora
        potenziali_duplicati = []
        for (data, orario), gruppo in df_classe.groupby(['Data', 'Orario']):
            if len(gruppo) > 1:
                potenziali_duplicati.append({
                    'Data': data,
                    'Orario': orario,
                    'Num_Duplicati': len(gruppo),
                    'Docenti': ', '.join(gruppo['Docente'].unique()),
                    'Insegnamenti': ', '.join(gruppo['Denominazione Insegnamento'].unique())
                })
        
        # Calcola la differenza rispetto al target
        differenza = cfu_totali - target_cfu
        
        # Determina lo status
        if abs(differenza) <= 0.1:
            status = "OK"
        elif differenza > 0.1:
            status = "ECCESSO"
        else:
            status = "DIFETTO"
        
        # Stima potenziali problemi
        problemi = []
        if status == "ECCESSO" and len(potenziali_duplicati) > 0:
            problemi.append("Possibili duplicati")
        elif status == "DIFETTO":
            problemi.append("Possibili lezioni mancanti")
        
        # Aggiungi al risultato
        risultati.append({
            'Classe': classe,
            'CFU_Totali': round(cfu_totali, 1),
            'Num_Lezioni': num_lezioni,
            'Differenza': round(differenza, 1),
            'Status': status,
            'Potenziali_Duplicati': len(potenziali_duplicati),
            'Dettaglio_Duplicati': potenziali_duplicati,
            'Problemi': ', '.join(problemi)
        })
    
    # Crea DataFrame con i risultati
    risultati_df = pd.DataFrame(risultati)
    
    # Ordina per status (prima quelli con problemi) e poi per classe
    if not risultati_df.empty:
        risultati_df['Status_Ord'] = risultati_df['Status'].map({'ECCESSO': 0, 'DIFETTO': 1, 'OK': 2})
        risultati_df = risultati_df.sort_values(['Status_Ord', 'Classe'])
        risultati_df = risultati_df.drop('Status_Ord', axis=1)
    
    return risultati_df


def mostra_analisi_cfu(df: pd.DataFrame, target_cfu: float = 16.0):
    """
    Visualizza l'analisi dei CFU per classe di concorso in un'interfaccia Streamlit.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        target_cfu: Valore target dei CFU per ogni classe di concorso (default: 16.0)
    """
    st.subheader("📊 Analisi dei CFU per Classe di Concorso")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per l'analisi dei CFU")
        return
    
    # Esegui l'analisi dei CFU
    cfu_analisi = analizza_cfu_per_classe(df, target_cfu)
    
    # Crea un conteggio delle classi per stato
    status_counts = cfu_analisi['Status'].value_counts().to_dict()
    num_eccesso = status_counts.get('ECCESSO', 0)
    num_difetto = status_counts.get('DIFETTO', 0) 
    num_ok = status_counts.get('OK', 0)
    
    # Mostra riepilogo
    st.write(f"Target CFU per classe: **{target_cfu}**")
    
    # Mostra metriche in tre colonne
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="✅ Classi con CFU corretti", value=num_ok)
    with col2:
        st.metric(label="⚠️ Classi con CFU in eccesso", value=num_eccesso)
    with col3:
        st.metric(label="⚠️ Classi con CFU in difetto", value=num_difetto)
    
    # Filtraggio per stato
    st.write("### Filtra per stato")
    stati = ["Tutti", "ECCESSO", "DIFETTO", "OK"]
    stato_selezionato = st.selectbox("Mostra classi con stato:", stati)
    
    if stato_selezionato != "Tutti":
        filtered_df = cfu_analisi[cfu_analisi['Status'] == stato_selezionato]
    else:
        filtered_df = cfu_analisi
    
    # Filtraggio per dipartimento specifico di lingue
    filtered_df_lingue = None
    
    # Verifica se esiste la colonna Dipartimento
    if 'Dipartimento' in df.columns:
        dipartimenti = ["Tutti"] + sorted(df['Dipartimento'].dropna().unique().tolist())
        dipartimento_selezionato = st.selectbox("Filtra per dipartimento:", dipartimenti)
        
        if dipartimento_selezionato != "Tutti":
            # Prima ottieni le classi del dipartimento
            classi_dipartimento = df[df['Dipartimento'] == dipartimento_selezionato]['Insegnamento comune'].unique()
            # Poi filtra l'analisi CFU per quelle classi
            filtered_df = filtered_df[filtered_df['Insegnamento comune'].isin(classi_dipartimento)]
            
            # Evidenzia specificamente il dipartimento di lingue
            if "lingue" in dipartimento_selezionato.lower():
                filtered_df_lingue = filtered_df.copy()
                
                # Sezione specifica per analisi dettagliata classi di lingue
                st.markdown("---")
                st.subheader("🌐 Analisi Dettagliata Classi di Lingue")
                
                # Esegui l'analisi specifica per le classi di lingue
                analisi_lingue = analizza_classi_lingue(df, target_cfu)
                
                if not analisi_lingue.empty:
                    # Mostra il numero di classi con problemi
                    classi_problematiche = analisi_lingue[analisi_lingue['Status'] != 'OK']
                    
                    if not classi_problematiche.empty:
                        st.warning(f"⚠️ Trovate {len(classi_problematiche)} classi di lingue con CFU non allineati al target di {target_cfu}.")
                        
                        # Mostra la tabella con le classi problematiche
                        st.write("### Classi con potenziali problemi")
                        
                        # Rinomina colonne per migliore leggibilità
                        display_df = classi_problematiche.copy()
                        display_df = display_df.rename(columns={
                            'Classe': 'Classe di Concorso',
                            'CFU_Totali': 'CFU Totali',
                            'Num_Lezioni': 'Numero Lezioni',
                            'Potenziali_Duplicati': 'Potenziali Duplicati'
                        })
                        
                        # Rimuovi la colonna con i dettagli dei duplicati dalla visualizzazione
                        if 'Dettaglio_Duplicati' in display_df.columns:
                            display_df = display_df.drop('Dettaglio_Duplicati', axis=1)
                        
                        # Visualizza la tabella
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Aggiungi dettaglio per ogni classe problematica
                        for _, row in classi_problematiche.iterrows():
                            with st.expander(f"Dettaglio: {row['Classe']} - {row['Status']} ({row['CFU_Totali']} CFU, {row['Differenza']} rispetto al target)"):
                                st.write(f"**Classe di Concorso:** {row['Classe']}")
                                st.write(f"**CFU Totali:** {row['CFU_Totali']}")
                                st.write(f"**Numero Lezioni:** {row['Num_Lezioni']}")
                                st.write(f"**Differenza dal target:** {row['Differenza']}")
                                st.write(f"**Problemi riscontrati:** {row['Problemi'] if row['Problemi'] else 'Nessuno specifico'}")
                                
                                # Mostra dettaglio dei potenziali duplicati
                                if row['Potenziali_Duplicati'] > 0:
                                    st.write(f"**Potenziali duplicati trovati:** {row['Potenziali_Duplicati']}")
                                    st.write("#### Dettaglio:")
                                    
                                    for i, dup in enumerate(row['Dettaglio_Duplicati'], 1):
                                        st.markdown(f"""
                                        **Gruppo {i}:**
                                        - **Data:** {dup['Data']}
                                        - **Orario:** {dup['Orario']}
                                        - **Numero lezioni:** {dup['Num_Duplicati']}
                                        - **Docenti:** {dup['Docenti']}
                                        - **Insegnamenti:** {dup['Insegnamenti']}
                                        """)
                                
                                # Aggiungi azione di ricerca duplicati avanzata per questa classe
                                st.button(
                                    f"🔍 Analizza duplicati per {row['Classe']}", 
                                    key=f"analizza_{row['Classe']}", 
                                    help=f"Esegui un'analisi approfondita dei potenziali duplicati per la classe {row['Classe']}"
                                )
                    else:
                        st.success("✅ Tutte le classi di lingue hanno i CFU allineati al target.")
                else:
                    st.info("Nessuna classe di lingue trovata nei dati.")
                
                st.markdown("---")
    
    # Mostra tabella con l'analisi
    if not filtered_df.empty:
        st.write(f"### Analisi CFU ({len(filtered_df)} classi)")
        
        # Rinomina le colonne per migliore leggibilità
        display_df = filtered_df.rename(columns={
            'Insegnamento comune': 'Classe di Concorso',
            'CFU_numeric': 'CFU Totali',
            'Num_Lezioni': 'Numero Lezioni'
        })
        
        # Aggiungi formattazione condizionale
        def highlight_status(s):
            return ['background-color: #ffcccb' if x == 'ECCESSO' 
                    else 'background-color: #ffffcc' if x == 'DIFETTO' 
                    else 'background-color: #ccffcc' for x in s]
        
        # Mostra tabella con highlight
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Classe di Concorso": st.column_config.TextColumn("Classe di Concorso"),
                "CFU Totali": st.column_config.NumberColumn("CFU Totali", format="%.1f"),
                "Differenza": st.column_config.NumberColumn("Differenza", format="%.1f"),
                "Numero Lezioni": st.column_config.NumberColumn("Numero Lezioni"),
                "Status": st.column_config.TextColumn("Status")
            }
        )
        
        # Scarica report analisi CFU
        st.download_button(
            label="📄 Scarica report analisi CFU",
            data=filtered_df.to_csv(index=False),
            file_name=f"analisi_cfu_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
        
        # Avviso speciale per le classi di lingue
        if filtered_df_lingue is not None and not filtered_df_lingue.empty:
            problemi_lingue = filtered_df_lingue[(filtered_df_lingue['Status'] == 'ECCESSO') | 
                                                (filtered_df_lingue['Status'] == 'DIFETTO')]
            if not problemi_lingue.empty:
                st.warning(f"⚠️ Trovate {len(problemi_lingue)} classi del dipartimento di lingue con CFU non allineati al target di {target_cfu}. Questi potrebbero contenere duplicati nascosti o lezioni mancanti.")
    else:
        st.info("Nessuna classe di concorso trovata con i filtri selezionati")
    
    return cfu_analisi
