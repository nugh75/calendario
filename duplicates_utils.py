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
import re
from log_utils import logger
from merge_utils import merge_duplicati, applica_merge, scegli_valori_per_merge, merge_con_selezione
from cfu_riepilogo_utils import _filtra_classi_multiple

def normalizza_stringa(testo: str) -> str:
    """
    Normalizza una stringa rimuovendo spazi in eccesso all'inizio, alla fine e tra parole.
    
    Args:
        testo: Testo da normalizzare
        
    Returns:
        str: Stringa normalizzata
    """
    if not isinstance(testo, str):
        # Se non è una stringa, converti e poi normalizza
        testo = str(testo) if pd.notna(testo) else ""
    
    # Rimuovi spazi all'inizio e alla fine
    testo = testo.strip()
    # Sostituisci più spazi consecutivi con uno solo
    testo = re.sub(r'\s+', ' ', testo)
    return testo

def separa_nome_cognome(nome_completo: str) -> Tuple[List[str], List[str]]:
    """
    Separa un nome completo in possibili nomi e cognomi.
    
    Args:
        nome_completo: Stringa contenente il nome completo (es. "Mario Rossi" o "Rossi Mario")
        
    Returns:
        Tuple[List[str], List[str]]: Tuple contenente le liste di possibili nomi e cognomi
    """
    # Pulisci e standardizza la stringa
    nome_completo = nome_completo.strip()
    # Rimuovi titoli comuni
    nome_completo = re.sub(r'(Prof\.|Dott\.|Dr\.|Ing\.|Arch\.|Avv\.)\s*', '', nome_completo, flags=re.IGNORECASE)
    
    # Dividi in parole
    parole = nome_completo.split()
    
    # Se c'è una sola parola, è probabilmente un cognome
    if len(parole) == 1:
        return ([], parole)
    
    # Se ci sono due parole, potrebbero essere nome e cognome in qualsiasi ordine
    if len(parole) == 2:
        return ([parole[0]], [parole[1]])
    
    # Se ci sono più di due parole, consideriamo diverse possibilità
    # Caso più comune in Italia: Nome [Secondo nome] Cognome
    nomi = parole[:-1]
    cognomi = [parole[-1]]
    
    return (nomi, cognomi)

def errore_ortografico_possibile(parola1: str, parola2: str, soglia: float = 0.8) -> bool:
    """
    Verifica se due parole potrebbero contenere errori ortografici l'una rispetto all'altra.
    
    Args:
        parola1: Prima parola
        parola2: Seconda parola
        soglia: Soglia di similitudine (0-1) per considerare le parole simili
        
    Returns:
        bool: True se le parole sono sufficientemente simili da suggerire un errore ortografico
    """
    # Se sono identiche, non c'è errore ortografico
    if parola1 == parola2:
        return False
    
    # Se una delle due è vuota, non possiamo confrontare
    if not parola1 or not parola2:
        return False
    
    # Calcola la distanza di Levenshtein normalizzata
    similarity = difflib.SequenceMatcher(None, parola1.lower(), parola2.lower()).ratio()
    
    # Se la similitudine è alta ma non sono identiche, potrebbe essere un errore ortografico
    return similarity >= soglia and similarity < 1.0

