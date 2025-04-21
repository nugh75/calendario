"""
Utility per la creazione di un riepilogo dei CFU per classi di concorso e percorsi formativi.
Questo modulo fornisce funzioni per generare statistiche sui CFU erogati per ciascuna classe di concorso
e relativi percorsi formativi (PeF60, PeF30, ecc.).
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Union
import os
import numpy as np
from percorsi_formativi import PERCORSI_CFU, AREE_FORMATIVE, SUBAREE_TRASVERSALI, classifica_insegnamento

# Definizione delle classi di concorso ufficiali
CLASSI_CONCORSO = [
    # Area umanistica
    "A001", "A007", "A008", "A011", "A012", "A013", "A017", "A018", "A019",
    "A022", "A023", "AA24", "AB24", "AC24", "AL24", "A029", "A030", "A037", 
    "A053", "A054", "A061", "A063", "A064",
    # Area scientifica/tecnica
    "A020", "A026", "A027", "A028", "A040", "A042", "A045", "A046", 
    "A050", "A060", "B015",
]

# Classi trasversali
CLASSI_TRASVERSALI = ["Trasversale A", "Trasversale B"]

# Percorsi formativi
PERCORSI = ["PeF60 all.1", "PeF30 all.2", "PeF36 all.5", "PeF30 art.13"]


def _espandi_classi_multiple(df: pd.DataFrame) -> pd.DataFrame:
    """
    Espande le classi di concorso multiple (es. A017-A054) in classi singole,
    duplicando le righe e assegnando ciascuna a una classe distinta.
    Per classi multiple come "A020-A027", i CFU vengono assegnati interamente 
    a ciascuna classe singola, siccome gli studenti svolgono la stessa lezione.
    
    Args:
        df: DataFrame con i dati delle lezioni
        
    Returns:
        pd.DataFrame: Nuovo DataFrame con le classi espanse
    """
    # Crea un nuovo DataFrame per le righe espanse
    expanded_rows = []
    
    for _, row in df.iterrows():
        insegnamento = str(row['Insegnamento comune'])
        
        # Controlla se è una classe multipla (contiene un trattino)
        if '-' in insegnamento:
            # Dividi in singole classi
            singole_classi = insegnamento.split('-')
            
            # Crea una riga per ogni classe singola
            for classe in singole_classi:
                classe = classe.strip()  # Rimuovi eventuali spazi
                if classe:  # Verifica che non sia vuota
                    # Crea una copia della riga originale e cambia l'insegnamento
                    new_row = row.copy()
                    new_row['Insegnamento comune'] = classe
                    expanded_rows.append(new_row)
        else:
            # Aggiungi la riga originale se non è una classe multipla
            expanded_rows.append(row.copy())
    
    # Crea un nuovo DataFrame con tutte le righe
    return pd.DataFrame(expanded_rows)


def _filtra_classi_multiple(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra il DataFrame escludendo i record con classi di concorso multiple 
    (es. A001-A007, A011-A012-A013-A019-A022, ecc.), che non devono essere
    considerate nell'analisi dei CFU.
    
    Args:
        df: DataFrame con i dati delle lezioni
        
    Returns:
        pd.DataFrame: Nuovo DataFrame senza le righe con classi multiple
    """
    # Filtra mantenendo solo le righe dove non c'è un trattino nel campo Insegnamento comune
    return df[~df['Insegnamento comune'].astype(str).str.contains('-')]

def mostra_riepilogo_cfu(df: pd.DataFrame):
    """
    Genera e visualizza un riepilogo dei CFU per classe di concorso e percorso formativo.
    
    Args:
        df: DataFrame contenente i dati delle lezioni
    """
    st.subheader("📊 Riepilogo CFU per Classi di Concorso e Percorsi")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per il riepilogo CFU")
        return
    
    # Crea una copia del dataframe per le operazioni
    stats_df = df.copy()
    
    # Pulisci e standardizza i valori dei CFU
    stats_df['CFU_clean'] = stats_df['CFU'].astype(str).str.replace(',', '.')
    stats_df['CFU_clean'] = stats_df['CFU_clean'].replace('nan', '0')
    stats_df['CFU_numeric'] = pd.to_numeric(stats_df['CFU_clean'], errors='coerce').fillna(0)
    
    # Rimuovi i duplicati per avere conteggi accurati
    stats_df = stats_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Espandi le classi multiple invece di filtrarle
    # In questo modo i CFU dei record con classi combinate vengono assegnati a ciascuna classe individuale
    stats_df = _espandi_classi_multiple(stats_df)
    
    # Separa le classi trasversali dalle classi di concorso specifiche
    classi_specifiche_df = stats_df[~stats_df['Insegnamento comune'].isin(CLASSI_TRASVERSALI)]
    trasversali_df = stats_df[stats_df['Insegnamento comune'].isin(CLASSI_TRASVERSALI)]
    
    # Tabs per separare le visualizzazioni
    tab1, tab2 = st.tabs(["Classi di Concorso", "Trasversali"])
    
    # Tab 1: Riepilogo per Classi di Concorso
    with tab1:
        st.subheader("Riepilogo CFU per Classi di Concorso")
        
        # Genera il riepilogo per classi di concorso
        if not classi_specifiche_df.empty:
            # Crea una tabella pivot per il riepilogo
            cfu_per_classe = _genera_pivot_cfu_per_classe(classi_specifiche_df)
            
            # Visualizza il riepilogo come tabella
            st.dataframe(cfu_per_classe, use_container_width=True)
            
            # Visualizza un grafico a barre per confronto visivo
            _visualizza_grafico_cfu(cfu_per_classe)
        else:
            st.info("Nessun dato disponibile per classi di concorso specifiche")
    
    # Tab 2: Riepilogo per Classi Trasversali
    with tab2:
        st.subheader("Riepilogo CFU per Classi Trasversali")
        
        # Genera il riepilogo per classi trasversali
        if not trasversali_df.empty:
            # Crea una tabella pivot per il riepilogo
            cfu_trasversali = _genera_pivot_cfu_per_classe(trasversali_df)
            
            # Visualizza il riepilogo come tabella
            st.dataframe(cfu_trasversali, use_container_width=True)
            
            # Visualizza un grafico a barre per confronto visivo
            _visualizza_grafico_cfu(cfu_trasversali)
        else:
            st.info("Nessun dato disponibile per classi trasversali")


