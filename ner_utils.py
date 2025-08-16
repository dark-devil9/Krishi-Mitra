# ner_utils.py
import spacy
import re

try:
    # Load the small English model for Named Entity Recognition.
    nlp = spacy.load("en_core_web_sm")
    print("spaCy NLP model 'en_core_web_sm' loaded successfully.")
except OSError:
    print("spaCy model not found. Please run this command first:")
    print("python -m spacy download en_core_web_sm")
    nlp = None

def extract_location_from_query(query: str):
    """
    Analyzes a query to find the most likely location.
    It prioritizes 6-digit pincodes, then looks for named locations.
    """
    if not nlp:
        return None

    # 1. Regex is the most reliable way to find an Indian pincode.
    pincode_match = re.search(r'\b\d{6}\b', query)
    if pincode_match:
        pincode = pincode_match.group(0)
        print(f"NER found a pincode: {pincode}")
        return pincode

    # 2. If no pincode, use spaCy to find a named location.
    doc = nlp(query)
    # GPE (Geopolitical Entity) and LOC (Location) are the most relevant labels.
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            location_name = ent.text
            print(f"NER found a location entity: {location_name} ({ent.label_})")
            return location_name
            
    print("NER did not find any location entities in the query.")
    return None