def sono_stesso_docente(docente1: str, docente2: str) -> bool:
    """
    Verifica se due stringhe di docenti potrebbero rappresentare la stessa persona con nome e cognome invertiti.
    
    Args:
        docente1: Primo nome docente
        docente2: Secondo nome docente
        
    Returns:
        bool: True se potrebbero essere la stessa persona, False altrimenti
    """
    # Se sono identici, sono ovviamente la stessa persona
    if docente1 == docente2:
        return True
    
    # Se uno è vuoto, non sono la stessa persona
    if not docente1 or not docente2:
        return False
    
    # Pulisci e standardizza le stringhe
    docente1 = docente1.strip().lower()
    docente2 = docente2.strip().lower()
    
    # Separa i possibili nomi e cognomi
    nomi1, cognomi1 = separa_nome_cognome(docente1)
    nomi2, cognomi2 = separa_nome_cognome(docente2)
    
    # Se uno dei nomi o cognomi è vuoto, non possiamo verificare l'inversione
    if not nomi1 or not cognomi1 or not nomi2 or not cognomi2:
        return False
    
    # Verifica se c'è corrispondenza incrociata (nome1 = cognome2 e cognome1 = nome2)
    for nome1 in nomi1:
        for cognome1 in cognomi1:
            for nome2 in nomi2:
                for cognome2 in cognomi2:
                    if (nome1.lower() == cognome2.lower() and cognome1.lower() == nome2.lower()):
                        return True
    
    # Verifica anche la somiglianza dei nomi/cognomi per gestire piccoli errori di battitura
    for nome1 in nomi1:
        for cognome2 in cognomi2:
            if difflib.SequenceMatcher(None, nome1.lower(), cognome2.lower()).ratio() > 0.8:
                for cognome1 in cognomi1:
                    for nome2 in nomi2:
                        if difflib.SequenceMatcher(None, cognome1.lower(), nome2.lower()).ratio() > 0.8:
                            return True
    
    return False

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
        # Normalizza i campi per rimuovere spazi in eccesso e creare una chiave di raggruppamento
        working_df['Docente_norm'] = working_df['Docente'].apply(lambda x: normalizza_stringa(x))
        working_df['Orario_norm'] = working_df['Orario'].apply(lambda x: normalizza_stringa(x))
        
        # Crea una chiave di raggruppamento con i valori normalizzati
        working_df['gruppo_key'] = working_df['Data_str'] + '|' + working_df['Docente_norm'] + '|' + working_df['Orario_norm']
        
        # Trova gruppi con più di un record
        gruppi = working_df.groupby('gruppo_key')
        gruppi_duplicati_standard = {k: g for k, g in gruppi if len(g) > 1}
        
        # Aggiungi un prefisso al gruppo key per identificare il metodo
        gruppi_duplicati.update({f"standard|{k}": g for k, g in gruppi_duplicati_standard.items()})
        
        # Cerca anche record che differiscono solo per spazi extra
        # Creiamo un altro gruppo dove cerchiamo record unici che hanno campi identici dopo la normalizzazione
        # ma che erano diversi prima della normalizzazione
        spazi_extra = []
        for _, gruppo in gruppi_duplicati_standard.items():
            # Per ogni gruppo, verifichiamo se i campi originali differivano solo per spazi
            docenti_orig = gruppo['Docente'].astype(str).tolist()
            docenti_norm = gruppo['Docente_norm'].tolist()
            orari_orig = gruppo['Orario'].astype(str).tolist()
            orari_norm = gruppo['Orario_norm'].tolist()
            
            # Se alcuni valori originali sono diversi ma quelli normalizzati sono uguali,
            # abbiamo trovato differenze dovute solo a spazi
            if len(set(docenti_orig)) > len(set(docenti_norm)) or len(set(orari_orig)) > len(set(orari_norm)):
                for i in range(len(gruppo)):
                    row = gruppo.iloc[i]
                    # Marca questo record come avente spazi extra
                    spazi_extra.append((row.name, "Trovati spazi extra nei campi"))
    
    if metodo in ['avanzato', 'completo']:
        # METODO AVANZATO: cerca anche piccole differenze
        # Questo metodo identifica duplicati potenziali anche quando ci sono piccole differenze
        
        # 1. Controllo errori ortografici nei nomi dei docenti
        # Questo controllo identifica errori di battitura o variazioni ortografiche nei nomi
        docenti_list = sorted(working_df['Docente'].dropna().unique())
        
        for i in range(len(docenti_list)):
            for j in range(i + 1, len(docenti_list)):
                docente1 = docenti_list[i]
                docente2 = docenti_list[j]
                
                # Salta se sono identici
                if docente1 == docente2:
                    continue
                
                # Separa nomi e cognomi
                nomi1, cognomi1 = separa_nome_cognome(docente1)
                nomi2, cognomi2 = separa_nome_cognome(docente2)
                
                # Verifica errori ortografici nei cognomi
                errore_trovato = False
                
                # Controlla se i cognomi sono simili (possibile errore ortografico)
                for cognome1 in cognomi1:
                    for cognome2 in cognomi2:
                        # Verifica se i cognomi sono ortograficamente simili
                        if errore_ortografico_possibile(cognome1, cognome2, 0.75):
                            errore_trovato = True
                            
                            # Verifica anche se i nomi sono identici o molto simili per confermare
                            nomi_simili = False
                            if nomi1 and nomi2:  # Se entrambi hanno nomi
                                for nome1 in nomi1:
                                    for nome2 in nomi2:
                                        if nome1.lower() == nome2.lower() or errore_ortografico_possibile(nome1, nome2, 0.9):
                                            nomi_simili = True
                                            break
                                    if nomi_simili:
                                        break
                            
                            # Se troviamo cognomi simili e nomi simili, probabile stesso docente con errore ortografico
                            if nomi_simili or not (nomi1 and nomi2):  # Se i nomi sono simili o uno dei due non ha nomi
                                # Ottieni tutti i record per entrambi i docenti
                                records1 = working_df[working_df['Docente'] == docente1]
                                records2 = working_df[working_df['Docente'] == docente2]
                                
                                # Per ogni combinazione di record, verifica se potrebbero essere duplicati
                                for _, rec1 in records1.iterrows():
                                    for _, rec2 in records2.iterrows():
                                        # Verifica se i record sono per lezioni simili
                                        if 'Denominazione Insegnamento' in rec1 and 'Denominazione Insegnamento' in rec2:
                                            insegnamento1 = str(rec1['Denominazione Insegnamento']).lower()
                                            insegnamento2 = str(rec2['Denominazione Insegnamento']).lower()
                                            
                                            # Calcola similarità degli insegnamenti
                                            sim_insegnamento = difflib.SequenceMatcher(None, insegnamento1, insegnamento2).ratio()
                                            
                                            # Se gli insegnamenti sono simili, potrebbe essere un duplicato con errore nel nome
                                            if sim_insegnamento > 0.6:
                                                # Crea un gruppo di duplicati per questo caso
                                                gruppo_key = f"avanzato|errore_ortografico|{docente1}~{docente2}"
                                                
                                                # Crea un DataFrame con i due record
                                                duplicati_df = pd.DataFrame([rec1, rec2])
                                                
                                                # Aggiungi al dizionario dei gruppi (solo se non è già presente)
                                                if gruppo_key not in gruppi_duplicati:
                                                    gruppi_duplicati[gruppo_key] = duplicati_df
                                                else:
                                                    # Aggiungi il record se non è già presente nel gruppo
                                                    gruppi_duplicati[gruppo_key] = pd.concat([gruppi_duplicati[gruppo_key], duplicati_df]).drop_duplicates()
        
        # 2. Controllo nomi docenti invertiti (nome-cognome vs cognome-nome)
        # Questo controllo identifica i duplicati dove il nome e il cognome del docente sono stati invertiti
        docenti_records = {}  # Dizionario per memorizzare i record per ogni docente
        
        # Popola il dizionario con i record per ogni docente
        for idx, row in working_df.iterrows():
            docente = str(row['Docente']).strip() if pd.notna(row['Docente']) else ""
            if docente == "":
                continue
                
            # Memorizza questo record per il docente
            if docente not in docenti_records:
                docenti_records[docente] = []
            docenti_records[docente].append(row)
        
        # Confronta i nomi dei docenti per trovare possibili inversioni nome-cognome
        docenti_list = list(docenti_records.keys())
        for i in range(len(docenti_list)):
            for j in range(i + 1, len(docenti_list)):
                docente1 = docenti_list[i]
                docente2 = docenti_list[j]
                
                # Verifica se potrebbero essere lo stesso docente con nome/cognome invertiti
                if sono_stesso_docente(docente1, docente2):
                    # Per ogni record del primo docente
                    for rec_i in docenti_records[docente1]:
                        # Per ogni record del secondo docente
                        for rec_j in docenti_records[docente2]:
                            # Verifica che i record abbiano la stessa data
                            data_i = str(rec_i.get('Data_str', ''))
                            data_j = str(rec_j.get('Data_str', ''))
                            
                            # Se le date sono diverse, non sono gli stessi record
                            if data_i != data_j or not data_i:
                                continue
                                
                            # Verifica che i record abbiano lo stesso orario
                            orario_i = str(rec_i.get('Orario', ''))
                            orario_j = str(rec_j.get('Orario', ''))
                            
                            # Se gli orari sono diversi, non sono gli stessi record
                            if orario_i != orario_j or not orario_i:
                                continue
                                
                            # Verifica ulteriormente se gli altri campi sono simili
                            # Ad esempio, stesso insegnamento o insegnamenti simili
                            insegnamento_i = str(rec_i.get('Denominazione Insegnamento', '')).lower()
                            insegnamento_j = str(rec_j.get('Denominazione Insegnamento', '')).lower()
                            
                            # Calcola somiglianza tra stringhe (ratio tra 0 e 1)
                            similarita = difflib.SequenceMatcher(None, insegnamento_i, insegnamento_j).ratio()
                            
                            if similarita > 0.6:  # Soglia di somiglianza
                                # Crea una chiave per questo gruppo basata sui nomi dei docenti e data
                                gruppo_key = f"avanzato|docenti_invertiti|{data_i}|{docente1}~{docente2}"
                                
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
        
        # 3. Controllo sovrapposizioni di orario per lo stesso docente
        # Questo controllo identifica le lezioni dello stesso docente che si sovrappongono nel tempo
        for docente, lezioni_docente in working_df.groupby('Docente'):
            if len(lezioni_docente) < 2:  # Servono almeno 2 lezioni per una sovrapposizione
                continue
                
            # Raggruppa per data
            for data, lezioni_giorno in lezioni_docente.groupby('Data_str'):
                if len(lezioni_giorno) < 2:  # Servono almeno 2 lezioni nello stesso giorno
                    continue
                    
                try:
                    # Converti orari in minuti per confronto numerico
                    lezioni_giorno['orario_minuti'] = lezioni_giorno['Orario'].apply(lambda x: 
                        int(str(x).split(':')[0]) * 60 + int(str(x).split(':')[1]) 
                        if ':' in str(x) else 0)
                    
                    # Ordina per orario
                    lezioni_giorno = lezioni_giorno.sort_values('orario_minuti')
                    
                    # Cerca lezioni con orari sovrapposti o molto vicini (entro 30 minuti)
                    sovrapposizioni_trovate = []
                    for i in range(len(lezioni_giorno)):
                        for j in range(i+1, len(lezioni_giorno)):
                            rec_i = lezioni_giorno.iloc[i]
                            rec_j = lezioni_giorno.iloc[j]
                            
                            # Calcola differenza in minuti
                            diff_minuti = abs(rec_j['orario_minuti'] - rec_i['orario_minuti'])
                            
                            # Se gli orari sono molto vicini (entro 30 minuti), potrebbero essere un problema
                            if diff_minuti <= 30:  
                                # Crea una chiave per questo gruppo di sovrapposizioni
                                gruppo_key = f"avanzato|sovrapposizione|{data}|{docente}|{rec_i['Orario']}~{rec_j['Orario']}"
                                
                                # Crea un DataFrame con i due record
                                duplicati_df = pd.DataFrame([rec_i, rec_j])
                                
                                # Aggiungi al dizionario dei gruppi
                                gruppi_duplicati[gruppo_key] = duplicati_df
                except Exception as e:
                    # In caso di errori nel confronto orari, procedi comunque
                    logger.warning(f"Errore nel confronto orari per sovrapposizione: {e}")
                    continue
    
    return gruppi_duplicati

