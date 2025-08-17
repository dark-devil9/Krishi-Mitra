# main.py (Final Workflow Version with Contextual Chat Fix)
# Description: Implements a clear user workflow and a context-aware chat agent.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import uuid
from pydantic import BaseModel

import re
from rapidfuzz import fuzz


# --- Import Core Logic ---
try:
    from data_sources import get_weather_forecast, get_market_prices
    from qna import get_answer_from_books, generate_advisory_answer
    from ner_utils import extract_location_from_query
    from translator import detect_language, translate_text, transliterate_to_latin, is_latin_script
except ImportError as e:
    print(f"Error importing modules: {e}")
    exit()

# --- In-Memory Storage (for Hackathon) ---
user_profiles = {}
user_alerts = {}
onboarding_sessions = {}
from ner_utils import extract_location_from_query

def detect_intent_nlp(q: str):
    ql = q.lower().strip()
    # Weather patterns (cover colloquial forms)
    if re.search(r"\brain\b|\bweather\b|\bforecast\b|\btemp\b|\btemperature\b|\bhumidity\b|\bwind\b", ql):
        return "weather"
    # Market/price patterns including Hindi/colloquial cues
    if re.search(r"\bprice\b|\brate\b|\bmodal\b|\bmandi\b|\bms?p\b|\bbhav\b", ql):
        return "market"
    return "rag"

def extract_commodity_from_text(q: str):
    # generic “price of X” pattern; language-agnostic-ish
    m = re.search(r"(?:price|rate|bhav)\s+of\s+([a-z\s]+?)(?:\s+in\b|$)", q, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Try simple noun extraction fallback: last word before 'price' etc.
    m2 = re.search(r"([a-z\s]+)\s+(?:price|rate|bhav)\b", q, flags=re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None

# --- Proactive Alerting Logic ---
def check_for_personalized_alerts():
    print(f"\n--- Running scheduled alert check at {datetime.datetime.now()} ---")
    for user_id, profile in list(user_profiles.items()):
        location = profile.get("location")
        if not location or not profile.get("profileComplete"):
            continue

        print(f"Checking alerts for user {user_id} in {location}...")
        weather_context = get_weather_forecast(location)
        
        alert_prompt = f"Analyze this weather data for {location}. If there are risks like heavy rain, frost, or extreme heat, generate a concise ALERT and an actionable SUGGESTION, separated by '::'. Do not use any markdown formatting like asterisks. Otherwise, respond with 'No alert'.\n\nData:\n{weather_context}"
        
        response_text = generate_advisory_answer(alert_prompt)

        if "no alert" not in response_text.lower() and "::" in response_text:
            try:
                parts = response_text.split("::")
                alert_msg = parts[0].replace("ALERT", "").strip()
                suggestion_msg = parts[1].replace("SUGGESTION", "").strip()
                if user_id not in user_alerts: user_alerts[user_id] = []
                user_alerts[user_id].insert(0, {
                    "id": str(uuid.uuid4()), "alert": alert_msg, "suggestion": suggestion_msg,
                    "status": "new", "timestamp": datetime.datetime.now().isoformat()
                })
                print(f"SUCCESS: Alert generated for user {user_id}.")
            except Exception as e:
                print(f"Error parsing LLM response for user {user_id}: {e}")

# --- FastAPI App Lifecycle (for Scheduler) ---
scheduler = AsyncIOScheduler()
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(check_for_personalized_alerts, 'interval', hours=4)
    scheduler.start()
    yield
    scheduler.shutdown()

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
    place_mention = extract_location_from_query(query) or profile.get("location")

    intent = detect_intent_nlp(query)

    if intent == "weather":
        place = place_mention or "Jaipur"  # only as a last-resort default used universally
        return {"answer": get_weather_brief(place)}

    if intent == "market":
        place = place_mention or profile.get("location") or "Jaipur"
        comm_text = extract_commodity_from_text(query)
        return {"answer": get_market_prices_smart(place, AGMARKNET_API_KEY, comm_text)}

    # RAG fallback, still short
    if not user_id or user_id not in user_profiles:
        answer, _ = get_answer_from_books(f"Answer in <=2 sentences.\nQuestion: {query}")
        return {"answer": answer}

    contextual_prompt = f"""
Answer in <=2 sentences. If not in the documents, say exactly: Not available in my documents.
Profile:
- Location: {profile.get('location','N/A')}
- Land Size: {profile.get('land_size','N/A')}
- Budget: {profile.get('budget','N/A')}
- Age: {profile.get('age','N/A')}
- Gender: {profile.get('gender','N/A')}
- Current Crops: {profile.get('current_crops','N/A')}
Question: {query}
"""
    answer, _ = get_answer_from_books(contextual_prompt)
    return {"answer": answer}
