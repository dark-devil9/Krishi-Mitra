# main.py
# Description: This script creates the main FastAPI server application.
# It provides API endpoints to handle user queries by routing them to the
# appropriate data source (live weather API or the book-based RAG model).

from fastapi import FastAPI, HTTPException
import uvicorn

# --- Import Core Logic ---
# Import the functions from your other specialized modules.
try:
    from data_sources import get_weather_forecast
    from qna import get_answer_from_books
    from ner_utils import extract_location_from_query
    from translator import detect_language, translate_text
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure data_sources.py, qna.py, ner_utils.py, and translator.py are in the same directory.")
    exit()

# --- Initialize FastAPI App ---
app = FastAPI(
    title="Krishi Mitra API (Multilingual)",
    description="An intelligent assistant for agricultural queries, supporting multiple Indian languages.",
    version="1.1.0"
)

# --- API Endpoints ---

@app.post("/ask", summary="Ask a multilingual question to the RAG model")
async def ask_question(query: str):
    """
    This is the main endpoint for all user queries. It intelligently routes
    the question to the correct backend service after handling language translation.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # --- Multilingual Workflow ---
    # 1. Detect the original language of the query
    original_lang = detect_language(query)
    print(f"Detected language: {original_lang}")

    # 2. Translate the query to English for processing
    processing_query = query
    if original_lang != 'en':
        processing_query = translate_text(query, 'en')
        print(f"Translated query to English: '{processing_query}'")

    # --- Smart Routing Logic (uses the English query) ---
    answer_en = ""
    source = ""
    retrieved_context = []

    if "weather" in processing_query.lower():
        # Use NER to robustly extract the location
        location = extract_location_from_query(processing_query)
        
        if not location:
            answer_en = "I see you're asking about the weather, but I couldn't identify a specific location. Please mention a city or pincode."
            source = "Internal Logic"
        else:
            print(f"Routing to weather forecast for extracted location: '{location}'")
            answer_en = get_weather_forecast(location)
            source = "Open-Meteo API"
    else:
        print(f"Detected general knowledge query: '{processing_query}'")
        answer_en, sources = get_answer_from_books(processing_query)
        source = "Agricultural Knowledge Base"
        retrieved_context = sources

    # --- Translate the answer back to the original language ---
    final_answer = answer_en
    if original_lang != 'en':
        final_answer = translate_text(answer_en, original_lang)
        print(f"Translated answer back to {original_lang}: '{final_answer}'")

    return {
        "original_query": query,
        "language": original_lang,
        "answer": final_answer,
        "source": source,
        "retrieved_context": retrieved_context
    }

@app.get("/alerts", summary="Get proactive alerts")
async def get_alerts():
    """
    This endpoint is a placeholder for Day 2.
    It will eventually fetch proactive alerts (e.g., frost warnings)
    from the PostgreSQL database.
    """
    return {"alerts": ["Placeholder: No active alerts at this time."]}


# --- Run the Server ---
if __name__ == "__main__":
    print("Starting FastAPI server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