def _genera_pivot_cfu_per_classe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera una tabella pivot con i CFU per ogni classe di concorso e percorso,
    distinguendo tra modalità Presenza (P) e Distanza (D).
    
    Args:
        df: DataFrame contenente i dati delle lezioni
        
    Returns:
        pd.DataFrame: Tabella pivot con i CFU per classe e percorso, separati per modalità
    """
    # Crea un DataFrame per il risultato finale
    result_df = pd.DataFrame(index=df['Insegnamento comune'].unique())
    
    # Per ogni percorso, calcola i CFU per modalità D e P
    for percorso in PERCORSI:
        if percorso in df.columns:
            # Calcola i CFU per la modalità D (Distanza)
            d_pivot = pd.pivot_table(
                df[df[percorso] == 'D'],
                values='CFU_numeric',
                index=['Insegnamento comune'],
                aggfunc='sum',
                fill_value=0
            )
            
            # Calcola i CFU per la modalità P (Presenza)
            p_pivot = pd.pivot_table(
                df[df[percorso] == 'P'],
                values='CFU_numeric',
                index=['Insegnamento comune'],
                aggfunc='sum',
                fill_value=0
            )
            
            # Aggiungi le colonne al risultato, distinguendo per modalità
            if not d_pivot.empty:
                result_df[f"{percorso} (D)"] = d_pivot
            else:
                result_df[f"{percorso} (D)"] = 0
                
            if not p_pivot.empty:
                result_df[f"{percorso} (P)"] = p_pivot
            else:
                result_df[f"{percorso} (P)"] = 0
                
            # Aggiungi una colonna per il totale del percorso
            result_df[f"{percorso} Tot"] = result_df[f"{percorso} (D)"].fillna(0) + result_df[f"{percorso} (P)"].fillna(0)
    
    # Calcola il totale di CFU (senza sommare i percorsi che sono in comune)
    # Utilizziamo il massimo dei CFU per ogni lezione come totale
    # Per farlo, calcoliamo il totale CFU per ogni classe direttamente dai dati originali
    cfu_totali = pd.pivot_table(
        df,
        values='CFU_numeric',
        index=['Insegnamento comune'],
        aggfunc='sum',
        fill_value=0
    )
    
    result_df['Totale CFU'] = cfu_totali
    
    # Riempi i valori NaN con 0
    result_df = result_df.fillna(0)
    
    # Arrotonda tutti i valori
    for col in result_df.columns:
        result_df[col] = result_df[col].round(1)
    
    # Ordina per nome classe
    result_df = result_df.sort_index()
    
    return result_df


def _visualizza_grafico_cfu(df_pivot: pd.DataFrame):
    """
    Funzione segnaposto per mantenere la struttura del codice.
    Non visualizza nulla come richiesto dall'utente.
    
    Args:
        df_pivot: DataFrame pivot con i CFU per classe e percorso
    """
    # La funzione non mostra nulla, come richiesto
    pass


def _mostra_dettaglio_classe(df: pd.DataFrame, classe: str):
    """
    Mostra il dettaglio completo di una classe di concorso selezionata.
    
    Args:
        df: DataFrame con i dati filtrati per la classe selezionata
        classe: Nome della classe di concorso
    """
    # Calcola i CFU totali per la classe
    cfu_totali = round(df['CFU_numeric'].sum(), 1)
    num_lezioni = len(df)
    
    # Mostra un riepilogo dei CFU per percorso
    st.info(f"📚 Classe {classe}: {num_lezioni} lezioni, {cfu_totali} CFU totali")
    
    # Calcola i CFU per percorso formativo
    cfu_per_percorso = {}
    for percorso in PERCORSI:
        if percorso in df.columns:
            # Filtra le lezioni per ogni tipo di percorso (P e D)
            p_df = df[df[percorso] == 'P']
            d_df = df[df[percorso] == 'D']
            non_applicable_df = df[df[percorso] == '---']
            
            cfu_p = round(p_df['CFU_numeric'].sum(), 1) if not p_df.empty else 0
            cfu_d = round(d_df['CFU_numeric'].sum(), 1) if not d_df.empty else 0
            
            # Calcola il numero di lezioni per tipo
            n_lezioni_p = len(p_df)
            n_lezioni_d = len(d_df)
            n_lezioni_na = len(non_applicable_df)
            
            cfu_per_percorso[percorso] = {
                'Presenza (P)': cfu_p,
                'Didattica (D)': cfu_d,
                'Totale': cfu_p + cfu_d,
                'Lezioni P': n_lezioni_p,
                'Lezioni D': n_lezioni_d,
                'Non applicabile': n_lezioni_na
            }
    
    # Visualizza i dati per percorso
    st.subheader("CFU per Percorso Formativo")
    
    # Crea un DataFrame per la visualizzazione tabulare
    percorsi_data = []
    for percorso, dati in cfu_per_percorso.items():
        percorsi_data.append({
            'Percorso': percorso,
            'CFU Presenza (P)': dati['Presenza (P)'],
            'CFU Didattica (D)': dati['Didattica (D)'],
            'Totale CFU': dati['Totale'],
            'N° Lezioni P': dati['Lezioni P'],
            'N° Lezioni D': dati['Lezioni D'],
            'Lezioni N/A': dati['Non applicabile']
        })
    
    percorsi_df = pd.DataFrame(percorsi_data)
    st.dataframe(percorsi_df, use_container_width=True, hide_index=True)
    
    # Aggiungi una spiegazione della legenda
    st.caption("Legenda: P = Presenza, D = Distanza, N/A = Non Applicabile (---)")
    
    # Mostra la lista dettagliata delle lezioni
    st.subheader("Elenco Lezioni")
    
    # Prepara le colonne per la visualizzazione
    display_cols = ['Data', 'Orario', 'Docente', 'Denominazione Insegnamento', 'CFU_numeric'] + [p for p in PERCORSI if p in df.columns]
    renamed_cols = {
        'CFU_numeric': 'CFU',
        'Denominazione Insegnamento': 'Denominazione'
    }
    
    # Crea una copia per la visualizzazione
    display_df = df[display_cols].copy()
    
    # Rinomina colonne per una migliore visualizzazione
    display_df = display_df.rename(columns=renamed_cols)
    
    # Converti la data in formato leggibile
    if 'Data' in display_df.columns and hasattr(display_df['Data'], 'dt'):
        display_df['Data'] = display_df['Data'].dt.strftime('%d/%m/%Y')
    
    # Mostra la tabella dettagliata
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def esporta_riepilogo_excel(df: pd.DataFrame, percorso_file: str = None) -> Optional[str]:
    """
    Esporta il riepilogo dei CFU in un file Excel.
    
    Args:
        df: DataFrame con i dati delle lezioni
        percorso_file: Percorso del file Excel da salvare (opzionale)
        
    Returns:
        str: Percorso del file Excel generato, o None in caso di errore
    """
    try:
        # Se non viene specificato un percorso, usa un percorso standard
        if percorso_file is None:
            from file_utils import DATA_FOLDER
            os.makedirs(DATA_FOLDER, exist_ok=True)
            percorso_file = os.path.join(DATA_FOLDER, 'riepilogo_cfu.xlsx')
        
        # Crea una copia del dataframe per le operazioni
        stats_df = df.copy()
        
        # Standardizza i CFU
        stats_df['CFU_clean'] = stats_df['CFU'].astype(str).str.replace(',', '.')
        stats_df['CFU_numeric'] = pd.to_numeric(stats_df['CFU_clean'], errors='coerce').fillna(0)
        
        # Rimuovi i duplicati
        stats_df = stats_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
        
        # Espandi le classi multiple invece di filtrarle
        # In questo modo i CFU dei record con classi combinate vengono assegnati a ciascuna classe individuale
        stats_df = _espandi_classi_multiple(stats_df)
        
        # Classifica gli insegnamenti per area formativa
        stats_df = _classifica_insegnamenti_per_area(stats_df)
        
        # Separa classi specifiche e trasversali
        classi_specifiche_df = stats_df[~stats_df['Insegnamento comune'].isin(CLASSI_TRASVERSALI)]
        trasversali_df = stats_df[stats_df['Insegnamento comune'].isin(CLASSI_TRASVERSALI)]
        
        # Crea un writer Excel per salvare più fogli
        with pd.ExcelWriter(percorso_file, engine='xlsxwriter') as writer:
            # Formati di cella per Excel
            workbook = writer.book
            header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
            subheader_format = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0', 'border': 1})
            value_format = workbook.add_format({'num_format': '0.0', 'border': 1})
            text_format = workbook.add_format({'border': 1})
            p_format = workbook.add_format({'bg_color': '#E6F2FF', 'num_format': '0.0', 'border': 1})
            d_format = workbook.add_format({'bg_color': '#FFF2CC', 'num_format': '0.0', 'border': 1})
            tot_format = workbook.add_format({'bold': True, 'bg_color': '#CCFFCC', 'num_format': '0.0', 'border': 1})
            conforme_format = workbook.add_format({'bg_color': '#CCFFCC', 'num_format': '0.0', 'border': 1})
            non_conforme_format = workbook.add_format({'bg_color': '#FFCCCC', 'num_format': '0.0', 'border': 1})
            
            # Foglio 1: Riepilogo Classi di Concorso
            pivot_classi = _genera_pivot_cfu_per_classe(classi_specifiche_df)
            pivot_classi.to_excel(writer, sheet_name="Classi di Concorso")
            
            # Personalizza il foglio delle classi di concorso
            worksheet = writer.sheets["Classi di Concorso"]
            
            # Aggiungi una legenda nella prima riga
            worksheet.merge_range("A1:D1", "Riepilogo CFU per Classi di Concorso", header_format)
            worksheet.write(2, 0, "Legenda:", subheader_format)
            worksheet.write(3, 0, "P = Presenza", text_format)
            worksheet.write(3, 1, "D = Distanza", text_format)
            worksheet.write(3, 2, "--- = Non applicabile", text_format)
            worksheet.write(5, 0, "Data generazione:", text_format)
            
            from datetime import datetime
            worksheet.write(5, 1, datetime.now().strftime('%d/%m/%Y %H:%M'), text_format)
            
            # Sposta la tabella di pivot più in basso per fare spazio alla legenda
            riepilogo_row = 7
            for col_num, value in enumerate(pivot_classi.columns.values):
                worksheet.write(riepilogo_row, col_num + 1, value, header_format)
            
            # Scrive i dati del pivot con formattazione
            for row_num, (index_value, row_data) in enumerate(pivot_classi.iterrows()):
                worksheet.write(row_num + riepilogo_row + 1, 0, index_value, text_format)
                for col_num, (col_name, value) in enumerate(row_data.items()):
                    # Formattazione basata sul tipo di colonna
                    if "(P)" in col_name:
                        cell_format = p_format
                    elif "(D)" in col_name:
                        cell_format = d_format
                    elif "Tot" in col_name:
                        cell_format = tot_format
                    else:
                        cell_format = value_format
                        
                    worksheet.write(row_num + riepilogo_row + 1, col_num + 1, value, cell_format)
            
            # Imposta la larghezza delle colonne
            worksheet.set_column(0, 0, 20)  # Colonna delle classi di concorso
            worksheet.set_column(1, len(pivot_classi.columns), 15)  # Colonne dei CFU
            
            # Foglio 2: Riepilogo Classi Trasversali
            if not trasversali_df.empty:
                pivot_trasversali = _genera_pivot_cfu_per_classe(trasversali_df)
                pivot_trasversali.to_excel(writer, sheet_name="Classi Trasversali")
                
                # Applica la stessa formattazione al foglio delle classi trasversali
                trasv_worksheet = writer.sheets["Classi Trasversali"]
                trasv_worksheet.merge_range("A1:D1", "Riepilogo CFU per Classi Trasversali", header_format)
                
                # Aggiunge la stessa legenda
                trasv_worksheet.write(2, 0, "Legenda:", subheader_format)
                trasv_worksheet.write(3, 0, "P = Presenza", text_format)
                trasv_worksheet.write(3, 1, "D = Distanza", text_format)
                trasv_worksheet.write(3, 2, "--- = Non applicabile", text_format)
                
                # Applica formattazione alle intestazioni
                for col_num, value in enumerate(pivot_trasversali.columns.values):
                    trasv_worksheet.write(riepilogo_row, col_num + 1, value, header_format)
                
                # Scrive i dati del pivot con formattazione
                for row_num, (index_value, row_data) in enumerate(pivot_trasversali.iterrows()):
                    trasv_worksheet.write(row_num + riepilogo_row + 1, 0, index_value, text_format)
                    for col_num, (col_name, value) in enumerate(row_data.items()):
                        # Formattazione basata sul tipo di colonna
                        if "(P)" in col_name:
                            cell_format = p_format
                        elif "(D)" in col_name:
                            cell_format = d_format
                        elif "Tot" in col_name:
                            cell_format = tot_format
                        else:
                            cell_format = value_format
                            
                        trasv_worksheet.write(row_num + riepilogo_row + 1, col_num + 1, value, cell_format)
                
                # Imposta la larghezza delle colonne
                trasv_worksheet.set_column(0, 0, 20)  # Colonna delle classi di concorso
                trasv_worksheet.set_column(1, len(pivot_trasversali.columns), 15)  # Colonne dei CFU
            
            # NUOVO FOGLIO: Aree Formative
            # Crea un foglio per ogni percorso formativo con analisi di conformità
            for percorso in PERCORSI_CFU.keys():
                # Verifica la conformità per questo percorso
                conformita = _verifica_conformita_percorso(stats_df, percorso)
                
                # Crea un foglio Excel per questo percorso
                sheet_name = f"Aree {percorso.replace(' ', '_')}"
                percorso_worksheet = writer.book.add_worksheet(sheet_name)
                
                # Titolo del foglio
                percorso_worksheet.merge_range("A1:F1", f"Analisi CFU per Aree Formative - {percorso}", header_format)
                
                # Legenda
                percorso_worksheet.write(2, 0, "Stato conformità:", subheader_format)
                if conformita['conforme']:
                    percorso_worksheet.merge_range("B2:F2", "✓ CONFORME", conforme_format)
                else:
                    percorso_worksheet.merge_range("B2:F2", "✗ NON CONFORME", non_conforme_format)
                
                # Intestazione per le aree formative
                row = 4
                percorso_worksheet.write(row, 0, "Area Formativa", header_format)
                percorso_worksheet.write(row, 1, "CFU Presenza (P)", header_format)
                percorso_worksheet.write(row, 2, "CFU Distanza (D)", header_format)
                percorso_worksheet.write(row, 3, "CFU Erogati", header_format)
                percorso_worksheet.write(row, 4, "CFU Richiesti", header_format)
                percorso_worksheet.write(row, 5, "Stato", header_format)
                
                # Dati delle aree formative
                row = 5
                for area, dati in conformita['aree'].items():
                    percorso_worksheet.write(row, 0, area, text_format)
                    percorso_worksheet.write(row, 1, dati['erogati_P'], p_format)
                    percorso_worksheet.write(row, 2, dati['erogati_D'], d_format)
                    percorso_worksheet.write(row, 3, dati['erogati'], tot_format)
                    
                    # Usa formati diversi in base alla conformità
                    format_stato = conforme_format if dati['conforme'] else non_conforme_format
                    percorso_worksheet.write(row, 4, dati['richiesti'], value_format)
                    percorso_worksheet.write(row, 5, "✓" if dati['conforme'] else "✗", format_stato)
                    row += 1
                
                # Intestazione per le subaree trasversali
                row += 2
                percorso_worksheet.write(row, 0, "Subarea Trasversale", header_format)
                percorso_worksheet.write(row, 1, "CFU Presenza (P)", header_format)
                percorso_worksheet.write(row, 2, "CFU Distanza (D)", header_format)
                percorso_worksheet.write(row, 3, "CFU Erogati", header_format)
                percorso_worksheet.write(row, 4, "CFU Richiesti", header_format)
                percorso_worksheet.write(row, 5, "Stato", header_format)
                
                # Dati delle subaree trasversali
                row += 1
                for subarea, dati in conformita['subaree'].items():
                    percorso_worksheet.write(row, 0, subarea, text_format)
                    percorso_worksheet.write(row, 1, dati['erogati_P'], p_format)
                    percorso_worksheet.write(row, 2, dati['erogati_D'], d_format)
                    percorso_worksheet.write(row, 3, dati['erogati'], tot_format)
                    
                    # Usa formati diversi in base alla conformità
                    format_stato = conforme_format if dati['conforme'] else non_conforme_format
                    percorso_worksheet.write(row, 4, dati['richiesti'], value_format)
                    percorso_worksheet.write(row, 5, "✓" if dati['conforme'] else "✗", format_stato)
                    row += 1
                
                # Imposta la larghezza delle colonne
                percorso_worksheet.set_column(0, 0, 30)  # Colonna dell'area/subarea
                percorso_worksheet.set_column(1, 5, 15)  # Altre colonne
                
                # Aggiungi note esplicative e raccomandazioni
                row += 2
                percorso_worksheet.merge_range(row, 0, row, 5, "Note e Raccomandazioni", subheader_format)
                row += 1
                
                if conformita['conforme']:
                    percorso_worksheet.merge_range(row, 0, row, 5, 
                                               f"Il percorso {percorso} è conforme alle specifiche del DPCM 4 agosto 2023.", 
                                               text_format)
                else:
                    percorso_worksheet.merge_range(row, 0, row, 5, 
                                               f"Il percorso {percorso} NON è conforme alle specifiche del DPCM 4 agosto 2023.", 
                                               text_format)
                    row += 1
                    
                    # Elenca i problemi
                    for area, dati in conformita['aree'].items():
                        if not dati['conforme']:
                            percorso_worksheet.merge_range(row, 0, row, 5,
                                                       f"- Area {area}: Mancano {abs(dati['differenza'])} CFU",
                                                       non_conforme_format)
                            row += 1
                    
                    for subarea, dati in conformita['subaree'].items():
                        if not dati['conforme'] and dati['richiesti'] > 0:
                            percorso_worksheet.merge_range(row, 0, row, 5,
                                                       f"- Subarea {subarea}: Mancano {abs(dati['differenza'])} CFU",
                                                       non_conforme_format)
                            row += 1
            
            # Foglio con il dettaglio della classificazione degli insegnamenti
            stats_df[['Data', 'Orario', 'Docente', 'Denominazione Insegnamento', 'CFU_numeric', 
                     'Area Formativa', 'Subarea Trasversale'] + [p for p in PERCORSI_CFU if p in stats_df.columns]]\
                .to_excel(writer, sheet_name="Classificazione", index=False)
            
            # Personalizza il foglio di classificazione
            classificazione_worksheet = writer.sheets["Classificazione"]
            classificazione_worksheet.set_row(0, None, header_format)  # Formatta la riga di intestazione
            classificazione_worksheet.set_column(0, len(stats_df.columns), 15)  # Larghezza colonne
            
            # Foglio con i dati completi
            stats_df.to_excel(writer, sheet_name="Dati Completi", index=False)
            
            # Personalizza il foglio dei dati completi
            dati_worksheet = writer.sheets["Dati Completi"]
            dati_worksheet.set_row(0, None, header_format)  # Formatta la riga di intestazione
            dati_worksheet.set_column(0, len(stats_df.columns), 15)  # Larghezza colonne
        
        return percorso_file
        
    except Exception as e:
        # Log dell'errore
        try:
            from log_utils import logger
            logger.error(f"Errore durante l'esportazione del riepilogo CFU: {str(e)}")
        except ImportError:
            pass
        
        return None


def _classifica_insegnamenti_per_area(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica gli insegnamenti nelle aree formative definite dal DPCM 4 agosto 2023.
    
    Args:
        df: DataFrame con i dati delle lezioni
        
    Returns:
        pd.DataFrame: DataFrame con le colonne aggiuntive 'Area Formativa', 'Subarea Trasversale' e 'Gruppo Trasversale'
    """
    # Crea una copia del DataFrame per non modificare l'originale
    result_df = df.copy()
    
    # Aggiungi colonne per l'area formativa, la subarea trasversale e il gruppo trasversale
    result_df['Area Formativa'] = 'Non classificato'
    result_df['Subarea Trasversale'] = None
    result_df['Gruppo Trasversale'] = None
    
    # Importa le definizioni dai gruppi di classi
    from percorsi_formativi import CLASSI_TRASVERSALI, CLASSI_GRUPPO_A, CLASSI_GRUPPO_B
    
    # Classifica ogni insegnamento in base alla sua denominazione e alla classe di concorso
    for idx, row in result_df.iterrows():
        denominazione = row.get('Denominazione Insegnamento', '')
        classe_concorso = row.get('Insegnamento comune', '')
        
        # Classifica automaticamente come Trasversale se appartiene alle classi trasversali
        if classe_concorso in CLASSI_TRASVERSALI:
            result_df.at[idx, 'Area Formativa'] = 'Trasversale'
            
            # Distingue tra Trasversale A e B
            if classe_concorso == "Trasversale A":
                result_df.at[idx, 'Gruppo Trasversale'] = "A"
            elif classe_concorso == "Trasversale B":
                result_df.at[idx, 'Gruppo Trasversale'] = "B"
                
            # Cerca di assegnare una subarea basandosi sulla denominazione
            if not pd.isna(denominazione) and denominazione:
                classificazione = classifica_insegnamento(denominazione, classe_concorso)
                result_df.at[idx, 'Subarea Trasversale'] = classificazione['subarea']
        else:
            # Per tutte le altre classi di concorso, usa la funzione di classificazione completa
            if not pd.isna(denominazione) and denominazione:
                classificazione = classifica_insegnamento(denominazione, classe_concorso)
                result_df.at[idx, 'Area Formativa'] = classificazione['area']
                result_df.at[idx, 'Subarea Trasversale'] = classificazione['subarea']
                
                # Determina il gruppo (A o B) in base alla classe di concorso
                if classe_concorso in CLASSI_GRUPPO_A:
                    result_df.at[idx, 'Gruppo Trasversale'] = "A"
                elif classe_concorso in CLASSI_GRUPPO_B:
                    result_df.at[idx, 'Gruppo Trasversale'] = "B"
    
    return result_df


