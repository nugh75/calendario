import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime
import os
from admin_utils import (
    login_admin, logout_admin, is_admin_logged_in, upload_excel_file,
    save_dataframe_to_csv, edit_record, create_new_record, delete_record,
    create_sample_excel
)

# Configurazione pagina Streamlit
st.set_page_config(
    page_title="Calendario Lezioni PeF 2024-25",
    page_icon="📚",
    layout="wide"
)

# Titolo dell'applicazione
st.title("Calendario Lezioni Percorsi di Formazione 2024-25")
st.markdown("### Visualizzazione interattiva del calendario lezioni")

# Funzione per caricare i dati
def load_data():
    # Imposta la localizzazione italiana per le date
    import locale
    try:
        locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'it_IT')
        except:
            pass

    # Usa direttamente il file dati.csv
    file_path = os.path.join('dati', 'dati.csv')
    
    # Controlla se il file esiste
    if not os.path.exists(file_path):
        # Se dati.csv non esiste, cerca un altro file CSV come fallback
        csv_files = [f for f in os.listdir('dati') if f.endswith('.csv')]
        if not csv_files:
            st.error("Nessun file CSV trovato nella cartella 'dati'")
            return None
        # Usa il file più recente come fallback
        file_path = os.path.join('dati', sorted(csv_files)[-1])
    
    try:
        # Carica il CSV
        df = pd.read_csv(file_path, delimiter=';', encoding='utf-8', skiprows=3)
        
        # Rinomina le colonne per chiarezza
        df.columns = [
            'Data', 'Orario', 'Dipartimento', 'Classe di concorso',
            'Insegnamento comune', 'PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13',
            'Codice insegnamento', 'Denominazione Insegnamento', 'Docente',
            'Aula', 'Link Teams', 'CFU', 'Note', 'Giorno', 'Mese', 'Anno'
        ]
        
        # Pulizia dei dati
        # Filtra le righe che hanno almeno l'orario compilato e non vuoto
        df = df[df['Orario'].notna() & (df['Orario'] != '')]
        
        # Gestione delle date
        def parse_date(date_str):
            if pd.isna(date_str):
                return None
            try:
                # Prima prova il formato italiano
                return pd.to_datetime(date_str, format='%A %d %B %Y')
            except:
                try:
                    # Poi prova il formato ISO
                    date = pd.to_datetime(date_str)
                    return date
                except:
                    return None

        # Converti le date e gestisci gli errori
        df['Data'] = df['Data'].apply(parse_date)
        
        # Rimuovi le righe con date non valide
        df = df.dropna(subset=['Data'])
        
        # Estrai giorno della settimana in italiano
        df['Giorno'] = df['Data'].dt.strftime('%A')
        
        # Crea una colonna per mese e anno per facilitare il filtraggio
        df['Mese'] = df['Data'].dt.strftime('%B')
        df['Anno'] = df['Data'].dt.year
        
        return df
        
    except Exception as e:
        st.error(f"Errore durante il caricamento dei dati: {e}")
        return None
    
    return df

# Caricamento dati
df = load_data()

# Aggiungi un pulsante per ricaricare esplicitamente i dati
if st.button("🔄 Ricarica dati"):
    st.experimental_memo.clear()
    st.rerun()

