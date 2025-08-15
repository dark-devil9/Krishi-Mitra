# ner_utils.py
# Description: This module uses spaCy for Named Entity Recognition (NER)
# to robustly extract location names and pincodes from user queries.

import spacy
import re

# Load the spaCy model once when the module is loaded.
# This is efficient as it avoids reloading the model on every request.
try:
    nlp = spacy.load("en_core_web_sm")
    print("spaCy NLP model loaded successfully.")
except OSError:
    print("spaCy model not found. Please run 'python -m spacy download en_core_web_sm'")
    nlp = None

def extract_location_from_query(query: str):
    """
    Analyzes a query to find the most likely location entity.
    It prioritizes 6-digit pincodes first, then looks for geopolitical
    entities (GPE) like cities and states.

    Args:
        query (str): The user's full question (e.g., "I live in jamdoli
                     district of jaipur what is the weather there my
                     pincode is 302031").

    Returns:
        str | None: The extracted location string (e.g., "302031" or "jaipur")
                     or None if no location is found.
    """
    if not nlp:
        return None

    # --- 1. Prioritize Pincode Extraction ---
    # Regex is the most reliable way to find a 6-digit Indian pincode.
    pincode_match = re.search(r'\b\d{6}\b', query)
    if pincode_match:
        pincode = pincode_match.group(0)
        print(f"NER found a pincode: {pincode}")
        return pincode

    # --- 2. Use spaCy for Named Entity Recognition ---
    doc = nlp(query)
    
    # GPE = Geopolitical Entity (cities, states, countries)
    # LOC = Location (non-GPE locations, like mountain ranges, bodies of water)
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            location_name = ent.text
            print(f"NER found a location entity: {location_name} ({ent.label_})")
            # Return the first location entity found
            return location_name
            
    print("NER did not find any location entities in the query.")
    return None

# Example for testing the function directly
if __name__ == "__main__":
    test_queries = [
        "I live in jamdoli district of jaipur what is the weather there my pincode is 302031",
        "what is the weather in mumbai?",
        "delhi weather forecast",
        "how is the weather today", # Should return None
        "what crops grow in punjab" # Should return punjab
    ]
    for q in test_queries:
        location = extract_location_from_query(q)
        print(f"Query: '{q}' -> Extracted Location: '{location}'\n")

