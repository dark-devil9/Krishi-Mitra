# main.py (Final Workflow Version with Contextual Chat Fix)
# Description: Implements a clear user workflow and a context-aware chat agent.

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import uuid
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, JSONResponse
import base64
import tempfile
import os

import re
from rapidfuzz import fuzz


# --- Import Core Logic ---
try:
    from data_sources import get_weather_forecast, get_market_prices, get_weather_brief, get_price_quote, compare_market_prices, get_price_trend, agmark_qna_answer
    from qna import get_answer_from_books, generate_advisory_answer
    from ner_utils import extract_location_from_query
    from translator import detect_language, translate_text, transliterate_to_latin, is_latin_script
except ImportError as e:
    print(f"Error importing modules: {e}")
    exit()

# --- Optional: Whisper ASR and gTTS (lazy-loaded) ---
whisper_model = None
faster_whisper_model = None

def _transcribe_file(tmp_path: str) -> str:
    global whisper_model, faster_whisper_model
    # Try Whisper (may fail with NumPy/Numba mismatch)
    try:
        import whisper
        if whisper_model is None:
            whisper_model = whisper.load_model("small")
        result = whisper_model.transcribe(tmp_path, fp16=False)
        return (result.get('text') or '').strip()
    except Exception as e:
        print(f"Whisper init/usage failed: {e}")
    # Fallback: faster-whisper (no Numba dependency)
    try:
        from faster_whisper import WhisperModel
        if faster_whisper_model is None:
            faster_whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, info = faster_whisper_model.transcribe(tmp_path)
        text = " ".join([seg.text for seg in segments])
        return text.strip()
    except Exception as e:
        print(f"faster-whisper failed: {e}")
        return ""

