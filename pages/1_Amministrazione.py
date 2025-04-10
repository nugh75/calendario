import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys

# Aggiungi la directory principale al path per poter importare i moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from admin_utils import (
    is_admin_logged_in, upload_excel_file, save_dataframe_to_csv, 
    edit_record, create_new_record, delete_record, create_sample_excel
)
# Importa la nuova funzione per le statistiche
from nuova_funzione_statistiche import mostra_statistiche_docenti

# Configurazione pagina
st.set_page_config(
    page_title="Amministrazione Calendario",
    page_icon="🔒",
    layout="wide"
)

# Titolo della pagina
st.title("Amministrazione Calendario Lezioni")

# Verifica se l'utente è loggato come amministratore
if not is_admin_logged_in():
    st.warning("Accesso non autorizzato. Effettua il login come amministratore dalla pagina principale.")
    st.stop()
else:
    st.success("Accesso effettuato come amministratore")

# Funzione per caricare i dati (stessa di app.py)
def load_data():
    import locale
    try:
        locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'it_IT')
        except:
            pass

    file_path = os.path.join('dati', 'dati.csv')
    
    if not os.path.exists(file_path):
        csv_files = [f for f in os.listdir('dati') if f.endswith('.csv')]
        if not csv_files:
            st.error("Nessun file CSV trovato nella cartella 'dati'")
            return None
        file_path = os.path.join('dati', sorted(csv_files)[-1])
    
    try:
        df = pd.read_csv(file_path, delimiter=';', encoding='utf-8', skiprows=3)
        
        df.columns = [
            'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
            'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
            'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
            'Aula', 'Link Teams', 'CFU', 'Note', 'Giorno', 'Mese', 'Anno'
        ]
        
        df = df[df['Orario'].notna() & (df['Orario'] != '')]
        
        # Rimuovi i decimali dai codici insegnamento
        if 'Codice insegnamento' in df.columns:
            df['Codice insegnamento'] = df['Codice insegnamento'].astype(str).apply(
                lambda x: x.split('.')[0] if '.' in x else x
            )
        
        def parse_date(date_str):
            if pd.isna(date_str):
                return None
            try:
                return pd.to_datetime(date_str, format='%A %d %B %Y')
            except:
                try:
                    date = pd.to_datetime(date_str)
                    return date
                except:
                    return None

        df['Data'] = df['Data'].apply(parse_date)
        df = df.dropna(subset=['Data'])
        df['Giorno'] = df['Data'].dt.strftime('%A')
        df['Mese'] = df['Data'].dt.strftime('%B')
        df['Anno'] = df['Data'].dt.year
        
        return df
        
    except Exception as e:
        st.error(f"Errore durante il caricamento dei dati: {e}")
        return None

# Carica i dati
df = load_data()

# Aggiungi pulsante per ricaricare i dati
if st.button("🔄 Ricarica dati"):
    st.experimental_memo.clear()
    st.rerun()