def evidenzia_differenze(str1: str, str2: str) -> Tuple[str, str]:
    """
    Evidenzia le differenze tra due stringhe per mostrare visivamente cosa è cambiato.
    Rende visibili anche gli spazi.
    
    Args:
        str1: Prima stringa
        str2: Seconda stringa
        
    Returns:
        Tuple[str, str]: Le due stringhe con le differenze evidenziate in HTML
    """
    # Controlliamo se la differenza è solo negli spazi
    str1_norm = normalizza_stringa(str1)
    str2_norm = normalizza_stringa(str2)
    diff_solo_spazi = (str1_norm == str2_norm) and (str1 != str2)
    
    # Se la differenza è solo negli spazi, utilizziamo una visualizzazione specializzata
    if diff_solo_spazi:
        # Sostituiamo gli spazi con un punto mediano visibile e evidenziamo le stringhe
        str1_vis = str1.replace(' ', '·')
        str2_vis = str2.replace(' ', '·')
        return (
            f"<span style='background-color: #FFEECC'>{str1_vis}</span>", 
            f"<span style='background-color: #FFEECC'>{str2_vis}</span>"
        )
    
    # Altrimenti procediamo con l'evidenziazione standard delle differenze
    matcher = difflib.SequenceMatcher(None, str1, str2)
    str1_html = []
    str2_html = []
    
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            str1_html.append(str1[i1:i2])
            str2_html.append(str2[j1:j2])
        elif op == 'insert':
            str2_html.append(f"<span style='background-color: #CCFFCC'>{str2[j1:j2].replace(' ', '·')}</span>")
        elif op == 'delete':
            str1_html.append(f"<span style='background-color: #FFCCCC'>{str1[i1:i2].replace(' ', '·')}</span>")
        elif op == 'replace':
            # Nelle sostituzioni, rendiamo visibili gli spazi
            str1_seg = str1[i1:i2].replace(' ', '·')
            str2_seg = str2[j1:j2].replace(' ', '·')
            str1_html.append(f"<span style='background-color: #FFCCCC'>{str1_seg}</span>")
            str2_html.append(f"<span style='background-color: #CCFFCC'>{str2_seg}</span>")
    
    return ''.join(str1_html), ''.join(str2_html)

