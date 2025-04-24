import pandas as pd
import streamlit as st
import traceback


def edit_record(df: pd.DataFrame, index: int) -> pd.DataFrame:
    """Modifica un record esistente nel DataFrame."""

    # ----- controlli preliminari -----
    if index < 0 or index >= len(df):
        st.error(
            f"Errore: indice record non valido (" f"{index}). Deve essere tra 0 e {len(df) - 1}."
        )
        return df

    record = df.iloc[index]

    st.subheader("Modifica Record")
    st.info("Modifica i campi e poi clicca su 'Invia modifiche'")
    status_container = st.empty()  # per messaggi di stato

    # data corrente del record (gestisce anche NaN / NaT)
    default_date = (
        pd.to_datetime(record["Data"]) if pd.notna(record["Data"]) else pd.Timestamp.today()
    )

    # --------- FORM ------------
    with st.form(key=f"edit_record_form_{index}"):
        col1, col2 = st.columns(2)

        with col1:
            data_input = st.date_input(
                "Data",
                value=default_date,
                format="YYYY-MM-DD",
                key=f"date_{index}",
            )
            orario_input = st.text_input(
                "Orario (es. 14:30-16:45)", value=record.get("Orario", ""), key=f"orario_{index}"
            )
            dipartimento_input = st.text_input(
                "Dipartimento", value=record.get("Dipartimento", ""), key=f"dipartimento_{index}"
            )
            insegnamento_comune_input = st.text_input(
                "Insegnamento comune", value=record.get("Insegnamento comune", ""), key=f"insegnamento_comune_{index}"
            )
            # Opzioni per i campi PeF: valori ammissibili sono solo "D", "P" o "---"
            pef_options = ["---", "D", "P"]
            
            # Funzione di utilità per determinare l'indice corretto del valore nel selectbox
            def get_pef_index(value):
                return pef_options.index(value) if value in pef_options else 0
            
            pef60_input = st.selectbox(
                "PeF60 all.1", 
                options=pef_options,
                index=get_pef_index(record.get("PeF60 all.1", "")),
                key=f"pef60_{index}"
            )
            
            pef30_all2_input = st.selectbox(
                "PeF30 all.2", 
                options=pef_options,
                index=get_pef_index(record.get("PeF30 all.2", "")),
                key=f"pef30_all2_{index}"
            )
            
            pef36_input = st.selectbox(
                "PeF36 all.5", 
                options=pef_options,
                index=get_pef_index(record.get("PeF36 all.5", "")),
                key=f"pef36_{index}"
            )

        with col2:
            pef30_art13_input = st.selectbox(
                "PeF30 art.13", 
                options=pef_options,
                index=get_pef_index(record.get("PeF30 art.13", "")),
                key=f"pef30_art13_{index}"
            )
            denominazione_input = st.text_input(
                "Denominazione Insegnamento", value=record.get("Denominazione Insegnamento", ""), key=f"denominazione_{index}"
            )
            docente_input = st.text_input(
                "Docente", value=record.get("Docente", ""), key=f"docente_{index}"
            )
            aula_input = st.text_input("Aula", value=record.get("Aula", ""), key=f"aula_{index}")
            link_input = st.text_input("Link Teams", value=record.get("Link Teams", ""), key=f"link_{index}")
            cfu_input = st.text_input("CFU", value=str(record.get("CFU", "")), key=f"cfu_{index}")
            note_input = st.text_area("Note", value=record.get("Note", ""), key=f"note_{index}")

        submitted = st.form_submit_button("Invia modifiche", type="primary")

    # --------- salvataggio ---------
    if submitted:
        try:
            new_record = {
                "Data": data_input,
                "Orario": orario_input,
                "Dipartimento": dipartimento_input,
                "Insegnamento comune": insegnamento_comune_input,
                "PeF60 all.1": pef60_input,
                "PeF30 all.2": pef30_all2_input,
                "PeF36 all.5": pef36_input,
                "PeF30 art.13": pef30_art13_input,
                "Denominazione Insegnamento": denominazione_input,
                "Docente": docente_input,
                "Aula": aula_input,
                "Link Teams": link_input,
                "CFU": float(cfu_input) if cfu_input.strip() else None,
                "Note": note_input,
            }

            # componenti data
            if pd.notna(data_input):
                new_record["Giorno"] = data_input.strftime("%A").capitalize()
                new_record["Mese"] = data_input.strftime("%B").capitalize()
                new_record["Anno"] = str(data_input.year)
            else:
                new_record["Giorno"] = new_record["Mese"] = new_record["Anno"] = None

            # aggiorna DataFrame
            for col, val in new_record.items():
                if col in df.columns:
                    df.at[index, col] = val

            # --------- sqlite (facoltativo) ---------
            try:
                from db_utils import update_record

                if update_record(df.iloc[index].to_dict()):
                    status_container.success("✅ Record aggiornato con successo nel database SQLite!")
                else:
                    status_container.warning(
                        "⚠️ Aggiornamento SQLite non riuscito, ma i dati sono stati salvati in memoria."
                    )
            except ImportError:
                status_container.info(
                    "Modulo db_utils non disponibile, i dati sono stati salvati solo in memoria."
                )
            except Exception as db_err:
                status_container.error(f"Errore nell'aggiornamento SQLite: {db_err}")

            # --------- salvataggio su file (retro‑compatibilità) ---------
            try:
                from data_operations import save_data

                save_data(df, replace_file=True)
            except Exception as save_err:
                status_container.warning(
                    f"Record aggiornato in memoria, ma problemi nel salvataggio su file: {save_err}"
                )

            # chiudi form
            st.session_state.pop("edit_idx", None)
            
            # Mostra un messaggio di successo prima del ricaricamento
            st.success("✅ Record aggiornato con successo! La pagina verrà ricaricata per mostrare le modifiche...")
            
            # Attendi brevemente per consentire la visualizzazione del messaggio
            import time
            time.sleep(1)
            
            # Ricarica la pagina per aggiornare la visualizzazione dei dati
            st.rerun()

        except Exception as e:
            status_container.error(f"Si è verificato un errore durante il salvataggio: {e}")
            st.error(traceback.format_exc())

    return df
