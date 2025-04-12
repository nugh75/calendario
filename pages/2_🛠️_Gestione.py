"""
Gestione dei record del calendario lezioni.
Permette di aggiungere, modificare ed eliminare i record.
"""

import streamlit as st
import pandas as pd
from file_utils import load_data, admin_interface, create_sample_excel
from admin_utils import is_admin_logged_in

def show_admin_management():
    """Mostra la pagina di gestione dei record"""
    
    st.set_page_config(
        page_title="Gestione Record - Calendario Lezioni",
        page_icon="🛠️",
        layout="wide"
    )
    
    st.title("🛠️ Gestione Record Calendario")
    
    # Importo le funzioni necessarie
    from admin_utils import login_admin, logout_admin, upload_excel_file
    
    # Contenuto protetto
    if not is_admin_logged_in():
        st.warning("🔒 Questa pagina è protetta da password")
        
        # Form di login
        with st.form("login_form_gestione"):
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Accedi")
            
            if submit_button:
                if login_admin(password):
                    st.success("✅ Accesso effettuato con successo!")
                    st.rerun()
                else:
                    st.error("❌ Password errata")
        
        # Interrompi l'esecuzione se l'utente non è loggato
        st.info("Questa sezione è riservata agli amministratori.")
        return
    else:
        # Logout button
        if st.sidebar.button("🚪 Logout"):
            logout_admin()
            st.rerun()
    
    # Carica i dati
    df = load_data()
    
    if df is None:
        st.error("Non è stato possibile caricare i dati.")
        return
    
    # Tabs per diverse funzionalità
    tab1, tab2, tab3 = st.tabs(["Gestione Record", "Importa Excel", "Gestione Link Teams"])
    
    # Tab per gestione record
    with tab1:
        # Utilizza l'interfaccia di amministrazione
        updated_df = admin_interface(df)
    
    # Tab per importazione Excel
    with tab2:
        st.subheader("Importazione da Excel")
        st.write("Carica un file Excel contenente nuovi record da aggiungere al calendario.")
        
        uploaded_file = st.file_uploader("Scegli un file Excel", type=["xlsx", "xls"])
        
        if uploaded_file is not None:
            if st.button("Importa Dati"):
                result = upload_excel_file(uploaded_file)
                if result:
                    st.success("Dati importati con successo!")
                    st.rerun()
                else:
                    st.error("Si è verificato un errore durante l'importazione.")
    
    # Tab per gestione link Teams
    with tab3:
        # Importa le funzioni per gestire i link Teams
        from teams_utils import (
            load_teams_links, save_teams_links, 
            add_teams_link, delete_teams_link
        )
        
        st.subheader("🔗 Gestione Link Microsoft Teams")
        st.write("Qui puoi associare i link Microsoft Teams agli insegnamenti comuni.")
        
        # Carica i link Teams esistenti
        teams_links = load_teams_links()
        
        # Visualizza i link Teams esistenti
        if teams_links:
            st.markdown("### Link Teams esistenti")
            
            # Converte il dizionario in dataframe per una visualizzazione migliore
            links_df = pd.DataFrame(list(teams_links.items()), columns=["Insegnamento comune", "Link Teams"])
            st.dataframe(links_df)
        else:
            st.info("Nessun link Teams configurato. Utilizza il form sotto per aggiungerne uno.")
        
        # Form per aggiungere/modificare un link Teams
        st.markdown("### Aggiungi o modifica un link Teams")
        
        # Estrai tutti gli insegnamenti comuni dal DataFrame principale
        insegnamenti = sorted(df['Insegnamento comune'].dropna().unique())
        
        with st.form("add_teams_link_form"):
            # Seleziona un insegnamento esistente o inserisci uno nuovo
            insegnamento_option = st.radio(
                "Seleziona metodo:",
                ["Seleziona da elenco", "Inserisci manualmente"]
            )
            
            if insegnamento_option == "Seleziona da elenco":
                insegnamento = st.selectbox(
                    "Seleziona un insegnamento comune:",
                    options=insegnamenti,
                    index=0 if insegnamenti else None
                )
            else:
                insegnamento = st.text_input("Inserisci nome insegnamento comune:")
            
            # Campo per il link Teams
            link_teams = st.text_input(
                "Link Microsoft Teams:",
                value=teams_links.get(insegnamento, "") if insegnamento else ""
            )
            
            # Pulsante per salvare
            submit_button = st.form_submit_button("Salva link Teams")
            
            if submit_button:
                if not insegnamento:
                    st.error("Inserisci un nome per l'insegnamento comune.")
                elif not link_teams:
                    st.error("Inserisci un link Microsoft Teams valido.")
                else:
                    # Salva il link
                    success = add_teams_link(insegnamento, link_teams)
                    if success:
                        st.success(f"✅ Link Teams per '{insegnamento}' salvato con successo!")
                        st.rerun()  # Ricarica la pagina per mostrare i cambiamenti
                    else:
                        st.error("❌ Si è verificato un errore durante il salvataggio del link.")
        
        # Form per eliminare un link Teams
        st.markdown("### Elimina un link Teams")
        
        # Ottieni gli insegnamenti che hanno un link Teams
        insegnamenti_con_link = list(teams_links.keys())
        
        if not insegnamenti_con_link:
            st.info("Non ci sono link Teams da eliminare.")
        else:
            with st.form("delete_teams_link_form"):
                insegnamento_da_eliminare = st.selectbox(
                    "Seleziona un insegnamento comune:",
                    options=insegnamenti_con_link
                )
                
                # Pulsante per eliminare
                delete_button = st.form_submit_button("❌ Elimina link Teams")
                
                if delete_button:
                    # Elimina il link
                    success = delete_teams_link(insegnamento_da_eliminare)
                    if success:
                        st.success(f"✅ Link Teams per '{insegnamento_da_eliminare}' eliminato con successo!")
                        st.rerun()  # Ricarica la pagina per mostrare i cambiamenti
                    else:
                        st.error("❌ Si è verificato un errore durante l'eliminazione del link.")
        
        # Download template Excel
        st.write("---")
        st.subheader("Template Excel")
        st.write("Scarica un file Excel di esempio da utilizzare come template.")
        
        if st.button("Scarica Template Excel"):
            template_path = create_sample_excel()
            with open(template_path, "rb") as file:
                st.download_button(
                    label="📥 Download Template",
                    data=file,
                    file_name="template_calendario.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    # Pulsante per tornare alla dashboard
    if st.button("↩️ Torna alla Dashboard"):
        st.switch_page("📅_Calendario.py")

if __name__ == "__main__":
    show_admin_management()