def confronta_record(record1: pd.Series, record2: pd.Series) -> Dict[str, Tuple[str, str, bool, bool]]:
    """
    Confronta due record e restituisce le differenze formattate.
    
    Args:
        record1: Primo record
        record2: Secondo record
        
    Returns:
        Dict[str, Tuple[str, str, bool, bool]]: Dizionario con le differenze evidenziate per ogni campo,
                                              un flag che indica se il campo è diverso e
                                              un flag che indica se la differenza è solo negli spazi
    """
    differenze = {}
    
    for campo in record1.index:
        # Converti entrambi i valori in stringhe per confronto
        val1 = str(record1[campo]) if pd.notna(record1[campo]) else ""
        val2 = str(record2[campo]) if pd.notna(record2[campo]) else ""
        
        # Normalizza i valori per il confronto senza spazi extra
        val1_norm = normalizza_stringa(val1)
        val2_norm = normalizza_stringa(val2)
        
        # Verifica se i campi sono diversi
        if val1 != val2:
            # Determina se la differenza è solo negli spazi
            diff_solo_spazi = (val1_norm == val2_norm)
            
            # Prepara la visualizzazione delle differenze
            if diff_solo_spazi:
                # Sostituiamo gli spazi con un simbolo visibile per evidenziare la differenza
                val1_vis = val1.replace(' ', '·')
                val2_vis = val2.replace(' ', '·')
                val1_html = f"<span style='background-color: #FFEECC'>{val1_vis}</span>"
                val2_html = f"<span style='background-color: #FFEECC'>{val2_vis}</span>"
            else:
                val1_html, val2_html = evidenzia_differenze(val1, val2)
            
            differenze[campo] = (val1_html, val2_html, True, diff_solo_spazi)
        else:
            differenze[campo] = (val1, val2, False, False)
    
    return differenze