if df is not None:
    # Tabs per separare le diverse funzionalità
    admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs(["Importa dati", "Gestione record", "Scarica esempi", "Statistiche"])
    
    with admin_tab1:
        st.subheader("Importazione massiva da Excel")
        st.write("Carica un file Excel contenente i dati del calendario. Il file deve avere la stessa struttura del file di esempio.")
        
        # Upload del file Excel
        uploaded_df = upload_excel_file()
        
        if uploaded_df is not None:
            st.write("Anteprima dei dati caricati:")
            st.dataframe(uploaded_df.head(10))
            
            if st.button("Salva dati importati"):
                file_path = save_dataframe_to_csv(uploaded_df)
                st.success(f"Dati salvati con successo nel file: {file_path}")
                st.info("Ricarica la pagina per vedere i nuovi dati")
    
    with admin_tab2:
        st.subheader("Gestione dei record")
        st.write("Puoi modificare, aggiungere o eliminare record del calendario.")
        
        # Inizializza lo stato della sessione se non esiste
        if 'edit_mode' not in st.session_state:
            st.session_state.edit_mode = False
            st.session_state.edit_index = None
            
        # Inizializza la lista dei record selezionati per l'eliminazione multipla
        if 'selected_records' not in st.session_state:
            st.session_state.selected_records = []
            
        admin_df = df.copy()
        
        # Mostra la tabella con i dati attuali
        if not st.session_state.edit_mode:
            st.write("Dati attuali:")
            
            # Crea una versione visualizzabile del dataframe con indice
            display_df = admin_df.copy()
            display_df['Data'] = display_df['Data'].dt.strftime('%a %d %b %Y')
            
            # Visualizza solo le colonne principali per compattezza
            compact_cols = ['Data', 'Orario', 'Dipartimento', 'Denominazione Insegnamento', 'Docente']
            
            # Tab per scegliere tra gestione singola o multipla
            record_tab1, record_tab2 = st.tabs(["Gestione singola", "Eliminazione multipla"])
            
            with record_tab1:
                # Aggiungi un indice per la selezione
                st.dataframe(display_df[compact_cols], use_container_width=True)
                
                # Input per selezionare un record da modificare
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    record_index = st.number_input("Indice del record da modificare:", 
                                                min_value=0, 
                                                max_value=len(admin_df)-1 if len(admin_df) > 0 else 0,
                                                value=0)
                    if st.button("Modifica record"):
                        st.session_state.edit_mode = True
                        st.session_state.edit_index = record_index
                        st.rerun()
                
                with col2:
                    if st.button("Aggiungi nuovo record"):
                        st.session_state.edit_mode = True
                        st.session_state.edit_index = -1  # -1 indica un nuovo record
                        st.rerun()
                
                with col3:
                    if st.button("Elimina record"):
                        if len(admin_df) > 0:
                            admin_df = delete_record(admin_df, record_index)
                            # Salva i dati aggiornati
                            save_dataframe_to_csv(admin_df)
                            st.success("Record eliminato con successo!")
                            # Ricarica automaticamente la pagina
                            st.rerun()
            
            with record_tab2:
                st.write("Seleziona i record da eliminare:")
                
                # Aggiungiamo una colonna di checkbox per la selezione
                selection_df = display_df.copy()
                
                # Inizializza stato selezione se non esiste
                if 'selections' not in st.session_state:
                    st.session_state.selections = [False] * len(selection_df)
                
                # Assicurati che la lunghezza corrisponda
                if len(st.session_state.selections) != len(selection_df):
                    st.session_state.selections = [False] * len(selection_df)
                    
                # Crea una tabella interattiva con checkbox per ogni riga
                for i, (idx, data_row) in enumerate(selection_df[compact_cols].iterrows()):
                    col1, col2 = st.columns([1, 20])
                    with col1:
                        st.session_state.selections[i] = st.checkbox(f"", key=f"sel_{i}", value=st.session_state.selections[i])
                    with col2:
                        # Formatta e mostra le informazioni della riga usando l'accesso diretto alle colonne
                        # che è più sicuro rispetto all'uso degli attributi di itertuples
                        row_data = f"**{data_row['Data']}** | {data_row['Orario']} | {data_row['Docente']} | {data_row['Denominazione Insegnamento']}"
                        st.markdown(row_data)
                        
                    # Aggiungi una linea sottile di separazione
                    st.markdown("---")
                
                # Pulsanti per selezionare/deselezionare tutti
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Seleziona tutti"):
                        st.session_state.selections = [True] * len(selection_df)
                        st.rerun()
                with col2:
                    if st.button("Deseleziona tutti"):
                        st.session_state.selections = [False] * len(selection_df)
                        st.rerun()
                with col3:
                    # Ottieni gli indici dei record selezionati
                    selected_indices = [i for i, is_selected in enumerate(st.session_state.selections) if is_selected]
                    
                    if st.button(f"Elimina selezionati ({len(selected_indices)})"):
                        if selected_indices:
                            # Elimina i record selezionati
                            admin_df = admin_df.drop(selected_indices)
                            # Resetta le selezioni
                            st.session_state.selections = [False] * (len(admin_df))
                            # Salva i dati aggiornati
                            save_dataframe_to_csv(admin_df)
                            st.success(f"Eliminati {len(selected_indices)} record con successo!")
                            st.info("Ricarica la pagina per vedere i dati aggiornati")
                            # Aggiungi pulsante per ricaricare
                            if st.button("🔄 Ricarica"):
                                st.rerun()
        
        else:
            # Modalità di modifica
            if st.session_state.edit_index == -1:
                # Aggiunta di un nuovo record
                updated_df = create_new_record(admin_df)
                
                if st.button("Torna alla lista"):
                    st.session_state.edit_mode = False
                    st.rerun()
                
                admin_df = updated_df
                # Salva i dati aggiornati
                save_dataframe_to_csv(admin_df)
            else:
                # Modifica di un record esistente
                updated_df = edit_record(admin_df, st.session_state.edit_index)
                
                if st.button("Torna alla lista"):
                    st.session_state.edit_mode = False
                    st.rerun()
                
                admin_df = updated_df
                # Salva i dati aggiornati
                save_dataframe_to_csv(admin_df)
    
    with admin_tab3:
        st.subheader("File di esempio")
        st.write("Scarica un file Excel di esempio per l'importazione dei dati.")
        
        if st.button("Genera file di esempio"):
            example_file = create_sample_excel()
            st.success(f"File di esempio creato: {example_file}")
            
            # Crea un link per il download
            with open(example_file, "rb") as file:
                btn = st.download_button(
                    label="Scarica file di esempio",
                    data=file,
                    file_name="esempio_caricamento.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    with admin_tab4:
        # Usa la nuova funzione migliorata per le statistiche
        mostra_statistiche_docenti(df)
        
        if df is None:
            st.info("Nessuna statistica disponibile sui docenti")

else:
    st.error("Errore nel caricamento dei dati. Controlla che il file CSV sia presente e formattato correttamente.")

# Aggiungi solo il pulsante logout nella sidebar
st.sidebar.markdown("---")
if is_admin_logged_in():
    if st.sidebar.button("📤 Logout"):
        # Esegui il logout
        st.session_state.admin_logged_in = False
        st.rerun()
