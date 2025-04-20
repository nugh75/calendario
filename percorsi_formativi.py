"""
Definizione dei percorsi formativi e dei CFU richiesti per ogni area secondo il DPCM 4 agosto 2023.

Questo modulo contiene le definizioni delle aree formative e i relativi CFU richiesti
per ogni percorso formativo (PeF60, PeF30 all.2, PeF36 all.5, PeF30 art.13).
"""

# Definizione delle aree formative
AREE_FORMATIVE = [
    "Disciplinare",      # Didattiche delle discipline e metodologie delle discipline di riferimento
    "Trasversale",       # Area trasversale, comuni a tutte le classi di concorso
    "Tirocinio Diretto", # Tirocinio diretto da svolgersi presso le istituzioni scolastiche
    "Tirocinio Indiretto" # Tirocinio indiretto da svolgersi presso l'Università
]

# Dettaglio delle aree trasversali per ogni percorso
SUBAREE_TRASVERSALI = [
    "Area pedagogica",
    "Formazione inclusiva persone con BES",
    "Metodologie didattiche",
    "Discipline psico-socio-antropologiche",
    "Area linguistico-digitale",
    "Discipline relative alla legislazione scolastica"
]

# Definizione dei percorsi formativi secondo il DPCM 4 agosto 2023
PERCORSI_CFU = {
    "PeF60 all.1": {
        "Disciplinare": 16,
        "Trasversale": 24,
        "Tirocinio Diretto": 15,
        "Tirocinio Indiretto": 5,
        "Trasversale_dettaglio": {
            "Area pedagogica": 10,
            "Formazione inclusiva persone con BES": 3,
            "Metodologie didattiche": 2,
            "Discipline psico-socio-antropologiche": 4,
            "Area linguistico-digitale": 3,
            "Discipline relative alla legislazione scolastica": 2
        }
    },
    "PeF30 all.2": {
        "Disciplinare": 4,
        "Trasversale": 17,
        "Tirocinio Diretto": 0,
        "Tirocinio Indiretto": 9,
        "Trasversale_dettaglio": {
            "Area pedagogica": 4,
            "Formazione inclusiva persone con BES": 3,
            "Metodologie didattiche": 2,
            "Discipline psico-socio-antropologiche": 3,
            "Area linguistico-digitale": 3,
            "Discipline relative alla legislazione scolastica": 2
        }
    },
    "PeF36 all.5": {
        "Disciplinare": 13,
        "Trasversale": 10,
        "Tirocinio Diretto": 10,
        "Tirocinio Indiretto": 3,
        "Trasversale_dettaglio": {
            "Area pedagogica": 3,
            "Formazione inclusiva persone con BES": 0,
            "Metodologie didattiche": 2,
            "Discipline psico-socio-antropologiche": 0,
            "Area linguistico-digitale": 3,
            "Discipline relative alla legislazione scolastica": 2
        }
    },
    "PeF30 art.13": {
        "Disciplinare": 16,
        "Trasversale": 14,
        "Tirocinio Diretto": 0,
        "Tirocinio Indiretto": 0,
        "Trasversale_dettaglio": {
            "Area pedagogica": 6,
            "Formazione inclusiva persone con BES": 3,
            "Metodologie didattiche": 2,
            "Discipline psico-socio-antropologiche": 2,
            "Area linguistico-digitale": 1,
            "Discipline relative alla legislazione scolastica": 0
        }
    }
}

# Lista delle classi considerate trasversali
CLASSI_TRASVERSALI = ["Trasversale A", "Trasversale B", "Trasversale", "Insegnamenti trasversali", "Obiettivi trasversali"]

# Definizione dei gruppi di classi A (umanistiche) e B (scientifiche)
# Classi che mostrano anche risultati della Trasversale A quando cercate (umanistiche)
CLASSI_GRUPPO_A = [
    'A001', 'A007', 'A008', 'A011', 'A012', 'A013', 'A017', 'A018', 'A019',
    'A022', 'A023', 'AA24', 'AB24', 'AC24', 'AL24', 'A029', 'A030',
    'A037', 'A053', 'A054', 'A061', 'A063', 'A064'
]