def _calcola_cfu_per_area(df: pd.DataFrame, percorso: str = None) -> pd.DataFrame:
    """
    Calcola i CFU erogati per ogni area formativa (e subarea trasversale) per un percorso specifico.
    
    Args:
        df: DataFrame con i dati delle lezioni classificati per area
        percorso: Nome del percorso da analizzare (se None, considera tutti i percorsi)
        
    Returns:
        pd.DataFrame: Pivot table con i CFU per area formativa e modalità
    """
    # Crea una copia del DataFrame
    stats_df = df.copy()
    
    # Se è specificato un percorso, filtra solo per quel percorso
    if percorso is not None and percorso in PERCORSI_CFU:
        # Filtra le righe dove il percorso è 'P' o 'D' (esclude '---')
        stats_df = stats_df[(stats_df[percorso] == 'P') | (stats_df[percorso] == 'D')]
        
        # Calcola i CFU per area formativa, distinguendo tra P e D
        pivot_area = pd.pivot_table(
            stats_df,
            values='CFU_numeric',
            index=['Area Formativa'],
            columns=[percorso],
            aggfunc='sum',
            fill_value=0
        )
        
        # Calcola i CFU per subarea trasversale (solo per l'area Trasversale)
        trasversale_df = stats_df[stats_df['Area Formativa'] == 'Trasversale']
        if not trasversale_df.empty:
            pivot_subarea = pd.pivot_table(
                trasversale_df,
                values='CFU_numeric',
                index=['Subarea Trasversale'],
                columns=[percorso],
                aggfunc='sum',
                fill_value=0
            )
        else:
            # Se non ci sono dati per le aree trasversali
            pivot_subarea = pd.DataFrame(index=SUBAREE_TRASVERSALI)
            for modalita in ['P', 'D']:
                pivot_subarea[modalita] = 0
    else:
        # Se non è specificato un percorso, calcola i CFU totali per area
        pivot_area = pd.pivot_table(
            stats_df,
            values='CFU_numeric',
            index=['Area Formativa'],
            aggfunc='sum',
            fill_value=0
        )
        pivot_area.columns = ['Totale']
        
        # Calcola i CFU per subarea trasversale
        trasversale_df = stats_df[stats_df['Area Formativa'] == 'Trasversale']
        if not trasversale_df.empty:
            pivot_subarea = pd.pivot_table(
                trasversale_df,
                values='CFU_numeric',
                index=['Subarea Trasversale'],
                aggfunc='sum',
                fill_value=0
            )
            pivot_subarea.columns = ['Totale']
        else:
            # Se non ci sono dati per le aree trasversali
            pivot_subarea = pd.DataFrame(index=SUBAREE_TRASVERSALI)
            pivot_subarea['Totale'] = 0
    
    return pivot_area, pivot_subarea


