# main.py (Final Workflow Version)
# Description: Implements a clear user workflow: one-time onboarding chat, then a dashboard
# with personalized, proactive alerts and on-demand suggestions.

from fastapi import FastAPI, HTTPException
import uvicorn
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
import uuid

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

# --- Proactive Alerting Logic ---
def check_for_personalized_alerts():
    print(f"\n--- Running scheduled alert check at {datetime.datetime.now()} ---")
    for user_id, profile in user_profiles.items():
        location = profile.get("location")
        if not location:
            continue

        print(f"Checking alerts for user {user_id} in {location}...")
        weather_context = get_weather_forecast(location)
        
        alert_prompt = f"Analyze this weather data for {location}. If there are risks like heavy rain, frost, or extreme heat, generate a concise ALERT and an actionable SUGGESTION, separated by '::'. Otherwise, respond with 'No alert'.\n\nData:\n{weather_context}"
        
        response_text = generate_advisory_answer(alert_prompt)

        if "no alert" not in response_text.lower() and "::" in response_text:
            try:
                parts = response_text.split("::")
                alert_msg = parts[0].replace("ALERT", "").strip()
                suggestion_msg = parts[1].replace("SUGGESTION", "").strip()

                if user_id not in user_alerts:
                    user_alerts[user_id] = []
                
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
    version="3.1.0", # Final Workflow Version with full conversation
    lifespan=lifespan
)

# --- API Endpoints ---

@app.get("/status", summary="Check user's onboarding status")
async def get_user_status(user_id: str):
    if user_id in user_profiles and user_profiles[user_id].get("location"):
        return {"status": "profile_complete"}
    else:
        return {"status": "new_user"}

@app.post("/chat", summary="Handle the onboarding conversation")
async def onboarding_chat(user_id: str, message: str):
    """
    Manages the step-by-step conversation for new user onboarding.
    """
    if user_id not in onboarding_sessions:
        onboarding_sessions[user_id] = {"stage": "asking_location", "profile": {}}
    
    session = onboarding_sessions[user_id]
    stage = session["stage"]

    # --- CHANGE: Expanded the entire conversational flow ---
    if stage == "asking_location":
        session["stage"] = "asking_land_size"
        return {"response": "Welcome to Krishi Mitra! To get started, please tell me your location (city or district)."}
    
    elif stage == "asking_land_size":
        session["profile"]["location"] = message
        session["stage"] = "asking_budget"
        return {"response": f"Got it, you're in {message}. How many acres of land do you have? (e.g., '5 acres', 'NA')"}

    elif stage == "asking_budget":
        session["profile"]["land_size"] = message
        session["stage"] = "asking_age_gender"
        return {"response": "Understood. What is your approximate budget for this season? (e.g., '50000 rupees', 'NA', or 'looking for a loan')"}

    elif stage == "asking_age_gender":
        session["profile"]["budget"] = message
        session["stage"] = "asking_crops"
        return {"response": "Thanks. What is your age and gender? This helps find specific government schemes."}

    elif stage == "asking_crops":
        session["profile"]["age"] = ''.join(filter(str.isdigit, message))
        session["profile"]["gender"] = "female" if "female" in message.lower() else "male"
        session["stage"] = "generating_recommendation"
        return {"response": "Almost done. What are you currently growing, or have you not planned yet?"}

    elif stage == "generating_recommendation":
        session["profile"]["current_crops"] = message
        
        # Save the completed profile to our "permanent" storage
        user_profiles[user_id] = session["profile"]
        
        # Clean up the temporary session
        del onboarding_sessions[user_id]
        
        # Now generate the initial recommendation
        profile = user_profiles[user_id]
        user_profile_text = f"User Profile: Location: {profile['location']}, Land: {profile['land_size']}, Budget: {profile['budget']}, Age: {profile['age']}, Gender: {profile['gender']}, Current Situation: {profile['current_crops']}"
        market_data = get_market_prices(profile['location'])
        rag_context, _ = get_answer_from_books(f"schemes and subsidies for a {profile['gender']} farmer aged {profile['age']} in {profile['location']}")
        final_prompt = f"Based on the user's profile and data below, provide a personalized recommendation.\n\n{user_profile_text}\n\nLive Market Data:\n{market_data}\n\nRelevant Schemes:\n{rag_context}\n\nRecommendation:"
        final_answer = generate_advisory_answer(final_prompt)
        
        return {"response": f"Thank you! Your profile is complete. Here is an initial recommendation based on your details:\n\n{final_answer}"}

    return {"response": "I'm sorry, something went wrong during setup."}


@app.get("/get-suggestion", summary="Get a timely, on-demand suggestion")
async def get_suggestion(user_id: str):
    if user_id not in user_profiles:
        raise HTTPException(status_code=404, detail="User profile not found. Please complete the onboarding chat.")

    profile = user_profiles[user_id]
    weather_context = get_weather_forecast(profile['location'])
    
    suggestion_prompt = f"Based on this user's profile and the latest weather, provide one single, actionable suggestion.\n\nProfile:\n{profile}\n\nWeather:\n{weather_context}\n\nSuggestion:"
    
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