# Classi che mostrano anche risultati della Trasversale B quando cercate (scientifiche)
CLASSI_GRUPPO_B = [
    'A020', 'A026', 'A027', 'A028', 'A040', 'A042', 'A045', 'A046',
    'A050', 'A060', 'B015'
]

# Mappa per collegare le discipline alle aree formative
MAPPA_DISCIPLINE_AREE = {
    # Esempio: La chiave è parte del nome dell'insegnamento, il valore è l'area formativa
    "didattiche discipline": "Disciplinare",
    "metodologie discipline": "Disciplinare",
    "area pedagogica": "Trasversale",
    "formazione inclusiva": "Trasversale",
    "inclusiva bes": "Trasversale",
    "metodologie didattiche": "Trasversale",
    "psico": "Trasversale",
    "socio antropolog": "Trasversale",
    "linguistico": "Trasversale",
    "digitale": "Trasversale",
    "legislazione": "Trasversale"
    # Tirocini non ancora implementati nell'applicazione
    # "tirocinio diretto": "Tirocinio Diretto",
    # "tirocinio indiretto": "Tirocinio Indiretto"
}

# Mappa per collegare le discipline alle subaree trasversali
MAPPA_DISCIPLINE_SUBAREE = {
    # Esempio: La chiave è parte del nome dell'insegnamento, il valore è la subarea trasversale
    "area pedagogica": "Area pedagogica",
    "pedagogia": "Area pedagogica",
    "formazione inclusiva": "Formazione inclusiva persone con BES",
    "inclusiva bes": "Formazione inclusiva persone con BES",
    "metodologie didattiche": "Metodologie didattiche",
    "psico": "Discipline psico-socio-antropologiche",
    "socio antropolog": "Discipline psico-socio-antropologiche",
    "linguistico": "Area linguistico-digitale",
    "digitale": "Area linguistico-digitale",
    "legislazione": "Discipline relative alla legislazione scolastica"
}

def classifica_insegnamento(denominazione: str, classe_concorso: str = None) -> dict:
    """
    Classifica un insegnamento nelle aree formative e nelle subaree trasversali
    in base alla sua denominazione e classe di concorso.
    
    Args:
        denominazione: La denominazione dell'insegnamento
        classe_concorso: La classe di concorso (opzionale)
        
    Returns:
        dict: Un dizionario con l'area formativa e eventualmente la subarea trasversale
    """
    denominazione = denominazione.lower() if denominazione else ""
    
    # Default se non trovato
    classificazione = {
        "area": "Non classificato",
        "subarea": None,
        "gruppo_trasversale": None  # Aggiunto per distinguere Trasversale A e B
    }
    
    # Se la classe di concorso è fornita e fa parte delle classi trasversali,
    # classifica automaticamente come Trasversale
    if classe_concorso and classe_concorso in CLASSI_TRASVERSALI:
        classificazione["area"] = "Trasversale"
        
        # Determina se è Trasversale A o B
        if classe_concorso == "Trasversale A":
            classificazione["gruppo_trasversale"] = "A"
        elif classe_concorso == "Trasversale B":
            classificazione["gruppo_trasversale"] = "B"
    else:
        # Altrimenti, se la classe di concorso è specificata, è disciplinare
        # (a meno che non sia riconosciuta come trasversale dal nome)
        if classe_concorso and classe_concorso not in ["", "nan", None, "None"]:
            classificazione["area"] = "Disciplinare"
            
            # Determina anche a quale gruppo appartiene (A o B)
            if classe_concorso in CLASSI_GRUPPO_A:
                classificazione["gruppo_trasversale"] = "A"
            elif classe_concorso in CLASSI_GRUPPO_B:
                classificazione["gruppo_trasversale"] = "B"
    
        # Prova a cercare nelle mappe usando la denominazione
        for keyword, area in MAPPA_DISCIPLINE_AREE.items():
            if keyword.lower() in denominazione:
                classificazione["area"] = area
                break
    
    # Se è un'area trasversale, cerca anche la subarea
    if classificazione["area"] == "Trasversale":
        for keyword, subarea in MAPPA_DISCIPLINE_SUBAREE.items():
            if keyword.lower() in denominazione:
                classificazione["subarea"] = subarea
                break
    
    return classificazione