def _verifica_conformita_percorso(df: pd.DataFrame, percorso: str) -> Dict:
    """
    Verifica la conformità dei CFU erogati rispetto ai requisiti del percorso formativo.
    
    Args:
        df: DataFrame con i dati delle lezioni classificati per area
        percorso: Nome del percorso da analizzare
        
    Returns:
        Dict: Dizionario con informazioni sulla conformità, con chiavi:
            - 'conforme': bool, True se tutti i CFU sono conformi
            - 'aree': Dict con chiave=area, valore=dict con 'erogati', 'richiesti', 'differenza'
            - 'subaree': Dict per le subaree trasversali
    """
    if percorso not in PERCORSI_CFU:
        return {'conforme': False, 'errore': f'Percorso {percorso} non definito'}
    
    # Calcola i CFU erogati per area e subarea
    pivot_area, pivot_subarea = _calcola_cfu_per_area(df, percorso)
    
    # Requisiti CFU per il percorso
    requisiti = PERCORSI_CFU[percorso]
    
    # Prepara la struttura del risultato
    risultato = {
        'conforme': True,
        'aree': {},
        'subaree': {}
    }
    
    # Verifica conformità per ogni area formativa
    for area in AREE_FORMATIVE:
        cfu_richiesti = requisiti.get(area, 0)
        
        # Calcola CFU erogati (somma di P e D)
        if area in pivot_area.index:
            cfu_erogati_P = pivot_area.loc[area, 'P'] if 'P' in pivot_area.columns else 0
            cfu_erogati_D = pivot_area.loc[area, 'D'] if 'D' in pivot_area.columns else 0
            cfu_erogati = cfu_erogati_P + cfu_erogati_D
        else:
            cfu_erogati_P = 0
            cfu_erogati_D = 0
            cfu_erogati = 0
        
        # Calcola la differenza
        differenza = cfu_erogati - cfu_richiesti
        
        # Aggiorna lo stato di conformità
        if differenza < 0:
            risultato['conforme'] = False
        
        # Salva i dettagli per questa area
        risultato['aree'][area] = {
            'erogati': round(cfu_erogati, 1),
            'erogati_P': round(cfu_erogati_P, 1),
            'erogati_D': round(cfu_erogati_D, 1),
            'richiesti': cfu_richiesti,
            'differenza': round(differenza, 1),
            'conforme': differenza >= 0
        }
    
    # Verifica conformità per le subaree dell'area trasversale
    subaree_requisiti = requisiti.get('Trasversale_dettaglio', {})
    for subarea in SUBAREE_TRASVERSALI:
        cfu_richiesti = subaree_requisiti.get(subarea, 0)
        
        # Calcola CFU erogati
        if subarea in pivot_subarea.index:
            cfu_erogati_P = pivot_subarea.loc[subarea, 'P'] if 'P' in pivot_subarea.columns else 0
            cfu_erogati_D = pivot_subarea.loc[subarea, 'D'] if 'D' in pivot_subarea.columns else 0
            cfu_erogati = cfu_erogati_P + cfu_erogati_D
        else:
            cfu_erogati_P = 0
            cfu_erogati_D = 0
            cfu_erogati = 0
        
        # Calcola la differenza
        differenza = cfu_erogati - cfu_richiesti
        
        # Aggiorna lo stato di conformità se necessario
        if differenza < 0 and cfu_richiesti > 0:
            risultato['conforme'] = False
        
        # Salva i dettagli per questa subarea
        risultato['subaree'][subarea] = {
            'erogati': round(cfu_erogati, 1),
            'erogati_P': round(cfu_erogati_P, 1),
            'erogati_D': round(cfu_erogati_D, 1),
            'richiesti': cfu_richiesti,
            'differenza': round(differenza, 1),
            'conforme': differenza >= 0 or cfu_richiesti == 0
        }
    
    return risultato