def genera_report_duplicati(df: pd.DataFrame, gruppi_duplicati: Dict[str, pd.DataFrame]) -> str:
    """
    Genera un report di testo con i dettagli dei potenziali record duplicati.
    Include informazioni su spazi extra nei campi.
    
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
    
    # Genera il report completo
    report_text = genera_report_duplicati(df, gruppi_duplicati)
    
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
            
        # Estrai informazioni dal gruppo
        parts = k.split("|")
        df_gruppo = gruppi_duplicati[k]
        num_records = len(df_gruppo)
        
        # Identifica se ci sono differenze solo per spazi extra
        differenze_spazi = False
        if len(df_gruppo) >= 2:
            # Controlla ogni campo per vedere se differisce solo per spazi
            for colonna in ['Docente', 'Orario', 'Denominazione Insegnamento', 'Aula', 'Insegnamento comune']:
                if colonna in df_gruppo.columns:
                    # Crea versioni normalizzate
                    valori = df_gruppo[colonna].astype(str).tolist()
                    valori_norm = [normalizza_stringa(v) for v in valori]
                    
                    # Se i valori normalizzati sono tutti uguali ma i valori originali differiscono, 
                    # abbiamo trovato differenze dovute solo a spazi
                    if len(set(valori)) > len(set(valori_norm)) and len(set(valori_norm)) == 1:
                        differenze_spazi = True
                        break
        
        # Crea una descrizione leggibile
        if len(parts) >= 3 and parts[0] == "standard":
            # Per i gruppi standard, mostra data, docente e numero di record
            data_docente = parts[1].split('|')
            if len(data_docente) >= 3:
                data = data_docente[0]
                docente = data_docente[1]
                descrizione = f"{tipo}: {data} - {docente} ({num_records} record)"
                if differenze_spazi:
                    descrizione = f"⚠️ {descrizione} [Differenze per spazi]"
                formatted_keys.append((k, descrizione))
        elif len(parts) >= 3 and parts[0] == "avanzato":
            # Per i gruppi avanzati, mostra il tipo di rilevamento e informazioni rilevanti
            subtipo = parts[1]
            if subtipo == "errore_ortografico":
                docenti = parts[2].split('~')
                descrizione = f"{tipo}: Possibile errore ortografico - {' vs '.join(docenti)} ({num_records} record)"
                if differenze_spazi:
                    descrizione = f"⚠️ {descrizione} [Differenze per spazi]"
                formatted_keys.append((k, descrizione))
            elif subtipo == "docenti_invertiti":
                if len(parts) >= 4:
                    data = parts[2]
                    docenti = parts[3].split('~')
                    descrizione = f"{tipo}: Nome/Cognome invertito {data} - {' vs '.join(docenti)} ({num_records} record)"
                    if differenze_spazi:
                        descrizione = f"⚠️ {descrizione} [Differenze per spazi]"
                    formatted_keys.append((k, descrizione))
            elif subtipo == "sovrapposizione":
                if len(parts) >= 5:
                    data = parts[2]
                    docente = parts[3]
                    orari = parts[4].split('~')
                    descrizione = f"{tipo}: Sovrapposizione orari {data} - {docente} - {' vs '.join(orari)} ({num_records} record)"
                    if differenze_spazi:
                        descrizione = f"⚠️ {descrizione} [Differenze per spazi]"
                    formatted_keys.append((k, descrizione))
            else:
                # Per altri tipi, usa una descrizione generica
                descrizione = f"{tipo}: Gruppo duplicati {k.split('|')[-1]} ({num_records} record)"
                if differenze_spazi:
                    descrizione = f"⚠️ {descrizione} [Differenze per spazi]"
                formatted_keys.append((k, descrizione))
        else:
            # Fallback per chiavi sconosciute
            descrizione = f"Gruppo duplicati {k} ({num_records} record)"
            if differenze_spazi:
                descrizione = f"⚠️ {descrizione} [Differenze per spazi]"
            formatted_keys.append((k, descrizione))
    
    # Crea un mapping tra le chiavi formattate e quelle originali
    key_mapping = dict(zip([x[1] for x in formatted_keys], [x[0] for x in formatted_keys]))
    
    # Seleziona il gruppo da visualizzare
    selected_formatted_key = st.selectbox(
        "Seleziona un gruppo di potenziali duplicati da esaminare:",
        [""] + [x[1] for x in formatted_keys]
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
            
            for campo, (val1, val2, diverso, diff_solo_spazi) in differenze.items():
                if diverso:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**{campo}**: {val1}", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"**{campo}**: {val2}", unsafe_allow_html=True)
                    # Se la differenza è solo negli spazi, aggiungi un indicatore
                    if diff_solo_spazi:
                        st.caption("⚠️ Questo campo differisce solo per spazi extra")
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
    
    # Visualizza il report completo in fondo alla pagina
    st.markdown("---")
    with st.expander("📋 Report completo dei duplicati", expanded=False):
        st.markdown("""
        ### Report completo dei duplicati
        
        Questo report fornisce un riepilogo dettagliato di tutti i gruppi di duplicati trovati nel sistema.
        Include informazioni su tutti i gruppi e le principali differenze rilevate.
        """)
        st.code(report_text, language="text")

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
                                if st.button(
                                    f"🔍 Analizza duplicati per {row['Classe']}", 
                                    key=f"analizza_{row['Classe']}", 
                                    help=f"Esegui un'analisi approfondita dei potenziali duplicati per la classe {row['Classe']}"
                                ):
                                    # Chiama la funzione per mostrare dettagli CFU per questa classe
                                    mostra_dettaglio_cfu_classe(df, row['Classe'])
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
        
        # Aggiungi azione per vedere dettagli di una classe specifica
        classe_selezionata_per_dettaglio = st.selectbox(
            "Visualizza dettagli completi per una classe:",
            [""] + sorted(filtered_df['Insegnamento comune'].unique().tolist()),
            help="Seleziona una classe di concorso per visualizzare i dettagli completi dei CFU, percorsi formativi e informazioni trasversali"
        )
        
        if classe_selezionata_per_dettaglio:
            # Chiama la funzione per mostrare dettagli CFU per questa classe
            mostra_dettaglio_cfu_classe(df, classe_selezionata_per_dettaglio)
        
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

def mostra_dettaglio_cfu_classe(df: pd.DataFrame, classe: str):
    """
    Mostra i dettagli completi dei CFU per una classe di concorso specifica,
    inclusi i percorsi formativi e le informazioni sulla trasversale della classe.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        classe: Classe di concorso da analizzare in dettaglio
    """
    from percorsi_formativi import (
        PERCORSI_CFU, AREE_FORMATIVE, SUBAREE_TRASVERSALI,
        CLASSI_GRUPPO_A, CLASSI_GRUPPO_B, CLASSI_TRASVERSALI
    )

    st.subheader(f"📚 Dettaglio CFU per {classe}")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per l'analisi dettagliata")
        return
    
    # Crea una copia del dataframe per le operazioni
    working_df = df.copy()
    
    # Pulisci e standardizza i valori dei CFU
    working_df['CFU_clean'] = working_df['CFU'].astype(str).str.replace(',', '.')
    working_df['CFU_clean'] = working_df['CFU_clean'].replace('nan', '0')
    working_df['CFU_numeric'] = pd.to_numeric(working_df['CFU_clean'], errors='coerce').fillna(0)
    
    # Rimuovi i duplicati per avere conteggi accurati
    working_df = working_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Filtra per la classe selezionata
    classe_df = working_df[working_df['Insegnamento comune'] == classe]
    
    # Se la classe non esiste nel dataframe
    if classe_df.empty:
        st.warning(f"La classe di concorso {classe} non è presente nei dati o non ha lezioni assegnate.")
        return
    
    # Calcola i CFU totali per la classe
    cfu_totali = round(classe_df['CFU_numeric'].sum(), 1)
    num_lezioni = len(classe_df)
    
    # Determina se la classe appartiene al gruppo A o B e quale trasversale le è associata
    gruppo_trasversale = None
    if classe in CLASSI_GRUPPO_A:
        gruppo_trasversale = "A"
    elif classe in CLASSI_GRUPPO_B:
        gruppo_trasversale = "B"
    
    # Crea tabs per organizzare le informazioni
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Riepilogo", "🔄 Percorsi Formativi", "🔀 Classi Trasversali", "📋 Elenco Lezioni"])
    
    # TAB 1: Riepilogo generale
    with tab1:
        # Mostra informazioni generali sulla classe
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Totale CFU", value=cfu_totali)
            st.metric(label="Numero Lezioni", value=num_lezioni)
        
        with col2:
            if gruppo_trasversale:
                st.info(f"📌 Questa classe appartiene al gruppo {gruppo_trasversale} (Trasversale {gruppo_trasversale})")
            else:
                st.info("📌 Questa classe non appartiene né al gruppo A né al gruppo B")
            
            # Calcola CFU medi per lezione
            cfu_medi = round(cfu_totali / num_lezioni, 2) if num_lezioni > 0 else 0
            st.metric(label="CFU medi per lezione", value=cfu_medi)
        
        # Mostra i dipartimenti associati
        if 'Dipartimento' in classe_df.columns:
            dipartimenti = classe_df['Dipartimento'].dropna().unique()
            if len(dipartimenti) > 0:
                st.write("### Dipartimenti associati:")
                for dip in dipartimenti:
                    st.write(f"- {dip}")
        
        # Mostra i docenti che insegnano questa classe
        st.write("### Docenti:")
        docenti_stats = classe_df.groupby('Docente').agg(
            Lezioni=pd.NamedAgg(column='Denominazione Insegnamento', aggfunc='count'),
            CFU=pd.NamedAgg(column='CFU_numeric', aggfunc='sum')
        ).reset_index()
        
        docenti_stats['CFU'] = docenti_stats['CFU'].round(1)
        st.dataframe(docenti_stats.sort_values('CFU', ascending=False), use_container_width=True, hide_index=True)
    
    # TAB 2: Percorsi Formativi
    with tab2:
        st.write("### Percorsi Formativi applicabili")
        
        # Controlla se le colonne dei percorsi formativi sono presenti
        percorsi_disponibili = [p for p in PERCORSI_CFU.keys() if p in working_df.columns]
        
        if not percorsi_disponibili:
            st.info("Nessun percorso formativo trovato nel dataset.")
        else:
            # Per ogni percorso, calcola i CFU erogati e la distribuzione P/D
            percorsi_data = []
            
            for percorso in percorsi_disponibili:
                # Filtra per lezioni della classe corrente
                percorso_df = classe_df[classe_df[percorso].isin(['P', 'D'])]
                
                # Separa in P e D
                p_df = percorso_df[percorso_df[percorso] == 'P']
                d_df = percorso_df[percorso_df[percorso] == 'D']
                
                # Calcola CFU per modalità
                cfu_p = round(p_df['CFU_numeric'].sum(), 1)
                cfu_d = round(d_df['CFU_numeric'].sum(), 1)
                cfu_tot = cfu_p + cfu_d
                
                # Aggiungi al risultato
                percorsi_data.append({
                    'Percorso': percorso,
                    'CFU Presenza': cfu_p,
                    'CFU Distanza': cfu_d,
                    'CFU Totali': cfu_tot,
                    'Lezioni Presenza': len(p_df),
                    'Lezioni Distanza': len(d_df)
                })
            
            # Visualizza tabella dei percorsi
            percorsi_df = pd.DataFrame(percorsi_data)
            st.dataframe(percorsi_df, use_container_width=True, hide_index=True)
            
            # Per ogni percorso, mostra tab con dettaglio conformità rispetto ai requisiti DPCM
            if percorsi_data:
                percorsi_tabs = st.tabs([p['Percorso'] for p in percorsi_data])
                
                for i, percorso in enumerate([p['Percorso'] for p in percorsi_data]):
                    with percorsi_tabs[i]:
                        # Ottieni i requisiti dal DPCM per questo percorso
                        requisiti = PERCORSI_CFU.get(percorso, {})
                        
                        if not requisiti:
                            st.warning(f"Requisiti non definiti per il percorso {percorso}")
                            continue
                        
                        st.write(f"#### Conformità {percorso} rispetto al DPCM")
                        
                        # Filtra per il percorso corrente
                        percorso_classe_df = classe_df[classe_df[percorso].isin(['P', 'D'])]
                        
                        # Aggiungi la classificazione delle aree formative
                        from cfu_riepilogo_utils import _classifica_insegnamenti_per_area
                        df_classificato = _classifica_insegnamenti_per_area(percorso_classe_df)
                        
                        # Calcola i CFU per area formativa
                        cfu_per_area = df_classificato.groupby('Area Formativa')['CFU_numeric'].sum().reset_index()
                        cfu_per_area['CFU_numeric'] = cfu_per_area['CFU_numeric'].round(1)
                        
                        # Aggiunge requisiti del DPCM e calcola conformità
                        result_data = []
                        for area in AREE_FORMATIVE:
                            cfu_req = requisiti.get(area, 0)
                            cfu_erog = cfu_per_area[cfu_per_area['Area Formativa'] == area]['CFU_numeric'].sum() if area in cfu_per_area['Area Formativa'].values else 0
                            diff = round(cfu_erog - cfu_req, 1)
                            stato = "✅" if diff >= 0 or cfu_req == 0 else "❌"
                            
                            result_data.append({
                                'Area': area,
                                'CFU Erogati': cfu_erog,
                                'CFU Richiesti': cfu_req,
                                'Differenza': diff,
                                'Stato': stato
                            })
                        
                        # Visualizza tabella di conformità
                        result_df = pd.DataFrame(result_data)
                        st.dataframe(result_df, use_container_width=True, hide_index=True)
                        
                        # Se il percorso ha requisiti per subaree trasversali, mostrali
                        if 'Trasversale_dettaglio' in requisiti:
                            st.write("#### Dettaglio Subaree Trasversali")
                            
                            # Filtra per area trasversale
                            trasv_df = df_classificato[df_classificato['Area Formativa'] == 'Trasversale']
                            
                            # Calcola CFU per subarea
                            if not trasv_df.empty and 'Subarea Trasversale' in trasv_df.columns:
                                subaree_data = []
                                
                                # Per ogni subarea definita nel DPCM
                                for subarea in SUBAREE_TRASVERSALI:
                                    # Trova i requisiti per questa subarea
                                    req_subarea = requisiti['Trasversale_dettaglio'].get(subarea, 0)
                                    
                                    # Calcola CFU erogati per questa subarea
                                    erog_subarea = trasv_df[trasv_df['Subarea Trasversale'] == subarea]['CFU_numeric'].sum()
                                    erog_subarea = round(erog_subarea, 1)
                                    
                                    # Calcola la differenza
                                    diff = round(erog_subarea - req_subarea, 1)
                                    
                                    # Determina lo stato
                                    stato = "✅" if diff >= 0 or req_subarea == 0 else "❌"
                                    
                                    # Aggiungi ai dati
                                    subaree_data.append({
                                        'Subarea': subarea,
                                        'CFU Erogati': erog_subarea,
                                        'CFU Richiesti': req_subarea,
                                        'Differenza': diff,
                                        'Stato': stato
                                    })
                                
                                # Visualizza tabella delle subaree
                                subaree_df = pd.DataFrame(subaree_data)
                                st.dataframe(subaree_df, use_container_width=True, hide_index=True)
                            else:
                                st.info("Nessun dato disponibile per le subaree trasversali")
    
    # TAB 3: Classi Trasversali
    with tab3:
        st.write("### Informazioni sulle Classi Trasversali")
        
        # Se la classe è già una trasversale
        if classe in CLASSI_TRASVERSALI:
            st.info(f"La classe {classe} è una classe trasversale.")
            
            # Ottiene i dati specifici di questa classe trasversale
            from cfu_riepilogo_utils import _classifica_insegnamenti_per_area
            trasv_df = _classifica_insegnamenti_per_area(classe_df)
            
            # Mostra la suddivisione per subaree trasversali
            if 'Subarea Trasversale' in trasv_df.columns:
                # Calcola CFU per subarea
                subaree_cfu = trasv_df.groupby('Subarea Trasversale')['CFU_numeric'].sum().reset_index()
                subaree_cfu['CFU_numeric'] = subaree_cfu['CFU_numeric'].round(1)
                subaree_cfu = subaree_cfu.rename(columns={'CFU_numeric': 'CFU'})
                
                st.write("#### CFU per Subarea Trasversale")
                st.dataframe(subaree_cfu, use_container_width=True, hide_index=True)
            
        # Se la classe appartiene a un gruppo che ha una trasversale associata
        elif gruppo_trasversale:
            trasversale_associata = f"Trasversale {gruppo_trasversale}"
            st.info(f"La classe {classe} è associata alla {trasversale_associata}")
            
            # Ottieni i dati della trasversale associata
            trasv_df = working_df[working_df['Insegnamento comune'] == trasversale_associata]
            
            if not trasv_df.empty:
                # Calcola CFU totali della trasversale
                cfu_trasv = round(trasv_df['CFU_numeric'].sum(), 1)
                num_lezioni_trasv = len(trasv_df)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(label=f"CFU {trasversale_associata}", value=cfu_trasv)
                with col2:
                    st.metric(label=f"Lezioni {trasversale_associata}", value=num_lezioni_trasv)
                
                # Classifica gli insegnamenti per subarea
                from cfu_riepilogo_utils import _classifica_insegnamenti_per_area
                trasv_classif = _classifica_insegnamenti_per_area(trasv_df)
                
                # Mostra la suddivisione per subaree trasversali
                if 'Subarea Trasversale' in trasv_classif.columns:
                    # Calcola CFU per subarea
                    subaree_cfu = trasv_classif.groupby('Subarea Trasversale')['CFU_numeric'].sum().reset_index()
                    subaree_cfu['CFU_numeric'] = subaree_cfu['CFU_numeric'].round(1)
                    subaree_cfu = subaree_cfu.rename(columns={'CFU_numeric': 'CFU'})
                    
                    st.write("#### CFU per Subarea Trasversale")
                    st.dataframe(subaree_cfu.sort_values('CFU', ascending=False), use_container_width=True, hide_index=True)
                
                # Mostra docenti della trasversale
                st.write(f"#### Docenti per {trasversale_associata}:")
                docenti_trasv = trasv_df.groupby('Docente').agg(
                    Lezioni=pd.NamedAgg(column='Denominazione Insegnamento', aggfunc='count'),
                    CFU=pd.NamedAgg(column='CFU_numeric', aggfunc='sum')
                ).reset_index()
                
                docenti_trasv['CFU'] = docenti_trasv['CFU'].round(1)
                st.dataframe(docenti_trasv.sort_values('CFU', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.warning(f"Non sono stati trovati dati per {trasversale_associata}")
        else:
            st.info("Questa classe non è associata a nessuna classe trasversale specifica")
    
    # TAB 4: Elenco Lezioni
    with tab4:
        st.write("### Elenco completo delle lezioni")
        
        # Prepara le colonne da visualizzare
        display_cols = ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento', 'CFU_numeric', 'Aula']
        display_cols += [p for p in percorsi_disponibili if p in working_df.columns]
        
        # Filtra le colonne che esistono effettivamente nel DataFrame
        display_cols = [col for col in display_cols if col in classe_df.columns]
        
        # Rinomina colonne per una migliore visualizzazione
        renamed_cols = {
            'CFU_numeric': 'CFU',
            'Denominazione Insegnamento': 'Denominazione'
        }
        
        # Crea una copia per la visualizzazione
        display_df = classe_df[display_cols].copy()
        
        # Rinomina colonne
        display_df = display_df.rename(columns=renamed_cols)
        
        # Converti la data in formato leggibile
        if 'Data' in display_df.columns and hasattr(display_df['Data'], 'dt'):
            display_df['Data'] = display_df['Data'].dt.strftime('%d/%m/%Y')
        
        # Ordina per data e orario
        if 'Data' in display_df.columns and 'Orario' in display_df.columns:
            display_df = display_df.sort_values(['Data', 'Orario'])
        
        # Mostra la tabella dettagliata
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Opzione per scaricare l'elenco delle lezioni
        st.download_button(
            label="📄 Scarica elenco lezioni",
            data=display_df.to_csv(index=False),
            file_name=f"lezioni_{classe}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