if df is not None:
    # Sidebar per filtri
    st.sidebar.header("Filtri")
    
    # Mappa dei nomi dei mesi per l'ordinamento corretto
    mappa_mesi = {
        'January': 1, 'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
        'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
        'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
        'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
    }
    
    # Filtro per mese - usa la mappa per l'ordinamento invece di strptime
    def ordina_mesi(mese):
        if isinstance(mese, str) and mese in mappa_mesi:
            return mappa_mesi[mese]
        return 0
        
    mesi = sorted(df['Mese'].unique(), key=ordina_mesi)
    mese_selezionato = st.sidebar.multiselect(
        "Seleziona Mese:", 
        options=mesi,
        default=mesi
    )
    
    # Filtro per dipartimento
    dipartimenti = sorted([d for d in df['Dipartimento'].unique() if pd.notna(d) and d != ''])
    dipartimento_selezionato = st.sidebar.multiselect(
        "Seleziona Dipartimento:",
        options=dipartimenti,
        default=dipartimenti
    )
    
    # Filtro per classe di concorso
    classi_concorso = sorted([c for c in df['Classe di concorso'].unique() if pd.notna(c) and c != ''])
    classe_concorso_selezionata = st.sidebar.multiselect(
        "Seleziona Classe di Concorso:",
        options=classi_concorso,
        default=classi_concorso
    )
    
    # Filtro per docente
    docenti = sorted([d for d in df['Docente'].unique() if pd.notna(d) and d != ''])
    docente_selezionato = st.sidebar.multiselect(
        "Seleziona Docente:",
        options=docenti,
        default=[]  # Nessun docente selezionato di default
    )
    
    # Filtro per denominazione insegnamento
    insegnamenti = sorted([i for i in df['Denominazione Insegnamento'].unique() if pd.notna(i) and i != ''])
    insegnamento_selezionato = st.sidebar.multiselect(
        "Seleziona Insegnamento:",
        options=insegnamenti,
        default=[]  # Nessun insegnamento selezionato di default
    )
    
    # Filtro per percorso formativo
    percorsi = ['PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13']
    percorso_selezionato = st.sidebar.selectbox(
        "Seleziona Percorso Formativo (opzionale):",
        options=['Tutti i percorsi'] + percorsi,
        index=0  # Default: tutti i percorsi
    )
    
    # Filtro per modalità di erogazione
    modalita = ['P', 'D', '---']
    modalita_selezionata = st.sidebar.multiselect(
        "Modalità di erogazione (P=Presenza, D=Distanza):",
        options=modalita,
        default=modalita[:2]  # P e D selezionate di default
    )
    
    # Applica filtri
    filtered_df = df.copy()
    
    if mese_selezionato:
        filtered_df = filtered_df[filtered_df['Mese'].isin(mese_selezionato)]
    
    if dipartimento_selezionato:
        filtered_df = filtered_df[filtered_df['Dipartimento'].isin(dipartimento_selezionato)]
    
    if classe_concorso_selezionata:
        filtered_df = filtered_df[filtered_df['Classe di concorso'].isin(classe_concorso_selezionata)]
    
    if docente_selezionato:
        filtered_df = filtered_df[filtered_df['Docente'].isin(docente_selezionato)]
    
    if insegnamento_selezionato:
        filtered_df = filtered_df[filtered_df['Denominazione Insegnamento'].isin(insegnamento_selezionato)]
    
    # Filtra per percorso formativo specifico
    if percorso_selezionato != 'Tutti i percorsi':
        # Se è stato selezionato un percorso specifico, filtra solo le lezioni con modalità P o D per quel percorso
        if modalita_selezionata:
            filtered_df = filtered_df[filtered_df[percorso_selezionato].isin(modalita_selezionata)]
    else:
        # Se non è stato selezionato un percorso specifico, applica il filtro di modalità su tutti i percorsi
        if modalita_selezionata:
            mask = filtered_df['PeF60 all.1'].isin(modalita_selezionata)
            mask |= filtered_df['PeF30 all.2'].isin(modalita_selezionata)
            mask |= filtered_df['PeF36 all.5'].isin(modalita_selezionata)
            mask |= filtered_df['PeF30 art.13'].isin(modalita_selezionata)
            filtered_df = filtered_df[mask]
    
    # Visualizzazione tabella filtrata
    st.subheader("Calendario Lezioni")
    
    if filtered_df.empty:
        st.warning("Nessuna lezione trovata con i filtri selezionati.")
    else:
        # Mostra il conteggio delle lezioni filtrate
        st.info(f"Trovate {len(filtered_df)} lezioni che corrispondono ai criteri selezionati.")
        
        # Determina quali colonne visualizzare in base al percorso selezionato
        base_cols = ['Data', 'Orario', 'Dipartimento', 'Classe di concorso',
                      'Codice insegnamento', 'Denominazione Insegnamento', 'Docente', 
                      'Aula', 'Link Teams', 'CFU']
                      
        # Se è selezionato un percorso specifico, mostra solo quella colonna
        if percorso_selezionato != 'Tutti i percorsi':
            display_cols = base_cols.copy()
            # Aggiungi solo la colonna del percorso selezionato
            display_cols.insert(4, percorso_selezionato)
        else:
            # Altrimenti mostra tutte le colonne dei percorsi
            display_cols = base_cols.copy()
            display_cols[4:4] = ['PeF60 all.1', 'PeF30 all.2', 'PeF36 all.5', 'PeF30 art.13']
        
        # Formatta la data in modo leggibile
        filtered_df_display = filtered_df.copy()
        filtered_df_display['Data'] = filtered_df_display['Data'].dt.strftime('%a %d %b %Y')
        
        # Visualizzazione della tabella
        st.dataframe(
            filtered_df_display[display_cols].sort_values('Data'),
            use_container_width=True,
            hide_index=True
        )
                
        # Statistiche
        st.subheader("Statistiche")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("Lezioni per Dipartimento")
            dipartimento_stats = filtered_df['Dipartimento'].value_counts().reset_index()
            dipartimento_stats.columns = ['Dipartimento', 'CFU']
            st.dataframe(dipartimento_stats, use_container_width=True, hide_index=True)
        
        with col2:
            st.write("Lezioni per Docente")
            docente_stats = filtered_df['Docente'].value_counts().head(10).reset_index()
            docente_stats.columns = ['Docente', 'CFU']
            st.dataframe(docente_stats, use_container_width=True, hide_index=True)
            
        # Statistiche per denominazione insegnamento
        st.write("Lezioni per Insegnamento")
        insegnamento_stats = filtered_df['Denominazione Insegnamento'].value_counts().reset_index()
        insegnamento_stats.columns = ['Insegnamento', 'CFU']
        st.dataframe(insegnamento_stats, use_container_width=True, hide_index=True)

else:
    st.error("Errore nel caricamento dei dati. Controlla che il file CSV sia presente e formattato correttamente.")

# Sezione amministrativa
st.markdown("---")
st.header("Sezione Amministratore")

# Inizializza lo stato della sessione se non esiste
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False

if 'admin_data' not in st.session_state:
    st.session_state.admin_data = None

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_index = None

# Gestione login/logout
if not is_admin_logged_in():
    login_admin()
else:
    # Mostra il pulsante di logout
    if st.button("Logout Amministratore"):
        logout_admin()
        st.rerun()
    
    st.success("Accesso effettuato come amministratore")
    
    # Tabs per separare le diverse funzionalità
    admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Importa dati", "Gestione record", "Scarica esempi"])
    
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
        st.write("Puoi modificare, aggiungere o eliminare singoli record del calendario.")
        
        # Carica i dati se non sono già in memoria
        if df is not None:
            admin_df = df.copy()
            
            # Mostra la tabella con i dati attuali
            if not st.session_state.edit_mode:
                st.write("Dati attuali:")
                
                # Crea una versione visualizzabile del dataframe con indice
                display_df = admin_df.copy()
                display_df['Data'] = display_df['Data'].dt.strftime('%a %d %b %Y')
                
                # Visualizza solo le colonne principali per compattezza
                compact_cols = ['Data', 'Orario', 'Dipartimento', 'Denominazione Insegnamento', 'Docente']
                
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
                            st.info("Ricarica la pagina per vedere i dati aggiornati")
            
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
