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
    entities (GPE) like cities and states, with special handling for Indian locations.
    """
    if not nlp:
        return None

    query_lower = query.lower().strip()
    
    # --- 1. Prioritize Pincode Extraction ---
    # Regex is the most reliable way to find a 6-digit Indian pincode.
    pincode_match = re.search(r'\b\d{6}\b', query)
    if pincode_match:
        pincode = pincode_match.group(0)
        print(f"NER found a pincode: {pincode}")
        return pincode

    # --- 2. Enhanced Indian Location Pattern Matching ---
    # Common Indian cities, districts, and states
    indian_locations = [
        # Major cities
        'mumbai', 'delhi', 'bangalore', 'hyderabad', 'chennai', 'kolkata', 'pune', 'ahmedabad', 'jaipur', 'lucknow',
        'kanpur', 'nagpur', 'indore', 'thane', 'bhopal', 'visakhapatnam', 'patna', 'vadodara', 'ghaziabad', 'ludhiana',
        # States
        'andhra pradesh', 'arunachal pradesh', 'assam', 'bihar', 'chhattisgarh', 'goa', 'gujarat', 'haryana', 
        'himachal pradesh', 'jharkhand', 'karnataka', 'kerala', 'madhya pradesh', 'maharashtra', 'manipur', 
        'meghalaya', 'mizoram', 'nagaland', 'odisha', 'punjab', 'rajasthan', 'sikkim', 'tamil nadu', 
        'telangana', 'tripura', 'uttar pradesh', 'uttarakhand', 'west bengal',
        # Union Territories
        'andaman and nicobar islands', 'chandigarh', 'dadra and nagar haveli and daman and diu', 
        'delhi', 'jammu and kashmir', 'ladakh', 'lakshadweep', 'puducherry',
        # Common districts
        'jamdoli', 'ajmer', 'udaipur', 'jodhpur', 'bikaner', 'kota', 'sikar', 'alwar', 'bharatpur', 'dholpur'
    ]
    
    # Look for Indian locations in the query
    for location in indian_locations:
        if location in query_lower:
            print(f"Found Indian location: {location}")
            return location.title()
    
    # --- 3. Use spaCy for Named Entity Recognition ---
    doc = nlp(query)
    
    # GPE = Geopolitical Entity (cities, states, countries)
    # LOC = Location (non-GPE locations, like mountain ranges, bodies of water)
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            location_name = ent.text
            print(f"NER found a location entity: {location_name} ({ent.label_})")
            # Return the first location entity found
            return location_name
    
    # --- 4. Fallback: Look for common location patterns ---
    # Pattern: "in [location]" or "at [location]" or "for [location]"
    location_patterns = [
        r'\bin\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)',
        r'\bat\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)',
        r'\bfor\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)',
        r'\b([a-zA-Z\s]+?)\s+(?:weather|price|market|mandi)',
        r'\b(?:weather|price|market|mandi)\s+(?:in|at|for)\s+([a-zA-Z\s]+?)(?:\s|$|,|\.)'
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, query_lower)
        if match:
            location = match.group(1).strip()
            # Clean up the location
            location = re.sub(r'\b(in|at|for|the|a|an|is|are|what|how|much|does|cost|price|of)\b', '', location, flags=re.IGNORECASE).strip()
            if location and len(location) > 2:
                print(f"Pattern matched location: {location}")
                return location.title()
            
    print("NER did not find any location entities in the query.")
    return None

# Example for testing the function directly
if __name__ == "__main__":
    test_queries = [
        "what is the price of rice in Jaipur Rajasthan",
        "what is the price of rice in Jaipur",
        "weather in Delhi",
        "market prices in Mumbai",
        "what crops grow in Punjab",
        "how is the weather today", # Should return None
        "price of wheat in Bangalore Karnataka"
    ]
    for q in test_queries:
        location = extract_location_from_query(q)
        print(f"Query: '{q}' -> Extracted Location: '{location}'\n")

