"""
Gestione dei record del calendario lezioni.
Permette di aggiungere, modificare ed eliminare i record.
"""

import streamlit as st
import pandas as pd
from file_utils import load_data, admin_interface
from admin_utils import is_admin_logged_in, upload_excel_file

def show_admin_management():
    """Mostra la pagina di gestione dei record"""
    
    st.set_page_config(
        page_title="Gestione Record - Calendario Lezioni",
        page_icon="🛠️",
        layout="wide"
    )
    
    st.title("🛠️ Gestione Record Calendario")
    
    # Importo le funzioni necessarie
    from admin_utils import login_admin, logout_admin
    
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
                    st.experimental_rerun()
                else:
                    st.error("❌ Password errata")
        
        # Interrompi l'esecuzione se l'utente non è loggato
        st.info("Questa sezione è riservata agli amministratori.")
        return
    else:
        # Logout button
        if st.sidebar.button("🚪 Logout"):
            logout_admin()
            st.experimental_rerun()
    
    # Carica i dati
    df = load_data()
    
    if df is None:
        st.error("Non è stato possibile caricare i dati.")
        return
    
    # Tabs per diverse funzionalità
    tab1, tab2 = st.tabs(["Gestione Record", "Importa Excel"])
    
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
                    st.experimental_rerun()
                else:
                    st.error("Si è verificato un errore durante l'importazione.")
        
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
        st.switch_page("pages/1_📊_Dashboard.py")

if __name__ == "__main__":
    show_admin_management()
