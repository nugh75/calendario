"""
Funzioni di validazione per verificare la compatibilità dei dati con il database SQLite.
Queste funzioni sono utilizzate per debug e verifica dei dati importati.
"""

def validate_record_schema(record: dict) -> tuple:
    """
    Verifica se un record è compatibile con lo schema del database SQLite.
    Controlla tipi di dati, valori richiesti e altri vincoli.
    
    Args:
        record (dict): Record da validare
        
    Returns:
        tuple: (is_valid, message) dove is_valid è True se il record è valido,
               e message è un messaggio di errore o una stringa vuota
    """
    errors = []
    
    # Verifica campi obbligatori
    required_fields = ["Data", "Orario", "Denominazione Insegnamento", "Docente"]
    for field in required_fields:
        if field not in record or not record[field]:
            errors.append(f"Campo obbligatorio mancante: {field}")
    
    # Se mancano campi obbligatori, ritorna subito
    if errors:
        return False, "; ".join(errors)
    
    # Verifica tipo di data
    if "Data" in record:
        if not pd.isna(record["Data"]):
            if not isinstance(record["Data"], (pd.Timestamp, datetime)):
                errors.append("Il campo Data deve essere una data valida")
    
    # Verifica CFU (deve essere convertibile a numero)
    if "CFU" in record and record["CFU"]:
        try:
            float(str(record["CFU"]).replace(',', '.'))
        except ValueError:
            errors.append("Il campo CFU deve essere un numero valido")
    
    # Verifica campi con vincoli specifici
    if "Codice insegnamento" in record and record["Codice insegnamento"]:
        # Rimuovi eventuali parti decimali (es. 12345.0 -> 12345)
        code = str(record["Codice insegnamento"])
        if '.' in code and code.split('.')[1] == '0':
            code = code.split('.')[0]
        # Verifica la lunghezza del codice (esempio: deve essere almeno 4 caratteri)
        if len(code) < 4 and code.strip():
            errors.append(f"Codice insegnamento troppo corto ({code}), dovrebbe avere almeno 4 caratteri")
    
    # Se non ci sono errori, il record è valido
    if not errors:
        return True, ""
    else:
        return False, "; ".join(errors)

def get_db_schema() -> dict:
    """
    Recupera lo schema del database SQLite per scopi di debugging.
    
    Returns:
        dict: Schema del database con tabelle e colonne
    """
    try:
        from db_utils import get_connection
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Ottieni la lista delle tabelle
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        schema = {}
        for table in tables:
            table_name = table[0]
            # Salta le tabelle di sistema
            if table_name.startswith('sqlite_'):
                continue
            
            # Ottieni le informazioni sulle colonne
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns_info = cursor.fetchall()
            
            columns = []
            for col in columns_info:
                # col[1] è il nome della colonna, col[2] è il tipo
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "required": col[3] == 1,  # NOT NULL constraint
                    "primary_key": col[5] == 1  # PRIMARY KEY
                })
            
            schema[table_name] = columns
            
        conn.close()
        return schema
        
    except Exception as e:
        import traceback
        try:
            from log_utils import logger
            logger.error(f"Errore nel recupero dello schema del database: {str(e)}")
            logger.error(traceback.format_exc())
        except ImportError:
            pass
        return {"error": str(e)}