def mostra_riepilogo_cfu_per_area(df: pd.DataFrame):
    """
    Mostra un riepilogo dei CFU per area formativa (Disciplinare, Trasversale, Tirocinio Diretto, Tirocinio Indiretto)
    secondo le specifiche del DPCM 4 agosto 2023.
    
    Args:
        df: DataFrame con i dati delle lezioni
    """
    st.subheader("📊 Analisi CFU per Aree Formative (DPCM 4 agosto 2023)")
    
    # Aggiungi filtro per dipartimento
    col1, col2 = st.columns([1, 2])
    with col1:
        if 'Dipartimento' in df.columns:
            dipartimenti_list = ["Tutti"] + sorted(df['Dipartimento'].dropna().unique().tolist())
            selected_dipartimento = st.selectbox("Filtro Dipartimento:", dipartimenti_list, key="dipartimento_area_formativa")
            
            # Salva il dataframe originale completo per le trasversali
            df_completo = df.copy()
            
            # Applica filtro per dipartimento se selezionato
            if selected_dipartimento != "Tutti":
                # Estrai le classi trasversali prima di filtrare
                from percorsi_formativi import CLASSI_TRASVERSALI
                trasversali_df = df[df['Insegnamento comune'].isin(CLASSI_TRASVERSALI)]
                
                # Filtra il resto per dipartimento
                df_filtrato_specifiche = df[~df['Insegnamento comune'].isin(CLASSI_TRASVERSALI)]
                df_filtrato_specifiche = df_filtrato_specifiche[df_filtrato_specifiche['Dipartimento'] == selected_dipartimento]
                
                # Ricombina i dataframe
                df_filtrato = pd.concat([df_filtrato_specifiche, trasversali_df])
                
                num_records = len(df_filtrato_specifiche)  # Contiamo solo le specifiche per l'informazione
                st.info(f"📊 Visualizzando {num_records} record specifici del dipartimento {selected_dipartimento} (più insegnamenti trasversali)")
            else:
                df_filtrato = df
                num_records = len(df)
                st.info(f"📊 Visualizzando tutti i {num_records} record")
        else:
            df_filtrato = df
            st.warning("⚠️ Campo 'Dipartimento' non presente nei dati")
    
    # Lavora con il dataframe filtrato da qui in avanti
    df = df_filtrato
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per l'analisi dei CFU per aree formative")
        return
    
    # Prepara i dati
    stats_df = df.copy()
    
    # Pulisci e standardizza i valori dei CFU
    stats_df['CFU_clean'] = stats_df['CFU'].astype(str).str.replace(',', '.')
    stats_df['CFU_clean'] = stats_df['CFU_clean'].replace('nan', '0')
    stats_df['CFU_numeric'] = pd.to_numeric(stats_df['CFU_clean'], errors='coerce').fillna(0)
    
    # Rimuovi i duplicati per avere conteggi accurati
    stats_df = stats_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Espandi le classi multiple invece di filtrarle
    # In questo modo i CFU dei record con classi combinate vengono assegnati a ciascuna classe individuale
    stats_df = _espandi_classi_multiple(stats_df)
    
    # Classifica gli insegnamenti per area formativa
    stats_df = _classifica_insegnamenti_per_area(stats_df)
    
    # Aggiunge il filtro per classe di concorso
    st.write("### Seleziona Classe di Concorso")
    st.write("L'analisi CFU è significativa quando filtrata per una specifica classe di concorso.")
    
    # Ottieni tutte le classi di concorso disponibili
    from percorsi_formativi import CLASSI_TRASVERSALI
    classi_concorso = sorted(stats_df['Insegnamento comune'].dropna().unique())
    
    # Dividi le classi in specifiche e trasversali per una migliore organizzazione
    classi_specifiche = [c for c in classi_concorso if c not in CLASSI_TRASVERSALI]
    classi_trasversali = [c for c in classi_concorso if c in CLASSI_TRASVERSALI]
    
    # Crea le opzioni per il selectbox con una categorizzazione chiara
    opzioni = ["Tutte le classi"]
    if classi_specifiche:
        opzioni.append("--- Classi Specifiche ---")
        opzioni.extend(classi_specifiche)
    if classi_trasversali:
        opzioni.append("--- Classi Trasversali ---")
        opzioni.extend(classi_trasversali)
    
    # Selectbox per scegliere la classe di concorso
    classe_selezionata = st.selectbox(
        "Seleziona una classe di concorso:",
        opzioni,
        index=opzioni.index("A008") if "A008" in opzioni else 0,
        help="Per un'analisi accurata, seleziona una classe di concorso specifica"
    )
    
    # Importa le definizioni dei gruppi A e B
    from percorsi_formativi import CLASSI_GRUPPO_A, CLASSI_GRUPPO_B
    
    # Filtra per classe selezionata (se non è una delle intestazioni o "Tutte le classi")
    filtered_df = stats_df
    if classe_selezionata not in ["Tutte le classi", "--- Classi Specifiche ---", "--- Classi Trasversali ---"]:
        filtered_df = stats_df[stats_df['Insegnamento comune'] == classe_selezionata]
        
        # Aggiungi le classi trasversali appropriate in base al gruppo (A o B)
        if classe_selezionata not in CLASSI_TRASVERSALI:
            # Determina se la classe selezionata appartiene al gruppo A (umanistico) o B (scientifico)
            gruppo_trasversale = None
            if classe_selezionata in CLASSI_GRUPPO_A:
                gruppo_trasversale = "A"
                trasversali_df = stats_df[stats_df['Insegnamento comune'] == "Trasversale A"]
                st.info("📚 La classe selezionata appartiene al gruppo umanistico (A). Inclusi CFU della Trasversale A.")
            elif classe_selezionata in CLASSI_GRUPPO_B:
                gruppo_trasversale = "B"
                trasversali_df = stats_df[stats_df['Insegnamento comune'] == "Trasversale B"]
                st.info("🧪 La classe selezionata appartiene al gruppo scientifico (B). Inclusi CFU della Trasversale B.")
            else:
                # Se non appartiene a nessun gruppo conosciuto, includi entrambe le trasversali
                trasversali_df = stats_df[stats_df['Insegnamento comune'].isin(["Trasversale A", "Trasversale B"])]
                st.warning("⚠️ La classe selezionata non è classificata nei gruppi A o B. Inclusi CFU di entrambe le trasversali.")
            
            # Aggiungi le altre classi trasversali generiche (non A o B specifiche)
            altre_trasversali = [t for t in CLASSI_TRASVERSALI if t not in ["Trasversale A", "Trasversale B"]]
            if altre_trasversali:
                altre_trasversali_df = stats_df[stats_df['Insegnamento comune'].isin(altre_trasversali)]
                trasversali_df = pd.concat([trasversali_df, altre_trasversali_df])
            
            # Unisci i dataframe
            filtered_df = pd.concat([filtered_df, trasversali_df])
    
    # Avviso se nessuna classe specifica è selezionata
    if classe_selezionata == "Tutte le classi":
        st.warning("⚠️ Per un'analisi più accurata, seleziona una classe di concorso specifica")
        
    # Mostra quali dati stiamo analizzando
    if classe_selezionata not in ["Tutte le classi", "--- Classi Specifiche ---", "--- Classi Trasversali ---"]:
        st.success(f"Analisi CFU per la classe: **{classe_selezionata}** (include anche le aree trasversali)")
    
    # Crea una variabile di sessione per tenere traccia della tab selezionata
    if "tab_selezionata" not in st.session_state:
        st.session_state.tab_selezionata = "Panoramica"
        
    # Lista dei tab (percorsi formativi)
    tab_names = ["Panoramica"] + list(PERCORSI_CFU.keys())
    
    # Crea tabs per ogni percorso formativo (converte dict_keys in lista)
    tabs = st.tabs(tab_names)
    
    # Tab Panoramica: Quadro generale di tutti i CFU
    with tabs[0]:
        # Aggiorna la tab selezionata
        st.session_state.tab_selezionata = "Panoramica"
        
        st.write("### Panoramica CFU per Aree Formative")
        
        # Calcola i CFU totali per area formativa usando il DataFrame filtrato
        pivot_area, pivot_subarea = _calcola_cfu_per_area(filtered_df)
        
        # Visualizza i CFU totali per area formativa
        st.write("#### CFU per Area Formativa")
        st.dataframe(pivot_area, use_container_width=True)
        
        # Nota: Rimossa la tabella CFU per Subarea Trasversale perché non necessaria
    
    # Tab per ciascun percorso formativo
    for i, percorso in enumerate(PERCORSI_CFU.keys()):
        with tabs[i+1]:
            # Aggiorna la tab selezionata quando l'utente clicca su un tab
            st.session_state.tab_selezionata = percorso
            
            st.write(f"### Analisi CFU - {percorso}")
            
            # Avviso informativo sui tirocini se stiamo visualizzando un percorso che li include
            requisiti_percorso = PERCORSI_CFU[percorso]
            if requisiti_percorso.get("Tirocinio Diretto", 0) > 0 or requisiti_percorso.get("Tirocinio Indiretto", 0) > 0:
                st.info("ℹ️ Le aree di tirocinio sono previste nel DPCM ma non ancora implementate nell'applicazione.")
            
            # Verifica la conformità del percorso usando il DataFrame filtrato
            conformita = _verifica_conformita_percorso(filtered_df, percorso)
            
            # Mostra stato generale di conformità
            if conformita['conforme']:
                st.success(f"✅ Il percorso {percorso} è conforme ai requisiti del DPCM 4 agosto 2023")
            else:
                st.error(f"❌ Il percorso {percorso} NON è conforme ai requisiti del DPCM 4 agosto 2023")
            
            # Mostra solo le aree formative principali (rimossa la visualizzazione delle subaree)
            st.write("#### CFU per Area Formativa")
            
            # Crea dataframe per visualizzazione
            aree_data = []
            for area, dati in conformita['aree'].items():
                stato = "✅" if dati['conforme'] else "❌"
                aree_data.append({
                    "Area": area,
                    "CFU Erogati": dati['erogati'],
                    "CFU Richiesti": dati['richiesti'],
                    "Differenza": dati['differenza'],
                    "Stato": stato
                })
            
            aree_df = pd.DataFrame(aree_data)
            st.dataframe(aree_df, use_container_width=True, hide_index=True)
            
            # Visualizzazione informazioni sulla classe di concorso selezionata
            if classe_selezionata not in ["Tutte le classi", "--- Classi Specifiche ---", "--- Classi Trasversali ---"]:
                with st.expander("📚 Dettagli CFU per la classe di concorso selezionata"):
                    # Filtra solo i record della classe selezionata
                    solo_classe_df = stats_df[stats_df['Insegnamento comune'] == classe_selezionata]
                    
                    # Calcola CFU totali per questa classe
                    cfu_classe_totale = solo_classe_df['CFU_numeric'].sum()
                    
                    # Visualizza informazioni sulla classe
                    st.write(f"**Classe di concorso:** {classe_selezionata}")
                    
                    # Determina a quale gruppo trasversale appartiene la classe (A o B)
                    from percorsi_formativi import CLASSI_GRUPPO_A, CLASSI_GRUPPO_B
                    gruppo_trasversale = None
                    if classe_selezionata in CLASSI_GRUPPO_A:
                        gruppo_trasversale = "A"
                        st.info(f"📌 Questa classe appartiene al gruppo A (Trasversale A)")
                    elif classe_selezionata in CLASSI_GRUPPO_B:
                        gruppo_trasversale = "B"
                        st.info(f"📌 Questa classe appartiene al gruppo B (Trasversale B)")
                    
                    # Il filtro per percorsi formativi ora viene impostato automaticamente in base al tab selezionato
                    percorsi_disponibili = ["Tutti"] + [p for p in PERCORSI if p in stats_df.columns]
                    
                    # Imposta il valore predefinito in base alla tab selezionata
                    default_percorso_idx = 0  # Default: "Tutti"
                    if st.session_state.tab_selezionata != "Panoramica" and st.session_state.tab_selezionata in percorsi_disponibili:
                        default_percorso_idx = percorsi_disponibili.index(st.session_state.tab_selezionata)
                    
                    percorso_filtro = st.selectbox(
                        "Filtra per percorso formativo:", 
                        percorsi_disponibili,
                        index=default_percorso_idx,
                        key=f"filtro_percorso_{classe_selezionata}_{percorso}"
                    )
                    
                    # Mostra il dettaglio degli insegnamenti per questa classe, includendo le trasversali
                    if not solo_classe_df.empty:
                        # Determina quali trasversali includere
                        trasversali_da_includere = []
                        if gruppo_trasversale == "A":
                            trasversali_da_includere = ["Trasversale A"]
                        elif gruppo_trasversale == "B":
                            trasversali_da_includere = ["Trasversale B"]
                        
                        # Ottieni i dati delle trasversali appropriate
                        trasversali_df = stats_df[stats_df['Insegnamento comune'].isin(trasversali_da_includere)]
                        
                        # Unisci i dataframe della classe specifica e delle trasversali
                        insegnamenti_completi_df = pd.concat([solo_classe_df, trasversali_df])
                        
                        # Applica il filtro per percorso se selezionato
                        if percorso_filtro != "Tutti" and percorso_filtro in insegnamenti_completi_df.columns:
                            # Filtra solo le righe dove il percorso è 'P' o 'D' (esclude '---')
                            insegnamenti_completi_df = insegnamenti_completi_df[
                                insegnamenti_completi_df[percorso_filtro].isin(['P', 'D'])
                            ]
                            st.write(f"**Insegnamenti specifici e trasversali per questa classe (filtrati per {percorso_filtro}):**")
                        else:
                            st.write("**Insegnamenti specifici e trasversali per questa classe:**")
                        
                        # Definisci tutte le colonne disponibili con priorità
                        available_cols = {
                            # Colonne principali
                            'Data': 'Data',
                            'Orario': 'Orario',
                            'Docente': 'Docente',
                            'Insegnamento comune': 'Classe',
                            'Denominazione Insegnamento': 'Insegnamento',
                            'CFU_numeric': 'CFU',
                            'Area Formativa': 'Area Formativa',
                            # Colonne logistiche
                            'Aula': 'Aula',
                            'Link Teams': 'Link Teams',
                            'Codice Insegnamento': 'Codice Insegnamento',
                            # Altre colonne se presenti
                            'Dipartimento': 'Dipartimento',
                            'Tipo': 'Tipo',
                            'Note': 'Note'
                        }
                        
                        # Verifica quali colonne sono effettivamente disponibili nel dataframe
                        actual_available_cols = {}
                        for k, v in available_cols.items():
                            if k in insegnamenti_completi_df.columns:
                                actual_available_cols[k] = v
                        
                        # Raggruppa le colonne per categoria per una migliore organizzazione dell'interfaccia
                        colonne_principali = ['Data', 'Orario', 'Insegnamento comune', 'Denominazione Insegnamento', 'CFU_numeric', 'Docente']
                        colonne_logistiche = ['Aula', 'Link Teams', 'Codice Insegnamento']
                        colonne_dettaglio = ['Area Formativa', 'Dipartimento', 'Tipo', 'Note']
                        
                        # Colonne predefinite da mostrare (priorità a quelle principali e logistiche)
                        default_cols = []
                        # Aggiungi colonne principali se disponibili
                        for col in colonne_principali:
                            if col in insegnamenti_completi_df.columns:
                                default_cols.append(col)
                        # Aggiungi colonne logistiche se disponibili
                        for col in colonne_logistiche:
                            if col in insegnamenti_completi_df.columns:
                                default_cols.append(col)
                        # Aggiungi Area Formativa se disponibile
                        if 'Area Formativa' in insegnamenti_completi_df.columns:
                            default_cols.append('Area Formativa')
                        
                        # Crea una chiave univoca basata solo sulla classe e il percorso (più stabile)
                        stable_key = f"col_select_{classe_selezionata}_{percorso}"
                        
                        # Crea un layout con 3 colonne
                        col1, col2, col3 = st.columns([1, 2, 1])
                        
                        with col1:
                            st.write("Seleziona colonne:")
                            
                        with col3:
                            # Pulsante per resettare le colonne
                            if st.button("Reset colonne", key=f"btn_reset_{stable_key}"):
                                if stable_key in st.session_state:
                                    del st.session_state[stable_key]
                                st.rerun()  # Forza il refresh della pagina
                                
                        # Dizionario per mappare nomi visualizzati alle chiavi originali
                        col_mapping = {}
                        for k, v in actual_available_cols.items():
                            col_mapping[v] = k
                            
                        # Ottieni le opzioni disponibili per categorie
                        options_principali = [actual_available_cols[col] for col in colonne_principali if col in actual_available_cols]
                        options_logistiche = [actual_available_cols[col] for col in colonne_logistiche if col in actual_available_cols]
                        options_dettaglio = [actual_available_cols[col] for col in colonne_dettaglio if col in actual_available_cols]
                        
                        # Tutte le opzioni disponibili per il multiselect
                        all_options = options_principali + options_logistiche + options_dettaglio
                        
                        # Valori predefiniti
                        default_values = [actual_available_cols[col] for col in default_cols if col in actual_available_cols]
                        
                        with col2:
                            # Usa st.multiselect con una chiave stabile e salva la selezione nella session_state
                            selected_col_names = st.multiselect(
                                "Colonne da visualizzare", 
                                all_options,
                                default=default_values if stable_key not in st.session_state else st.session_state[stable_key],
                                key=stable_key
                            )
                        
                        # Gestione più robusta della selezione delle colonne
                        try:
                            # Converti i nomi visualizzati nelle chiavi originali usando il dizionario di mappatura
                            if not selected_col_names:
                                # Se non ci sono colonne selezionate, usa quelle predefinite
                                selected_cols = default_cols
                                st.warning("Nessuna colonna selezionata, utilizzo le colonne predefinite")
                            else:
                                # Mappa i nomi selezionati alle chiavi del dataframe
                                selected_cols = [col_mapping[name] for name in selected_col_names if name in col_mapping]
                                
                                # Se la conversione fallisce, usa le colonne predefinite
                                if not selected_cols:
                                    selected_cols = default_cols
                                    st.warning("Problema nella selezione delle colonne, utilizzo le colonne predefinite")
                        except Exception as e:
                            # In caso di errore, usa le colonne predefinite
                            st.error(f"Errore durante la gestione delle colonne: {str(e)}")
                            selected_cols = default_cols
                        
                        # Verifica che tutte le colonne selezionate esistano nel dataframe
                        valid_cols = [col for col in selected_cols if col in insegnamenti_completi_df.columns]
                        
                        # Aggiungi la colonna del percorso selezionato se applicabile
                        percorso_col = []
                        if percorso_filtro != "Tutti" and percorso_filtro in insegnamenti_completi_df.columns:
                            percorso_col = [percorso_filtro]
                        
                        # Definisci le colonne finali da visualizzare
                        final_cols = valid_cols + percorso_col
                        
                        # Verifica che ci siano colonne valide da visualizzare
                        if not final_cols:
                            st.warning("Nessuna colonna valida selezionata. Ripristino le colonne predefinite.")
                            final_cols = [col for col in default_cols if col in insegnamenti_completi_df.columns]
                            if percorso_col:
                                final_cols += percorso_col
                        
                        # Crea il dataframe da visualizzare
                        insegnamenti_df = insegnamenti_completi_df[final_cols].copy()
                        
                        # Formatta la data se è un oggetto datetime
                        if 'Data' in insegnamenti_df.columns and hasattr(insegnamenti_df['Data'], 'dt'):
                            insegnamenti_df['Data'] = insegnamenti_df['Data'].dt.strftime('%d/%m/%Y')
                            
                        # Rinomina le colonne per una migliore leggibilità
                        renamed_cols = {k: v for k, v in available_cols.items() if k in selected_cols}
                        # Aggiungi anche il rename per il percorso se presente
                        if percorso_filtro != "Tutti" and percorso_filtro in insegnamenti_completi_df.columns:
                            renamed_cols[percorso_filtro] = 'Modalità'
                            
                        insegnamenti_df = insegnamenti_df.rename(columns=renamed_cols)
                        
                        # Ordina per data e orario
                        if 'Data' in insegnamenti_df.columns and 'Orario' in insegnamenti_df.columns:
                            insegnamenti_df = insegnamenti_df.sort_values(['Data', 'Orario'])
                        
                        # Visualizza la tabella
                        st.dataframe(insegnamenti_df, use_container_width=True, hide_index=True)
                        
                        # Aggiungi opzione per scaricare l'elenco delle lezioni
                        percorso_nome = percorso_filtro if percorso_filtro != "Tutti" else "tutti_percorsi"
                        st.download_button(
                            label="📄 Scarica elenco lezioni",
                            data=insegnamenti_df.to_csv(index=False),
                            file_name=f"lezioni_{classe_selezionata}_{percorso_nome}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            key=f"download_dettaglio_classe_{classe_selezionata}_{percorso}_{id(insegnamenti_df)}"
                        )
                    else:
                        st.warning("⚠️ Nessun insegnamento trovato per questa classe nel periodo selezionato.")
    return

