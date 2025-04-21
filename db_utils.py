"""
Modulo per la gestione del database SQLite nell'applicazione Calendario.
Questo modulo centralizza tutte le operazioni di lettura, scrittura e gestione dei dati in SQLite.
"""

import os
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime
import traceback
from typing import Dict, List, Tuple, Optional, Any, Union

# Importa le funzioni di validazione
try:
    from db_utils_validation import validate_record_schema, get_db_schema
except ImportError:
    # Definizione fallback delle funzioni di validazione
    def validate_record_schema(record: dict) -> tuple:
        """Fallback per la funzione di validazione record"""
        return True, ""
    
    def get_db_schema() -> dict:
        """Fallback per la funzione di recupero schema"""
        return {}

# Importa il logger
try:
    from log_utils import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Costanti per il database
DB_FOLDER = 'dati'
DB_FILE = 'calendario.db'
DB_PATH = os.path.join(DB_FOLDER, DB_FILE)

def get_connection():
    """
    Ottiene una connessione al database SQLite.
    
    Returns:
        sqlite3.Connection: Oggetto connessione al database
    """
    os.makedirs(DB_FOLDER, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    """
    Inizializza il database e crea le tabelle se non esistono.
    
    Returns:
        bool: True se l'inizializzazione è riuscita, False altrimenti
    """
    try:
        # Assicurati che la cartella esista
        os.makedirs(DB_FOLDER, exist_ok=True)
        
        # Connetti al database
        conn = get_connection()
        cursor = conn.cursor()
        
        # Creazione tabella dipartimenti
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dipartimenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        )
        ''')
        
        # Creazione tabella docenti
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS docenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            email TEXT,
            dipartimento_id INTEGER,
            FOREIGN KEY (dipartimento_id) REFERENCES dipartimenti(id)
        )
        ''')
        
        # Creazione tabella lezioni
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lezioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            orario TEXT NOT NULL,
            dipartimento_id INTEGER,
            classe_concorso TEXT,
            insegnamento_comune TEXT,
            pef60 TEXT,
            pef30_all2 TEXT,
            pef36_all5 TEXT,
            pef30_art13 TEXT,
            codice_insegnamento TEXT,
            denominazione_insegnamento TEXT NOT NULL,
            docente_id INTEGER NOT NULL,
            aula TEXT,
            link_teams TEXT,
            cfu REAL,
            note TEXT,
            giorno TEXT,
            mese TEXT,
            anno TEXT,
            FOREIGN KEY (dipartimento_id) REFERENCES dipartimenti(id),
            FOREIGN KEY (docente_id) REFERENCES docenti(id)
        )
        ''')
        
        # Creazione tabella teams_links
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            insegnamento TEXT UNIQUE NOT NULL,
            link TEXT NOT NULL
        )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Database inizializzato con successo")
        return True
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        logger.error(f"Errore nell'inizializzazione del database: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def load_data() -> pd.DataFrame:
    """
    Carica tutti i dati dal database in un DataFrame pandas.
    
    Returns:
        pd.DataFrame: DataFrame contenente tutti i dati delle lezioni
    """
    try:
        # Verifica se il database esiste, altrimenti inizializzalo
        if not os.path.exists(DB_PATH):
            init_db()
            # Migra i dati dal JSON se il database è vuoto
            if migrate_from_json():
                logger.info("Dati migrati con successo dal file JSON al database SQLite")
            else:
                logger.warning("Nessun dato migrato dal JSON. Il database potrebbe essere vuoto.")
        
        # Connetti al database
        conn = get_connection()
        
        # Query con JOIN per ottenere tutti i dati necessari
        query = '''
        SELECT 
            l.id, l.data, l.orario as "Orario", d.nome as "Dipartimento", 
            l.classe_concorso as "Classe di concorso", 
            l.insegnamento_comune as "Insegnamento comune",
            l.pef60 as "PeF60 all.1", 
            l.pef30_all2 as "PeF30 all.2", 
            l.pef36_all5 as "PeF36 all.5", 
            l.pef30_art13 as "PeF30 art.13", 
            l.codice_insegnamento as "Codice insegnamento", 
            l.denominazione_insegnamento as "Denominazione Insegnamento", 
            doc.nome as "Docente", 
            l.aula as "Aula", 
            l.link_teams as "Link Teams", 
            l.cfu as "CFU", 
            l.note as "Note", 
            l.giorno as "Giorno", 
            l.mese as "Mese", 
            l.anno as "Anno"
        FROM lezioni l
        LEFT JOIN dipartimenti d ON l.dipartimento_id = d.id
        LEFT JOIN docenti doc ON l.docente_id = doc.id
        ORDER BY l.data, l.orario
        '''
        
        df = pd.read_sql_query(query, conn)
        
        # Converte le date dal formato stringa a datetime
        df['Data'] = pd.to_datetime(df['data'], errors='coerce')
        
        # Rimuovi la colonna data originale e id
        if 'data' in df.columns:
            df = df.drop('data', axis=1)
        if 'id' in df.columns:
            df = df.drop('id', axis=1)
            
        # Assicurati che tutti i campi abbiano il tipo dati corretto
        df['CFU'] = pd.to_numeric(df['CFU'], errors='coerce').fillna(0.0)
        
        # Riempie i valori NaN con stringhe vuote per le colonne di testo
        text_columns = df.select_dtypes(include=['object']).columns
        df[text_columns] = df[text_columns].fillna('')
        
        conn.close()
        
        logger.info(f"Caricati {len(df)} record dal database")
        return df
        
    except Exception as e:
        logger.error(f"Errore nel caricamento dei dati dal database: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Fallback al vecchio metodo JSON in caso di errore
        logger.warning("Tentativo di fallback al caricamento dati da JSON")
        try:
            from file_utils import load_data as load_data_json
            return load_data_json()
        except:
            logger.error("Fallback fallito. Impossibile caricare i dati.")
            return pd.DataFrame()

def get_or_create_dipartimento(dipartimento: str) -> int:
    """
    Ottiene l'ID di un dipartimento o lo crea se non esiste.
    
    Args:
        dipartimento: Nome del dipartimento
        
    Returns:
        int: ID del dipartimento nel database
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Controlla se esiste
        cursor.execute('SELECT id FROM dipartimenti WHERE nome = ?', (dipartimento,))
        result = cursor.fetchone()
        
        if result:
            dipartimento_id = result[0]
        else:
            # Non esiste, crealo
            cursor.execute('INSERT INTO dipartimenti (nome) VALUES (?)', (dipartimento,))
            conn.commit()
            dipartimento_id = cursor.lastrowid
        
        conn.close()
        return dipartimento_id
        
    except Exception as e:
        logger.error(f"Errore nel recupero/creazione del dipartimento '{dipartimento}': {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return -1

def get_or_create_docente(docente: str, dipartimento_id: int = None) -> int:
    """
    Ottiene l'ID di un docente o lo crea se non esiste.
    
    Args:
        docente: Nome del docente
        dipartimento_id: ID del dipartimento associato (opzionale)
        
    Returns:
        int: ID del docente nel database
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Controlla se esiste
        cursor.execute('SELECT id FROM docenti WHERE nome = ?', (docente,))
        result = cursor.fetchone()
        
        if result:
            docente_id = result[0]
            # Aggiorna il dipartimento se fornito e diverso
            if dipartimento_id is not None:
                cursor.execute('UPDATE docenti SET dipartimento_id = ? WHERE id = ?', 
                               (dipartimento_id, docente_id))
                conn.commit()
        else:
            # Non esiste, crealo
            cursor.execute('INSERT INTO docenti (nome, dipartimento_id) VALUES (?, ?)', 
                          (docente, dipartimento_id))
            conn.commit()
            docente_id = cursor.lastrowid
        
        conn.close()
        return docente_id
        
    except Exception as e:
        logger.error(f"Errore nel recupero/creazione del docente '{docente}': {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return -1

def save_record(record_data: Dict) -> bool:
    """
    Salva un record nel database o lo aggiorna se esiste già.
    
    Args:
        record_data: Dizionario con i dati del record
        
    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ottieni o crea il dipartimento
        dipartimento = record_data.get('Dipartimento', '')
        if dipartimento:
            dipartimento_id = get_or_create_dipartimento(dipartimento)
        else:
            dipartimento_id = None
        
        # Ottieni o crea il docente
        docente = record_data.get('Docente', '')
        if docente:
            docente_id = get_or_create_docente(docente, dipartimento_id)
        else:
            docente_id = None
            
        # Controlla se il record esiste già (per data, ora e docente)
        data_str = pd.to_datetime(record_data.get('Data')).strftime('%Y-%m-%d')
        orario = record_data.get('Orario', '')
        insegnamento_comune = record_data.get('Insegnamento comune', '')
        denominazione = record_data.get('Denominazione Insegnamento', '')
        
        cursor.execute('''
            SELECT id FROM lezioni 
            WHERE data = ? AND orario = ? AND docente_id = ? AND denominazione_insegnamento = ? AND insegnamento_comune = ?
        ''', (data_str, orario, docente_id, denominazione, insegnamento_comune))
        
        existing_id = cursor.fetchone()
        
        if existing_id:
            # Aggiorna record esistente
            record_id = existing_id[0]
            cursor.execute('''
                UPDATE lezioni SET
                dipartimento_id = ?,
                classe_concorso = ?,
                insegnamento_comune = ?,
                pef60 = ?,
                pef30_all2 = ?,
                pef36_all5 = ?,
                pef30_art13 = ?,
                codice_insegnamento = ?,
                denominazione_insegnamento = ?,
                aula = ?,
                link_teams = ?,
                cfu = ?,
                note = ?,
                giorno = ?,
                mese = ?,
                anno = ?
                WHERE id = ?
            ''', (
                dipartimento_id,
                record_data.get('Classe di concorso', ''),
                record_data.get('Insegnamento comune', ''),
                record_data.get('PeF60 all.1', ''),
                record_data.get('PeF30 all.2', ''),
                record_data.get('PeF36 all.5', ''),
                record_data.get('PeF30 art.13', ''),
                record_data.get('Codice insegnamento', ''),
                record_data.get('Denominazione Insegnamento', ''),
                record_data.get('Aula', ''),
                record_data.get('Link Teams', ''),
                record_data.get('CFU', 0),
                record_data.get('Note', ''),
                record_data.get('Giorno', ''),
                record_data.get('Mese', ''),
                record_data.get('Anno', ''),
                record_id
            ))
            logger.info(f"Record aggiornato con ID: {record_id}")
        else:
            # Inserisce nuovo record
            cursor.execute('''
                INSERT INTO lezioni (
                    data, orario, dipartimento_id, classe_concorso, insegnamento_comune,
                    pef60, pef30_all2, pef36_all5, pef30_art13, codice_insegnamento,
                    denominazione_insegnamento, docente_id, aula, link_teams, cfu,
                    note, giorno, mese, anno
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data_str, 
                orario,
                dipartimento_id,
                record_data.get('Classe di concorso', ''),
                record_data.get('Insegnamento comune', ''),
                record_data.get('PeF60 all.1', ''),
                record_data.get('PeF30 all.2', ''),
                record_data.get('PeF36 all.5', ''),
                record_data.get('PeF30 art.13', ''),
                record_data.get('Codice insegnamento', ''),
                record_data.get('Denominazione Insegnamento', ''),
                docente_id,
                record_data.get('Aula', ''),
                record_data.get('Link Teams', ''),
                record_data.get('CFU', 0),
                record_data.get('Note', ''),
                record_data.get('Giorno', ''),
                record_data.get('Mese', ''),
                record_data.get('Anno', '')
            ))
            logger.info(f"Nuovo record inserito con ID: {cursor.lastrowid}")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Errore nel salvataggio del record: {str(e)}")
        logger.error(traceback.format_exc())
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def update_record(record_data: dict) -> bool:
    """
    Aggiorna un record esistente nel database SQLite.
    
    Args:
        record_data: Dizionario contenente i dati del record da aggiornare
        
    Returns:
        bool: True se l'aggiornamento è riuscito, False altrimenti
    """
    try:
        # Valida i dati prima di procedere
        try:
            is_valid, message = validate_record_schema(record_data)
            if not is_valid:
                logger.error(f"Dati non validi per l'aggiornamento: {message}")
                return False
        except Exception as validation_err:
            logger.warning(f"Errore durante la validazione del record: {str(validation_err)}")
            # Continua comunque con l'aggiornamento
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ottieni o crea il dipartimento
        dipartimento = record_data.get('Dipartimento', '')
        if dipartimento:
            dipartimento_id = get_or_create_dipartimento(dipartimento)
        else:
            dipartimento_id = None
        
        # Ottieni o crea il docente
        docente = record_data.get('Docente', '')
        if docente:
            docente_id = get_or_create_docente(docente, dipartimento_id)
        else:
            docente_id = None
            
        # Prepara i dati della data
        if pd.isna(record_data.get('Data')):
            logger.error("Impossibile aggiornare un record senza data")
            return False
            
        data_str = pd.to_datetime(record_data.get('Data')).strftime('%Y-%m-%d')
        orario = record_data.get('Orario', '')
        insegnamento_comune = record_data.get('Insegnamento comune', '')
        denominazione = record_data.get('Denominazione Insegnamento', '')
        
        # Trova l'ID del record da aggiornare
        cursor.execute('''
            SELECT id FROM lezioni 
            WHERE data = ? AND orario = ? AND docente_id = ? AND denominazione_insegnamento = ?
        ''', (data_str, orario, docente_id, denominazione))
        
        existing_id = cursor.fetchone()
        
        if not existing_id:
            logger.warning(f"Nessun record trovato da aggiornare con: data={data_str}, orario={orario}, docente={docente}, insegnamento={denominazione}")
            conn.close()
            return False
            
        # Aggiorna il record esistente
        record_id = existing_id[0]
        cursor.execute('''
            UPDATE lezioni SET
            dipartimento_id = ?,
            classe_concorso = ?,
            insegnamento_comune = ?,
            pef60 = ?,
            pef30_all2 = ?,
            pef36_all5 = ?,
            pef30_art13 = ?,
            codice_insegnamento = ?,
            denominazione_insegnamento = ?,
            aula = ?,
            link_teams = ?,
            cfu = ?,
            note = ?,
            giorno = ?,
            mese = ?,
            anno = ?
            WHERE id = ?
        ''', (
            dipartimento_id,
            record_data.get('Classe di concorso', ''),
            record_data.get('Insegnamento comune', ''),
            record_data.get('PeF60 all.1', ''),
            record_data.get('PeF30 all.2', ''),
            record_data.get('PeF36 all.5', ''),
            record_data.get('PeF30 art.13', ''),
            record_data.get('Codice insegnamento', ''),
            record_data.get('Denominazione Insegnamento', ''),
            record_data.get('Aula', ''),
            record_data.get('Link Teams', ''),
            record_data.get('CFU', 0),
            record_data.get('Note', ''),
            record_data.get('Giorno', ''),
            record_data.get('Mese', ''),
            record_data.get('Anno', ''),
            record_id
        ))
        
        rows_updated = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_updated > 0:
            logger.info(f"Record aggiornato con successo: ID={record_id}")
            return True
        else:
            logger.warning(f"Nessuna modifica effettiva apportata al record: ID={record_id}")
            return False
        
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento del record: {str(e)}")
        logger.error(traceback.format_exc())
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def delete_record(criteria: Dict) -> bool:
    """
    Elimina un record dal database in base ai criteri specificati.
    
    Args:
        criteria: Dizionario con i criteri per identificare il record (es. Data, Orario, Docente)
        
    Returns:
        bool: True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Preparazione della query di eliminazione
        conditions = []
        params = []
        
        # Gestione della data
        if 'Data' in criteria and criteria['Data']:
            data_str = pd.to_datetime(criteria['Data']).strftime('%Y-%m-%d')
            conditions.append("data = ?")
            params.append(data_str)
            
        # Gestione dell'orario
        if 'Orario' in criteria and criteria['Orario']:
            conditions.append("orario = ?")
            params.append(criteria['Orario'])
            
        # Gestione del docente
        if 'Docente' in criteria and criteria['Docente']:
            cursor.execute("SELECT id FROM docenti WHERE nome = ?", (criteria['Docente'],))
            result = cursor.fetchone()
            if result:
                conditions.append("docente_id = ?")
                params.append(result[0])
            else:
                logger.warning(f"Docente '{criteria['Docente']}' non trovato nel database")
                return False
                
        # Gestione dell'ID diretto
        if 'id' in criteria and criteria['id']:
            conditions.append("id = ?")
            params.append(criteria['id'])
            
        # Verifica se ci sono condizioni
        if not conditions:
            logger.warning("Nessun criterio fornito per eliminare un record")
            conn.close()
            return False
            
        # Costruisci la query
        query = f"DELETE FROM lezioni WHERE {' AND '.join(conditions)}"
        
        # Esegui la query
        cursor.execute(query, params)
        
        # Verifica se sono state eliminate righe
        rows_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_deleted > 0:
            logger.info(f"Eliminati {rows_deleted} record dal database")
            return True
        else:
            logger.warning("Nessun record trovato da eliminare")
            return False
            
    except Exception as e:
        logger.error(f"Errore nell'eliminazione del record: {str(e)}")
        logger.error(traceback.format_exc())
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def migrate_from_json() -> bool:
    """
    Migra i dati dal file JSON al database SQLite.
    
    Returns:
        bool: True se la migrazione è riuscita, False altrimenti
    """
    try:
        # Importa la funzione di caricamento JSON
        from file_utils import load_data as load_json_data
        
        # Carica i dati dal JSON
        df = load_json_data()
        
        if df is None or len(df) == 0:
            logger.warning("Nessun dato da migrare o file JSON non trovato")
            return False
            
        logger.info(f"Iniziata migrazione di {len(df)} record da JSON a SQLite")
        
        # Inizializza il contatore di successo
        success_count = 0
        
        # Per ogni record nel DataFrame
        for _, row in df.iterrows():
            # Converti la riga in dizionario
            record_data = row.to_dict()
            
            # Salva nel database
            if save_record(record_data):
                success_count += 1
        
        logger.info(f"Migrazione completata: {success_count}/{len(df)} record migrati con successo")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Errore durante la migrazione dei dati: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def save_teams_link(insegnamento: str, link: str) -> bool:
    """
    Salva un link Teams nel database.
    
    Args:
        insegnamento: Nome dell'insegnamento
        link: Link alla riunione Teams
        
    Returns:
        bool: True se l'operazione è riuscita, False altrimenti
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Controlla se esiste già
        cursor.execute('SELECT id FROM teams_links WHERE insegnamento = ?', (insegnamento,))
        result = cursor.fetchone()
        
        if result:
            # Aggiorna
            cursor.execute('UPDATE teams_links SET link = ? WHERE id = ?', (link, result[0]))
        else:
            # Inserisce nuovo
            cursor.execute('INSERT INTO teams_links (insegnamento, link) VALUES (?, ?)', 
                          (insegnamento, link))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Errore nel salvataggio del link Teams: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def get_teams_links() -> Dict[str, str]:
    """
    Ottiene tutti i link Teams dal database.
    
    Returns:
        dict: Dizionario con insegnamenti come chiavi e link Teams come valori
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT insegnamento, link FROM teams_links')
        results = cursor.fetchall()
        
        teams_links = {row[0]: row[1] for row in results}
        
        conn.close()
        return teams_links
        
    except Exception as e:
        logger.error(f"Errore nel recupero dei link Teams: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return {}

def get_teams_link(insegnamento: str) -> Optional[str]:
    """
    Ottiene il link Teams per un insegnamento specifico.
    
    Args:
        insegnamento: Nome dell'insegnamento
        
    Returns:
        str: Link Teams o None se non trovato
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT link FROM teams_links WHERE insegnamento = ?', (insegnamento,))
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else None
        
    except Exception as e:
        logger.error(f"Errore nel recupero del link Teams per '{insegnamento}': {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def delete_teams_link(insegnamento: str) -> bool:
    """
    Elimina un link Teams dal database.
    
    Args:
        insegnamento: Nome dell'insegnamento
        
    Returns:
        bool: True se l'eliminazione è riuscita, False altrimenti
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM teams_links WHERE insegnamento = ?', (insegnamento,))
        conn.commit()
        
        deleted = cursor.rowcount > 0
        conn.close()
        
        return deleted
        
    except Exception as e:
        logger.error(f"Errore nell'eliminazione del link Teams per '{insegnamento}': {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def migrate_teams_links_from_json() -> bool:
    """
    Migra i link Teams dal file JSON al database SQLite.
    
    Returns:
        bool: True se la migrazione è riuscita, False altrimenti
    """
    try:
        from teams_utils import load_teams_links as load_teams_links_json
        
        # Carica i link dal JSON
        teams_links = load_teams_links_json()
        
        if not teams_links:
            logger.warning("Nessun link Teams da migrare")
            return False
            
        success_count = 0
        
        # Salva ogni link nel database
        for insegnamento, link in teams_links.items():
            if save_teams_link(insegnamento, link):
                success_count += 1
                
        logger.info(f"Migrazione Teams links completata: {success_count}/{len(teams_links)} link migrati")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Errore durante la migrazione dei link Teams: {str(e)}")
        return False

def get_stats() -> Dict[str, Any]:
    """
    Ottiene statistiche dal database.
    
    Returns:
        dict: Dizionario con varie statistiche sui dati
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Numero totale di lezioni
        cursor.execute('SELECT COUNT(*) FROM lezioni')
        stats['total_lessons'] = cursor.fetchone()[0]
        
        # Numero di docenti
        cursor.execute('SELECT COUNT(*) FROM docenti')
        stats['total_teachers'] = cursor.fetchone()[0]
        
        # Numero di dipartimenti
        cursor.execute('SELECT COUNT(*) FROM dipartimenti')
        stats['total_departments'] = cursor.fetchone()[0]
        
        # Totale CFU
        cursor.execute('SELECT SUM(cfu) FROM lezioni')
        stats['total_cfu'] = cursor.fetchone()[0] or 0
        
        # Distribuzione per dipartimento
        cursor.execute('''
            SELECT d.nome, COUNT(*) 
            FROM lezioni l
            JOIN dipartimenti d ON l.dipartimento_id = d.id
            GROUP BY d.nome
        ''')
        stats['lessons_by_department'] = dict(cursor.fetchall())
        
        # Distribuzione per docente (top 10)
        cursor.execute('''
            SELECT d.nome, COUNT(*) 
            FROM lezioni l
            JOIN docenti d ON l.docente_id = d.id
            GROUP BY d.nome
            ORDER BY COUNT(*) DESC
            LIMIT 10
        ''')
        stats['lessons_by_teacher'] = dict(cursor.fetchall())
        
        # Distribuzione per mese
        cursor.execute('''
            SELECT mese, COUNT(*) 
            FROM lezioni 
            GROUP BY mese
        ''')
        stats['lessons_by_month'] = dict(cursor.fetchall())
        
        conn.close()
        return stats
        
    except Exception as e:
        logger.error(f"Errore nel recupero delle statistiche: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return {}

# Verifica se il modulo è eseguito direttamente
if __name__ == "__main__":
    # Inizializza il database e migra i dati
    print("Inizializzazione del database...")
    if init_db():
        print("Database inizializzato con successo")
        
        print("Migrazione dati dal JSON...")
        if migrate_from_json():
            print("Dati migrati con successo")
        else:
            print("Nessun dato migrato o errore durante la migrazione")
            
        print("Migrazione link Teams dal JSON...")
        if migrate_teams_links_from_json():
            print("Link Teams migrati con successo")
        else:
            print("Nessun link Teams migrato o errore durante la migrazione")
    else:
        print("Errore nell'inizializzazione del database")
