# app.py

import os
import whisper
import tempfile
import io
import torch
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from gtts import gTTS
from deep_translator import GoogleTranslator

# --- Import all our logic modules ---
from qna import initialize_components, retrieve_context, generate_answer
from data_sources import get_weather_forecast
from ner_utils import extract_location_from_query

# --- GPU & Model Initialization ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {DEVICE}")

print("Loading AI models...")
stt_model = whisper.load_model("base", device=DEVICE)
embedding_model, collection, mistral_client = initialize_components(device=DEVICE)
print("Models loaded successfully.")

app = FastAPI(
    title="Krishi Mitra API",
    description="An intelligent assistant for agricultural queries, with live weather data and multilingual support.",
    version="4.0.0" # Version updated
)

# --- Pydantic Model for Text Input ---
class TextQuery(BaseModel):
    query_text: str

# --- Helper Functions (Reused by both endpoints) ---
def text_to_speech(text: str, lang: str):
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        print(f"Error in text-to-speech for language '{lang}': {e}")
        return None

def detect_language(text: str):
    try:
        lang = GoogleTranslator(source='auto', target='en').detect(text)
        return lang[0] if isinstance(lang, list) else lang
    except Exception:
        return "en"

def translate_text(text: str, target: str, source: str = 'auto'):
    if not text: return ""
    try:
        return GoogleTranslator(source=source, target=target).translate(text)
    except Exception:
        return text

def get_smart_answer(query_in_english: str):
    """Core logic to route a query and get an answer in English."""
    source = ""
    if "weather" in query_in_english.lower():
        location = extract_location_from_query(query_in_english)
        if not location:
            answer_en = "I can get the weather for you, but please specify a city or pincode."
            source = "Logic"
        else:
            print(f"Routing to weather API for location: '{location}'")
            answer_en = get_weather_forecast(location)
            source = "Open-Meteo Weather API"
    else:
        print("Routing to RAG model (knowledge base)...")
        context = retrieve_context(query_in_english, collection, embedding_model)
        answer_en = generate_answer(query_in_english, context, mistral_client)
        source = "Knowledge Base (Documents)"
    return answer_en, source

# --- NEW: Separate API Endpoints ---

@app.post("/ask-text", response_class=JSONResponse)
async def ask_text(query: TextQuery):
    """Handles questions submitted as text and returns a text answer."""
    original_query = query.query_text
    if not original_query:
        raise HTTPException(status_code=400, detail="Query text cannot be empty.")

    original_lang = detect_language(original_query)
    processing_query = translate_text(original_query, 'en', original_lang)
    
    answer_en, source = get_smart_answer(processing_query)
    
    final_answer = translate_text(answer_en, original_lang, 'en')

    return JSONResponse(content={
        "answer": final_answer,
        "language": original_lang,
        "source": source
    })


@app.post("/ask-voice", response_class=StreamingResponse)
async def ask_voice(file: UploadFile = File(...)):
    """Handles questions submitted as an audio file and returns a spoken answer."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        temp_audio.write(await file.read())
        temp_path = temp_audio.name
    
    result = stt_model.transcribe(temp_path)
    original_query = result["text"].strip()
    original_lang = result["language"]
    os.remove(temp_path)

    if not original_query:
        raise HTTPException(status_code=400, detail="Could not understand the audio.")

    processing_query = translate_text(original_query, 'en', original_lang)

    answer_en, source = get_smart_answer(processing_query)

    final_answer = translate_text(answer_en, original_lang, 'en')
    
    audio_response_file = text_to_speech(final_answer, lang=original_lang)
    if not audio_response_file:
        raise HTTPException(status_code=500, detail="Failed to generate audio response.")

    return StreamingResponse(
        audio_response_file,
        media_type="audio/mpeg",
        headers={
            'X-Answer-Text': final_answer.encode('utf-8'),
            'X-Source': source
        }
    )