def mostra_riepilogo_cfu_per_percorso(df: pd.DataFrame):
    """
    Mostra un riepilogo dei CFU per percorso formativo (PeF60, PeF30, ecc.)
    secondo le specifiche del DPCM 4 agosto 2023.
    
    Args:
        df: DataFrame con i dati delle lezioni
    """
    st.subheader("📊 Analisi CFU per Percorsi Formativi (DPCM 4 agosto 2023)")
    
    if df is None or df.empty:
        st.info("Nessun dato disponibile per l'analisi dei CFU per percorsi formativi")
        return
    
    # Prepara i dati
    stats_df = df.copy()
    
    # Pulisci e standardizza i valori dei CFU
    stats_df['CFU_clean'] = stats_df['CFU'].astype(str).str.replace(',', '.')
    stats_df['CFU_clean'] = stats_df['CFU_clean'].replace('nan', '0')
    stats_df['CFU_numeric'] = pd.to_numeric(stats_df['CFU_clean'], errors='coerce').fillna(0)
    
    # Rimuovi i duplicati per avere conteggi accurati
    stats_df = stats_df.drop_duplicates(subset=['Data', 'Orario', 'Docente', 'Denominazione Insegnamento'])
    
    # Espandi le classi multiple invece di filtrarle
    # In questo modo i CFU dei record con classi combinate vengono assegnati a ciascuna classe individuale
    stats_df = _espandi_classi_multiple(stats_df)
    
    # Classifica gli insegnamenti per area formativa
    stats_df = _classifica_insegnamenti_per_area(stats_df)
    
    # Crea tabs per ogni percorso formativo (converte dict_keys in lista)
    tabs = st.tabs(["Panoramica"] + list(PERCORSI_CFU.keys()))
    
    # Tab Panoramica: Quadro generale di tutti i CFU
    with tabs[0]:
        st.write("### Panoramica CFU per Aree Formative")
        
        # Calcola i CFU totali per area formativa usando il DataFrame filtrato
        pivot_area, pivot_subarea = _calcola_cfu_per_area(stats_df)
        
        # Visualizza i CFU totali per area formativa
        st.write("#### CFU per Area Formativa")
        st.dataframe(pivot_area, use_container_width=True)
        
        # Nota: Rimossa la tabella CFU per Subarea Trasversale perché non necessaria
    
    # Tab per ciascun percorso formativo
    for i, percorso in enumerate(PERCORSI_CFU.keys()):
        with tabs[i+1]:
            st.write(f"### Analisi CFU - {percorso}")
            
            # Avviso informativo sui tirocini se stiamo visualizzando un percorso che li include
            requisiti_percorso = PERCORSI_CFU[percorso]
            if requisiti_percorso.get("Tirocinio Diretto", 0) > 0 or requisiti_percorso.get("Tirocinio Indiretto", 0) > 0:
                st.info("ℹ️ Le aree di tirocinio sono previste nel DPCM ma non ancora implementate nell'applicazione.")
            
            # Verifica la conformità del percorso usando il DataFrame filtrato
            conformita = _verifica_conformita_percorso(stats_df, percorso)
            
            # Mostra stato generale di conformità
            if conformita['conforme']:
                st.success(f"✅ Il percorso {percorso} è conforme ai requisiti del DPCM 4 agosto 2023")
            else:
                st.error(f"❌ Il percorso {percorso} NON è conforme ai requisiti del DPCM 4 agosto 2023")
            
            # Mostra solo le aree formative principali (rimossa la visualizzazione delle subaree)
            st.write("#### CFU per Area Formativa")
            
            # Crea dataframe per visualizzazione
            aree_data = []
            for area, dati in conformita['aree'].items():
                stato = "✅" if dati['conforme'] else "❌"
                aree_data.append({
                    "Area": area,
                    "CFU Erogati": dati['erogati'],
                    "CFU Richiesti": dati['richiesti'],
                    "Differenza": dati['differenza'],
                    "Stato": stato
                })
            
            aree_df = pd.DataFrame(aree_data)
            st.dataframe(aree_df, use_container_width=True, hide_index=True)
            
            # Nota: Rimossa la visualizzazione delle Subaree Trasversali per semplificare l'interfaccia
            
            # Nota: Rimossa anche la sezione "Dettaglio CFU per Modalità" per semplificare ulteriormente l'interfaccia
            
            # Nota: Rimossa la sezione "Suggerimenti per risolvere le non conformità" per semplificare l'interfaccia
    return