tts_model = None
async def _tts_bytes_async(text: str, voice: str = 'en-IN-NeerjaNeural') -> bytes:
    """Generate TTS audio using Edge TTS (Indian voices), returns MP3 bytes."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text=text, voice=voice)
        audio_bytes = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])
        return bytes(audio_bytes)
    except Exception as e:
        print(f"Edge TTS error: {e}")
        return b""

# --- In-Memory Storage (for Hackathon) ---
user_profiles = {}
user_alerts = {}
onboarding_sessions = {}
from ner_utils import extract_location_from_query

def detect_intent_nlp(q: str):
    """
    Smart intent detection that understands context and nuances
    """
    ql = q.lower().strip()
    
    # Smart growing cost detection
    if any(word in ql for word in ['cost to grow', 'growing cost', 'cultivation cost', 'farm cost', 'production cost']):
        return "growing_cost"
    
    # Smart weather patterns with context
    weather_keywords = ['rain', 'weather', 'forecast', 'temp', 'temperature', 'humidity', 'wind', 
                       'sunny', 'cloudy', 'storm', 'hot', 'cold', 'warm', 'cool', 'dry', 'wet',
                       'frost', 'heat stress', 'et0', 'wind gusts']
    if any(word in ql for word in weather_keywords):
        return "weather"
    
    # Smart market/price patterns with context
    market_keywords = ['price', 'rate', 'modal', 'mandi', 'msp', 'bhav', 'cost', 'value', 'market', 
                      'sell', 'buy', 'commodity', 'trend', 'arrival', 'liquidity']
    if any(word in ql for word in market_keywords):
        return "market"
    
    # Smart agricultural decisions
    agri_keywords = ['crop', 'farming', 'soil', 'fertilizer', 'pest', 'harvest', 'plant', 'seed', 
                    'water', 'season', 'intercrop', 'variety', 'irrigation', 'spray', 'disease']
    if any(word in ql for word in agri_keywords):
        return "agriculture"
    
    # Smart policy/scheme detection
    policy_keywords = ['pm-kisan', 'kalia', 'rythu bandhu', 'pmfby', 'fasal bima', 'soil health card', 
                      'subsidy', 'loan', 'kcc', 'e-nam', 'procurement', 'msp']
    if any(word in ql for word in policy_keywords):
        return "policy"
    
    # Smart logistics/storage
    logistics_keywords = ['sell now', 'store', 'harvest', 'cold storage', 'warehouse', 'logistics', 
                         'timing', 'when to', 'best day', 'procurement window']
    if any(word in ql for word in logistics_keywords):
        return "logistics"
    
    # Smart compliance/export
    compliance_keywords = ['mrl', 'residue', 'export', 'certification', 'organic', 'grading', 'quality', 
                          'compliance', 'penalty', 'pesticide']
    if any(word in ql for word in compliance_keywords):
        return "compliance"
    
    return "general"

def extract_commodity_from_text(q: str):
    """
    Smart commodity extraction that understands context and handles typos
    """
    # Enhanced patterns for better coverage
    patterns = [
        r"(?:price|rate|bhav|cost)\s+of\s+([a-z\s]+?)(?:\s+in\b|$)",
        r"([a-z\s]+)\s+(?:price|rate|bhav|cost)\b",
        r"(?:what|how much)\s+(?:is|are)\s+(?:the\s+)?(?:price|rate|bhav|cost)\s+of\s+([a-z\s]+)",
        r"(?:price|rate|bhav|cost)\s+(?:of|for)\s+([a-z\s]+)",
        r"([a-z\s]+)\s+(?:price|rate|bhav|cost)\s+(?:in|at|for)",
        r"(?:market\s+)?prices?\s+(?:for|of)\s+([a-z\s]+?)(?:\s+in\b|$)",
        r"([a-z\s]+)\s+(?:in|at|for)\s+[a-z\s]+(?:price|rate|bhav|cost)",
        r"(?:price|rate|bhav|cost)\s+([a-z\s]+)\s+in",
        r"([a-z\s]+)\s+(?:price|rate|bhav|cost)\s+in",
        # Growing cost patterns
        r"(?:cost|expense)\s+to\s+grow\s+([a-z\s]+)",
        r"(?:growing|cultivation|production)\s+cost\s+of\s+([a-z\s]+)",
        r"([a-z\s]+)\s+(?:growing|cultivation|production)\s+cost"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, q, flags=re.IGNORECASE)
        if m:
            commodity = m.group(1).strip()
            # Clean up common words that aren't commodities
            commodity = re.sub(r'\b(in|at|for|the|a|an|is|are|what|how|much|does|cost|price|of|market|prices|grow|growing|cultivation|production)\b', '', commodity, flags=re.IGNORECASE).strip()
            if commodity and len(commodity) > 2:
                print(f"Extracted commodity: '{commodity}' from pattern: {pattern}")
                return commodity
    
    # Fallback: look for common agricultural commodities in the query with typo handling
    common_commodities = [
        'rice', 'wheat', 'maize', 'corn', 'potato', 'tomato', 'tomatoes', 'onion', 'garlic', 'ginger',
        'turmeric', 'chilli', 'pepper', 'cardamom', 'cinnamon', 'clove', 'nutmeg',
        'cotton', 'jute', 'sugarcane', 'tea', 'coffee', 'cocoa', 'rubber',
        'pulses', 'lentils', 'chickpea', 'chikpea', 'pigeon pea', 'mung bean', 'black gram',
        'oilseeds', 'mustard', 'sesame', 'sunflower', 'groundnut', 'soybean',
        'fruits', 'apple', 'banana', 'orange', 'mango', 'grapes', 'papaya',
        'vegetables', 'carrot', 'cabbage', 'cauliflower', 'brinjal', 'cucumber',
        'basmati', 'groundnut', 'bajra', 'berseem', 'oats', 'okra'
    ]
    
    # Typo correction mapping
    typo_corrections = {
        'chikpea': 'chickpea',
        'chana': 'chickpea',
        'dal': 'pulses',
        'dhal': 'pulses',
        'bajra': 'pearl millet',
        'jowar': 'sorghum',
        'ragi': 'finger millet'
    }
    
    q_lower = q.lower()
    
    # First check for exact matches
    for commodity in common_commodities:
        if commodity in q_lower:
            print(f"Found commodity in fallback: {commodity}")
            return commodity
    
    # Then check for typos and correct them
    for typo, correct in typo_corrections.items():
        if typo in q_lower:
            print(f"Corrected typo: {typo} -> {correct}")
            return correct
    
    # Finally, look for partial matches
    for commodity in common_commodities:
        if len(commodity) > 3 and commodity in q_lower:
            print(f"Found commodity in partial match: {commodity}")
            return commodity
    
    return None

def extract_growing_cost_context(query: str):
    """
    Extract context for growing cost queries
    """
    context = {}
    
    # Extract land size
    land_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:acres?|hectares?|ha)', query, re.IGNORECASE)
    if land_match:
        context['land_size'] = land_match.group(1)
    
    # Extract location if mentioned
    location = extract_location_from_query(query)
    if location:
        context['location'] = location
    
    # Extract crop type
    crop = extract_commodity_from_text(query)
    if crop:
        context['crop'] = crop
    
    return context

# --- Proactive Alerting Logic ---
def check_for_personalized_alerts():
    print(f"\n--- Running scheduled alert check at {datetime.datetime.now()} ---")
    for user_id, profile in list(user_profiles.items()):
        location = profile.get("location")
        if not location or not profile.get("profileComplete"):
            continue

        print(f"Checking alerts for user {user_id} in {location}...")
        weather_context = get_weather_forecast(location)
        
        # Ask LLM to always provide 2-3 concise suggestions when any alert/risk exists
        alert_prompt = (
            f"Analyze this weather data for {location}.\n"
            "If there are risks like heavy rain, frost, or extreme heat, produce exactly one line starting with 'ALERT: ' summarizing the key risk,\n"
            "then on the next lines provide 2-3 concise 'SUGGESTION: ' items (actionable, distinct, no markdown).\n"
            "If there is no clear risk, still provide 2 short 'SUGGESTION: ' items for good agricultural practice relevant to the forecast.\n\n"
            f"Data:\n{weather_context}"
        )

        response_text = generate_advisory_answer(alert_prompt)

        try:
            lines = [ln.strip() for ln in response_text.splitlines() if ln.strip()]
            alert_line = next((ln for ln in lines if ln.lower().startswith("alert:")), None)
            suggestion_lines = [ln for ln in lines if ln.lower().startswith("suggestion:")]
            # Ensure 2-3 suggestions
            suggestion_lines = suggestion_lines[:3] if len(suggestion_lines) >= 2 else suggestion_lines

            if user_id not in user_alerts:
                user_alerts[user_id] = []

            if alert_line or suggestion_lines:
                user_alerts[user_id].insert(0, {
                    "id": str(uuid.uuid4()),
                    "alert": (alert_line or "ALERT: General advisory"),
                    "suggestions": suggestion_lines if suggestion_lines else ["SUGGESTION: Monitor forecast updates", "SUGGESTION: Plan field work during cooler hours"],
                    "status": "new",
                    "timestamp": datetime.datetime.now().isoformat()
                })
                print(f"SUCCESS: Alert generated for user {user_id} with {len(suggestion_lines) or 2} suggestion(s).")
        except Exception as e:
            print(f"Error parsing LLM alert response for user {user_id}: {e}")

        # Secondary: Government schemes and programs based on profile
        try:
            scheme_prompt = (
                "Based on this farmer profile, list 2-3 relevant CURRENT Indian government schemes or programs (central/state) with a one-line action for each. "
                "Output each on a new line prefixed with 'SUGGESTION: '. Avoid markdown and keep it factual.\n\n"
                f"Profile: {profile}\n"
                "Fields: location (state), land size, age, gender, crops."
            )
            scheme_text = generate_advisory_answer(scheme_prompt)
            scheme_lines = [ln.strip() for ln in scheme_text.splitlines() if ln.strip().lower().startswith("suggestion:")]
            if scheme_lines:
                if user_id not in user_alerts:
                    user_alerts[user_id] = []
                user_alerts[user_id].insert(0, {
                    "id": str(uuid.uuid4()),
                    "alert": "ALERT: Updates on applicable schemes",
                    "suggestions": scheme_lines[:3],
                    "status": "new",
                    "timestamp": datetime.datetime.now().isoformat()
                })
                print(f"SCHEMES: Added {len(scheme_lines[:3])} scheme suggestions for {user_id}.")
        except Exception as e:
            print(f"Scheme suggestion error for user {user_id}: {e}")

# --- FastAPI App Lifecycle (for Scheduler) ---
scheduler = AsyncIOScheduler()
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(check_for_personalized_alerts, 'interval', hours=1)
    scheduler.start()
    yield
    scheduler.shutdown()

# Manual trigger to generate alerts immediately (defined after app initialization)

# --- Initialize FastAPI App ---
app = FastAPI(
    title="Krishi Mitra Agent",
    version="3.3.0", # Final fix version
    lifespan=lifespan
)

# --- Add CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manual trigger to generate alerts immediately
@app.post("/alerts/run-now", summary="Trigger alert generation immediately and return latest alerts")
async def run_alerts_now(user_id: str):
    check_for_personalized_alerts()
    return {"data": user_alerts.get(user_id, [])}

# --- Pydantic Models for Request Bodies ---
class ChatMessage(BaseModel):
    message: str

class AskRequest(BaseModel):
    user_id: str
    query: str

# --- API Endpoints ---

@app.get("/status", summary="Check user's onboarding status")
async def get_user_status(user_id: str):
    if user_id in user_profiles and user_profiles[user_id].get("profileComplete"):
        return {"status": "profile_complete"}
    else:
        return {"status": "new_user"}

@app.post("/chat", summary="Handle the onboarding conversation")
async def onboarding_chat(user_id: str, request: ChatMessage):
    message = request.message
    if user_id not in onboarding_sessions:
        onboarding_sessions[user_id] = {"stage": "asking_location", "profile": {}}
    
    session = onboarding_sessions[user_id]
    stage = session["stage"]

    if stage == "asking_location":
        session["stage"] = "asking_land_size"
        return {"response": "Welcome! To get started, please tell me your location (city or district)."}
    elif stage == "asking_land_size":
        session["profile"]["location"] = message
        session["stage"] = "asking_budget"
        return {"response": f"Got it, {message}. How many acres of land do you have? (e.g., '5 acres', 'NA')"}
    elif stage == "asking_budget": 
        session["profile"]["land_size"] = message
        session["stage"] = "asking_age_gender"
        return {"response": "Understood. What is your approximate budget for this season? (e.g., '50000 rupees', 'NA')"}
    elif stage == "asking_age_gender":
        session["profile"]["budget"] = message
        session["stage"] = "asking_crops"
        return {"response": "Thanks. What is your age and gender?"}
    elif stage == "asking_crops":
        session["profile"]["age"] = ''.join(filter(str.isdigit, message))
        session["profile"]["gender"] = "female" if "female" in message.lower() else "male"
        session["stage"] = "generating_recommendation"
        return {"response": "Almost done. What are you currently growing, or have you not planned yet?"}
    elif stage == "generating_recommendation":
        session["profile"]["current_crops"] = message
        user_profiles[user_id] = {**session["profile"], "profileComplete": True, "email": user_id}
        del onboarding_sessions[user_id]
        return {"response": "Thank you! Your profile is now complete."}
    return {"response": "I'm sorry, something went wrong during setup."}


@app.get("/get-suggestion", summary="Get a timely, on-demand suggestion")
async def get_suggestion(user_id: str):
    if user_id not in user_profiles or not user_profiles[user_id].get("profileComplete"):
        return {"suggestion": "Your personalized suggestions will appear here once your profile is complete."}
    
    profile = user_profiles[user_id]
    weather_context = get_weather_forecast(profile['location'])
    suggestion_prompt = f"Based on this user's profile and the latest weather, provide one single, actionable suggestion. Do not use any markdown formatting.\n\nProfile:\n{profile}\n\nWeather:\n{weather_context}\n\nSuggestion:"
    suggestion = generate_advisory_answer(suggestion_prompt)
    return {"suggestion": suggestion}


@app.get("/alerts", summary="Get personalized alerts and suggestions")
async def get_alerts(user_id: str):
    return {"data": user_alerts.get(user_id, [])}


@app.post("/apply-suggestion", summary="Mark a suggestion as applied")
async def apply_suggestion(user_id: str, suggestion_id: str):
    if user_id in user_alerts:
        for item in user_alerts[user_id]:
            if item["id"] == suggestion_id:
                item["status"] = "applied"
                return {"message": "Suggestion status updated."}
    raise HTTPException(status_code=404, detail="Suggestion or User ID not found.")

from data_sources import (
    get_weather_brief,
    get_market_prices_smart,
    AGMARKNET_API_KEY,
)

@app.post("/ask", summary="Ask a context-aware question")
async def ask_question(request: AskRequest):
    user_id = request.user_id
    query = request.query.strip()

    profile = user_profiles.get(user_id, {})
    
    # Enhanced location extraction with better pincode handling
    place_mention = extract_location_from_query(query)
    if not place_mention:
        place_mention = profile.get("location")
    
    print(f"Extracted location: {place_mention} from query: {query}")

    intent = detect_intent_nlp(query)
    print(f"Detected intent: {intent} for query: {query}")

    # Handle growing cost queries intelligently
    if intent == "growing_cost":
        context = extract_growing_cost_context(query)
        crop = context.get('crop', 'rice')
        location = place_mention or profile.get("location") or "India"
        
        growing_cost_prompt = f"""
        Provide a concise, practical estimate of the cost to grow {crop} in {location}.
        Include: seed cost, fertilizer, pesticides, labor, and total per acre.
        Format: 2-3 bullet points with actual cost estimates.
        If specific data unavailable, provide reasonable estimates based on {location} conditions.
        """
        
        answer, _ = get_answer_from_books(growing_cost_prompt)
        return {"answer": answer}

    # Handle weather queries with context
    if intent == "weather":
        place = place_mention or profile.get("location") or "Jaipur"
        print(f"Fetching weather for: {place}")
        
        # Check if it's a specific weather metric query
        if any(word in query.lower() for word in ['rain', 'rainfall']):
            weather_info = get_weather_brief(place)
            if "High chance of rain" in weather_info:
                weather_info += "\n\n💡 Smart Action: Consider delaying field operations, protect harvested crops, and check drainage."
            return {"answer": weather_info}
        elif any(word in query.lower() for word in ['humidity', 'wind', 'frost', 'heat']):
            weather_info = get_weather_brief(place)
            return {"answer": weather_info}
        else:
            weather_info = get_weather_brief(place)
            return {"answer": weather_info}

    # Handle market/price queries intelligently
    if intent == "market":
        # Delegate to Agmark QnA workflow end-to-end
        place = place_mention or profile.get("location")
        # We pass user_profile to help resolve scope if needed
        answer = agmark_qna_answer(query, user_profile=profile if profile else {"location": place})
        return {"answer": answer}

    # Handle agricultural decisions intelligently
    if intent == "agriculture":
        if "vs" in query.lower() or "comparison" in query.lower():
            comparison_prompt = f"Provide a smart comparison for this agricultural decision: {query}. Include pros/cons and recommendation based on {place_mention or 'your location'}."
            answer, _ = get_answer_from_books(comparison_prompt)
            return {"answer": answer}
        
        elif "when to" in query.lower() or "timing" in query.lower():
            timing_prompt = f"Provide optimal timing advice for this agricultural activity: {query}. Consider weather, season, and best practices."
            answer, _ = get_answer_from_books(timing_prompt)
            return {"answer": answer}
        
        else:
            agri_prompt = f"Provide smart, actionable agricultural advice for: {query}. Consider location: {place_mention or 'your area'}. Keep it practical and specific."
            answer, _ = get_answer_from_books(agri_prompt)
            return {"answer": answer}

    # Handle policy/scheme queries
    if intent == "policy":
        policy_prompt = f"""
        Answer this policy/scheme question intelligently: {query}
        
        User Profile:
        - Location: {profile.get('location', 'N/A')}
        - Land Size: {profile.get('land_size', 'N/A')}
        - Age: {profile.get('age', 'N/A')}
        - Gender: {profile.get('gender', 'N/A')}
        
        Provide: eligibility status (yes/no), key requirements, and next steps.
        Format: 2-3 bullet points maximum.
        """
        answer, _ = get_answer_from_books(policy_prompt)
        return {"answer": answer}

    # Handle logistics/storage queries
    if intent == "logistics":
        logistics_prompt = f"""
        Provide smart logistics advice for: {query}
        Consider: timing, market conditions, storage options, and cost-benefit analysis.
        Give specific, actionable recommendations.
        """
        answer, _ = get_answer_from_books(logistics_prompt)
        return {"answer": answer}

    # Handle compliance/export queries
    if intent == "compliance":
        compliance_prompt = f"""
        Answer this compliance/export question: {query}
        Provide: requirements, steps, costs, and timeline.
        Keep it practical and actionable.
        """
        answer, _ = get_answer_from_books(compliance_prompt)
        return {"answer": answer}

    # General questions - try to be helpful and smart
    if not user_id or user_id not in user_profiles:
        general_prompt = f"""
        Answer this question intelligently: {query}
        If it's about agriculture, farming, or rural development, provide practical advice.
        If it's about weather, markets, or policies, be specific and actionable.
        Keep response to 2-3 sentences maximum.
        """
        answer, _ = get_answer_from_books(general_prompt)
        return {"answer": answer}

    # For users with profiles, provide contextual answers
    contextual_prompt = f"""
    Answer this question intelligently and contextually: {query}
    
    User Profile:
    - Location: {profile.get('location','N/A')}
    - Land Size: {profile.get('land_size','N/A')}
    - Budget: {profile.get('budget','N/A')}
    - Age: {profile.get('age','N/A')}
    - Gender: {profile.get('gender','N/A')}
    - Current Crops: {profile.get('current_crops','N/A')}
    
    Provide smart, actionable advice considering their profile.
    If agricultural question, be location-specific and practical.
    Keep response to 2-3 sentences maximum.
    """
    answer, _ = get_answer_from_books(contextual_prompt)
    return {"answer": answer}

# ================== Voice Support Endpoints ==================

class VoiceAskResponse(BaseModel):
    answer: str
    audio_b64: str | None = None

@app.post("/voice/transcribe", summary="Transcribe audio to text (Whisper/faster-whisper)")
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or '')[-1] or '.wav') as tmp:
            data = await file.read()
            tmp.write(data)
            tmp_path = tmp.name
        text = _transcribe_file(tmp_path)
        os.unlink(tmp_path)
        if not text:
            raise RuntimeError("Empty transcription")
        return {"text": text}
    except Exception as e:
        print(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail="Failed to transcribe audio")

@app.post("/voice/ask", response_model=VoiceAskResponse, summary="Ask via audio and get TTS reply")
async def voice_ask(file: UploadFile = File(...), user_id: str | None = None):
    # 1) Transcribe
    tr = await transcribe_audio(file)
    query_text = tr.get("text") or ""
    if not query_text:
        raise HTTPException(status_code=400, detail="No speech detected")
    # 2) Route into existing pipeline (/ask logic) by calling ask_question internals
    req = AskRequest(user_id=user_id or "voice_user", query=query_text)
    answer_json = await ask_question(req)
    answer_text = answer_json.get("answer") or ""
    # 3) TTS (Indian voice)
    audio_bytes = await _tts_bytes_async(answer_text, voice='en-IN-NeerjaNeural')
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else None
    return VoiceAskResponse(answer=answer_text, audio_b64=audio_b64)

class TtsRequest(BaseModel):
    text: str
    language: str | None = None

@app.post("/tts", summary="Convert text to speech (Edge TTS en-IN)")
async def tts_endpoint(req: TtsRequest):
    if not req.text:
        raise HTTPException(status_code=400, detail="Missing text")
    # Use Indian voices; user can override voice via language mapping if needed
    voice = 'en-IN-NeerjaNeural' if (req.language or 'en').startswith('en') else 'hi-IN-SwaraNeural'
    audio_bytes = await _tts_bytes_async(req.text, voice=voice)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="TTS failed")
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return {"audio_b64": audio_b64}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Krishi Mitra Chatbot Server...")
    print("📱 Server will be available at: http://127.0.0.1:8000")
    print("🔧 API Documentation at: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
