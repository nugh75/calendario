"""
Modulo per la gestione dei log nell'applicazione.
"""
import logging
import os
import sys
import time
from datetime import datetime

# Configurazione dei log
LOG_FOLDER = "logs"
LOG_FILE = os.path.join(LOG_FOLDER, f"calendario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

def setup_logger(name="calendario"):
    """
    Configura un logger che scrive sia su file che su console.
    
    Args:
        name: Nome del logger
        
    Returns:
        logging.Logger: Logger configurato
    """
    # Assicurati che la cartella dei log esista
    if not os.path.exists(LOG_FOLDER):
        os.makedirs(LOG_FOLDER)
    
    # Crea il logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Formattazione dei log
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] - %(message)s')
    
    # Handler per file
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Handler per console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    # Aggiungi gli handler al logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"Logger inizializzato. Log scritti su: {LOG_FILE}")
    
    return logger

# Logger globale dell'applicazione
logger = setup_logger()
