# data_sources.py
import requests
import pgeocode
import re
import os

from datetime import datetime, timedelta
from functools import lru_cache
from rapidfuzz import process, fuzz


# Initialize geocoders for India
geo_pincode = pgeocode.Nominatim('in')

from dotenv import load_dotenv
import json
from qna import run_llm_json, run_llm_text


# Initialize the geocoder for India. It downloads data on first use.
geo_pincode = pgeocode.Nominatim('in')

def reverse_geocode(lat: float, lon: float):
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/reverse?latitude={lat}&longitude={lon}&language=en&format=json"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json()
        if js.get("results"):
            res = js["results"][0]
            district = res.get("admin2") or res.get("name")
            state = res.get("admin1")
            return {"district": district, "state": state}
    except requests.exceptions.RequestException:
        pass
    return {"district": None, "state": None}


def get_state_from_location(location_name: str):
    """
    Finds the state for a given Indian city, district, or pincode.
    Enhanced with better Indian location mapping and pincode handling.
    """
    print(f"Looking up state for: {location_name}")
    
    # Check if it's a pincode first (no hardcoded mapping)
    if re.match(r'^\d{6}$', location_name):
        pincode = location_name
        try:
            location_data = geo_pincode.query_postal_code(pincode)
            if not location_data.empty and 'state_name' in location_data:
                state = location_data['state_name'].iloc[0]
                if isinstance(state, str):
                    print(f"pgeocode found state for pincode: {state}")
                    return state
        except Exception as e:
            print(f"pgeocode error for pincode: {e}")
    
    # Try pgeocode for any named location (no hardcoded city/state tables)
    try:
        location_info = geo_pincode.query_location(location_name)
        if not location_info.empty and 'state_name' in location_info:
            state = location_info['state_name'].iloc[0]
            if isinstance(state, str):
                print(f"pgeocode found state: {state}")
                return state
    except Exception as e:
        print(f"pgeocode error: {e}")
    
    print(f"Could not determine state for {location_name}.")
    return None


def get_coords_for_location(location_query: str):
    """
    Gets latitude and longitude for an Indian location, which can be a 
    6-digit pincode or a city name.
    
    Returns: A dictionary {'lat': float, 'lon': float} or None if not found.
    """
    print(f"Attempting to find coordinates for: '{location_query}'")
    
    # --- Step 1: Check if it's a pincode ---
    pincode_match = re.search(r'\b\d{6}\b', location_query)
    if pincode_match:
        pincode = pincode_match.group(0)
        print(f"Detected pincode: {pincode}. Querying with pgeocode...")
        location_data = geo_pincode.query_postal_code(pincode)
        
        if not location_data.empty and 'latitude' in location_data and location_data.latitude > 0:
            lat = location_data.latitude
            lon = location_data.longitude
            print(f"Found coordinates for pincode {pincode}: Lat={lat}, Lon={lon}")
            return {"lat": lat, "lon": lon}

    # --- Step 2: If not a valid pincode, treat as a city name ---
    print(f"Could not find pincode, treating '{location_query}' as a city name. Querying Open-Meteo Geocoding API...")
    try:
        geo_api_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_query}&count=1&language=en&format=json"
        response = requests.get(geo_api_url)
        response.raise_for_status()
        geo_data = response.json()

        if "results" in geo_data and len(geo_data["results"]) > 0:
            first_result = geo_data["results"][0]
            if first_result.get("country_code") == "IN":
                lat = first_result["latitude"]
                lon = first_result["longitude"]
                print(f"Found coordinates for city '{location_query}': Lat={lat}, Lon={lon}")
                return {"lat": lat, "lon": lon}

    except requests.exceptions.RequestException as e:
        print(f"API error when geocoding city: {e}")
        return None
        
    print(f"Could not find coordinates for '{location_query}'.")
    return None

def get_weather_brief(location_query: str, prob_yes: int = 50, amt_yes_mm: float = 1.0):
    """
    Get a smart, actionable weather forecast for a location
    """
    print(f"Getting weather for: {location_query}")
    
    coords = get_coords_for_location(location_query)
    if not coords:
        return f"Sorry, I couldn't find the location '{location_query}'. Please try with a city name, district, or pincode."
    
    lat, lon = coords["lat"], coords["lon"]

    api = "https://api.open-meteo.com/v1/forecast"
    daily = "precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean,windspeed_10m_max"
    
    try:
        r = requests.get(f"{api}?latitude={lat}&longitude={lon}&daily={daily}&timezone=Asia/Kolkata", timeout=12)
        r.raise_for_status()
        d = r.json().get("daily", {})
        times = d.get("time", [])
        
        # choose tomorrow if present, else closest next
        idx = 1 if len(times) > 1 else 0

        pprob = d.get("precipitation_probability_max", [None])[idx]
        psum = d.get("precipitation_sum", [None])[idx]
        tmax = d.get("temperature_2m_max", [None])[idx]
        tmin = d.get("temperature_2m_min", [None])[idx]
        humidity = d.get("relative_humidity_2m_mean", [None])[idx]
        wind = d.get("windspeed_10m_max", [None])[idx]

        if pprob is None and psum is None and tmax is None and tmin is None:
            return f"Weather data unavailable for {location_query} right now. Please try again later."

        # Build a smart, actionable weather description
        weather_parts = []
        actions = []
        
        # Temperature
        if tmin is not None and tmax is not None:
            weather_parts.append(f"Temperature: {tmin}°C to {tmax}°C")
            
            # Smart temperature actions
            if tmax > 35:
                actions.append("🌡️ High heat alert: Avoid field work during peak hours (11 AM-3 PM)")
            elif tmin < 5:
                actions.append("❄️ Cold alert: Protect sensitive crops, delay early morning operations")
        
        # Rain probability
        if pprob is not None:
            if pprob >= 70:
                rain_desc = "High chance of rain"
                actions.append("🌧️ Rain likely: Delay field operations, protect harvested crops, check drainage")
            elif pprob >= 40:
                rain_desc = "Moderate chance of rain"
                actions.append("🌦️ Rain possible: Plan outdoor activities carefully, avoid spraying pesticides")
            else:
                rain_desc = "Low chance of rain"
            weather_parts.append(f"{rain_desc} ({pprob}%)")
        
        # Rain amount
        if psum is not None and psum > 0:
            weather_parts.append(f"Expected rainfall: {psum}mm")
            if psum > 20:
                actions.append("💧 Heavy rain expected: Postpone irrigation, check flood protection")
        
        # Humidity
        if humidity is not None:
            weather_parts.append(f"Humidity: {humidity}%")
            if humidity > 80:
                actions.append("💨 High humidity: Monitor for fungal diseases, avoid dense planting")
        
        # Wind
        if wind is not None:
            weather_parts.append(f"Wind speed: {wind} km/h")
            if wind > 25:
                actions.append("💨 Strong winds: Avoid spraying, protect young plants, delay harvesting")
        
        # Build final response
        response = f"🌤️ Weather forecast for {location_query}: {'; '.join(weather_parts)}."
        
        # Add smart actions if available
        if actions:
            response += "\n\n💡 Smart Actions:\n" + "\n".join(actions[:3])  # Limit to 3 actions
        
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"Weather API error: {e}")
        return f"Sorry, I couldn't fetch weather data for {location_query} right now. Please try again later."
    except Exception as e:
        print(f"Unexpected error in weather: {e}")
        return f"Weather data unavailable for {location_query} right now."

def get_state_and_district(location_query: str):
    # 1) Try pgeocode (pincode or name)
    state = get_state_from_location(location_query)  # may be None
    # 2) If we can geocode coords, try reverse for district/state
    coords = get_coords_for_location(location_query)
    if coords:
        rev = reverse_geocode(coords["lat"], coords["lon"])
        # prefer reverse_geocode if available
        state = rev["state"] or state
        district = rev["district"]
    else:
        district = None
    return {"state": state, "district": district}


def get_weather_forecast(location_query: str):
    """
    Fetches a comprehensive daily weather forecast with agricultural parameters
    and formats it as a context string for an LLM.
    """
    coords = get_coords_for_location(location_query)
    
    if not coords:
        return f"Sorry, I couldn't find the location '{location_query}'. Please be more specific."

    lat = coords["lat"]
    lon = coords["lon"]

    # CHANGE: Added specific agricultural parameters to the request.
    daily_params = [
        "temperature_2m_max", "temperature_2m_min", "relative_humidity_2m_mean",
        "precipitation_sum", "precipitation_probability_max",
        "windspeed_10m_max", "windgusts_10m_max",
        "shortwave_radiation_sum", "et0_fao_evapotranspiration",
        "soil_temperature_0_to_7cm_mean", "soil_moisture_0_to_7cm_mean"
    ]
    
    api_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily={','.join(daily_params)}&timezone=Asia/Kolkata"

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        # --- Format all the data into a clean, agricultural-focused context string ---
        daily_data = data['daily']
        
        # Extract data for tomorrow (index 1)
        forecast_date = daily_data['time'][1]
        max_temp = daily_data['temperature_2m_max'][1]
        min_temp = daily_data['temperature_2m_min'][1]
        humidity = daily_data['relative_humidity_2m_mean'][1]
        precip_total = daily_data['precipitation_sum'][1]
        precip_prob = daily_data['precipitation_probability_max'][1]
        wind_speed = daily_data['windspeed_10m_max'][1]
        solar_radiation = daily_data['shortwave_radiation_sum'][1]
        evapotranspiration = daily_data['et0_fao_evapotranspiration'][1]
        soil_temp = daily_data['soil_temperature_0_to_7cm_mean'][1]
        soil_moisture = daily_data['soil_moisture_0_to_7cm_mean'][1]

        # CHANGE: Build a more detailed, farmer-centric context string.
        context_string = f"""
        Agricultural Weather Forecast for {location_query} on {forecast_date}:
        - Air Temperature: Max {max_temp}°C, Min {min_temp}°C.
        - Humidity: The average relative humidity will be {humidity}%.
        - Precipitation: Total of {precip_total}mm expected, with a {precip_prob}% maximum probability of rain.
        - Soil Conditions: Average soil temperature at the top layer (0-7cm) will be {soil_temp}°C. Average soil moisture will be {soil_moisture} m³/m³.
        - Wind: Maximum speed of {wind_speed} km/h.
        - Sunlight: Total solar radiation will be {solar_radiation} MJ/m².
        - Water Loss: Estimated crop water loss (Evapotranspiration ET₀) will be {evapotranspiration} mm.
        """
        
        # This detailed context will be passed to the LLM.
        return context_string.strip()

    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"
    
load_dotenv()
AGMARKNET_API_KEY = os.getenv("AGMARKNET_API_KEY")

AGMARK_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
AGMARK_API = "https://api.data.gov.in/resource"

@lru_cache(maxsize=1)
def get_all_commodities(api_key: str):
    if not api_key:
        return []
    try:
        # Pull a page; many APIs support 'distinct' but data.gov.in does not for this dataset.
        # Strategy: fetch multiple pages and aggregate; keep it simple with one larger page.
        params = {"api-key": api_key, "format": "json", "limit": "500"}
        r = requests.get(f"{AGMARK_API}/{AGMARK_RESOURCE}", params=params, timeout=15)
        r.raise_for_status()
        recs = r.json().get("records", [])
        names = { (rec.get("commodity") or "").strip() for rec in recs if rec.get("commodity") }
        return sorted(n for n in names if n)
    except requests.exceptions.RequestException:
        return []

def fuzzy_match_commodity(text: str, choices: list[str], threshold: int = 85):
    if not text or not choices:
        return None
    cand = process.extractOne(text, choices, scorer=fuzz.WRatio)
    if cand and cand[1] >= threshold:
        return cand
    return None

def _parse_date(ddmmyyyy: str):
    try:
        return datetime.strptime(ddmmyyyy, "%d/%m/%Y")
    except Exception:
        return datetime.min

def get_market_prices_smart(*args, **kwargs):
    # Removed per new workflow; kept as shim if referenced elsewhere
    return "This endpoint has been replaced by the new Agmark QnA workflow."

def get_market_prices(*args, **kwargs):
    # Removed per new workflow; kept as shim if referenced elsewhere
    return "This endpoint has been replaced by the new Agmark QnA workflow."

# ---------- New helpers to support structured market workflows ----------

def _parse_quantity_from_query(query: str):
    """
    Extract quantity and unit from the user query.
    Returns a tuple (amount: float, unit: str) or None if not found.
    Supported units: kg, g, quintal/qtl/q, ton/tonne
    """
    try:
        pattern = r"(\d+(?:\.\d+)?)\s*(kg|kilograms?|g|grams?|quintals?|qtl|q|tons?|tonnes?)\b"
        m = re.search(pattern, query, flags=re.IGNORECASE)
        if not m:
            # also match like '1kg' without space
            pattern2 = r"(\d+(?:\.\d+)?)(kg|g|qtl|q|ton|tonne|tons|tonnes)\b"
            m = re.search(pattern2, query, flags=re.IGNORECASE)
        if m:
            amount = float(m.group(1))
            unit = m.group(2).lower()
            # Normalize unit names
            if unit in ["kilogram", "kilograms"]:
                unit = "kg"
            if unit in ["g", "gram", "grams"]:
                unit = "g"
            if unit in ["q", "qtl", "quintal", "quintals"]:
                unit = "quintal"
            if unit in ["ton", "tons", "tonne", "tonnes"]:
                unit = "tonne"
            return (amount, unit)
    except Exception:
        pass
    return None

def _price_per_unit_from_quintal(price_per_quintal: float, target_unit: str) -> float | None:
    """
    Convert price quoted per quintal to price per target_unit.
    Assumptions: 1 quintal = 100 kg = 100000 g; 1 tonne = 10 quintals.
    """
    try:
        if price_per_quintal is None:
            return None
        if target_unit == "kg":
            return price_per_quintal / 100.0
        if target_unit == "g":
            return price_per_quintal / 100000.0
        if target_unit == "quintal":
            return price_per_quintal
        if target_unit == "tonne":
            return price_per_quintal * 10.0
    except Exception:
        return None
    return None

def _format_currency(value: float) -> str:
    try:
        # round to nearest integer for simplicity like examples
        return f"₹{int(round(value))}"
    except Exception:
        return "₹N/A"

def _resolve_pincode_via_web(user_query: str) -> dict | None:
    """
    If the query contains a 6-digit pincode, resolve district/state via India Postal API
    and infer a nearest market from Agmark records for that district/state.
    Returns {pincode, district, state, nearest_market} or None.
    """
    m = re.search(r"\b(\d{6})\b", user_query)
    if not m:
        return None
    pincode = m.group(1)
    try:
        r = requests.get(f"https://api.postalpincode.in/pincode/{pincode}", timeout=10)
        r.raise_for_status()
        js = r.json()
        if not js or not isinstance(js, list) or not js[0].get("PostOffice"):
            return {"pincode": pincode, "district": None, "state": None, "nearest_market": None}
        po = js[0]["PostOffice"][0]
        district = po.get("District")
        state = po.get("State")
        nearest_market = None
        # Try to pick a market from Agmark records in that district/state
        filters = {}
        if state:
            filters["state"] = state
        recs = _query_agmark(filters, limit=200)
        if recs and district:
            district_lower = district.strip().lower()
            district_recs = [x for x in recs if (x.get("district") or "").strip().lower() == district_lower]
            if district_recs:
                # choose most recent market name
                district_recs.sort(key=lambda x: _parse_date(x.get("arrival_date", "01/01/1900")), reverse=True)
                nearest_market = (district_recs[0].get("market") or "").strip() or None
        return {"pincode": pincode, "district": district, "state": state, "nearest_market": nearest_market}
    except requests.exceptions.RequestException:
        return {"pincode": pincode, "district": None, "state": None, "nearest_market": None}

def _fetch_recent_records(api_key: str, state: str, recent_days: int = 14,
                          commodity_exact: str | None = None, district_hint: str | None = None) -> list[dict]:
    base_params = {
        "api-key": api_key,
        "format": "json",
        "limit": "500",
        "filters[state]": state,
    }
    if commodity_exact:
        base_params["filters[commodity]"] = commodity_exact
    try:
        r = requests.get(f"{AGMARK_API}/{AGMARK_RESOURCE}", params=base_params, timeout=18)
        r.raise_for_status()
        recs = r.json().get("records", [])
        if not recs:
            return []
        cutoff = datetime.now() - timedelta(days=recent_days)
        recs = [x for x in recs if _parse_date(x.get("arrival_date", "01/01/1900")) >= cutoff]
        if district_hint:
            prefer = [x for x in recs if (x.get("district") or "").strip().lower() == district_hint.strip().lower()]
            if prefer:
                recs = prefer
        # sort latest first
        recs.sort(key=lambda x: _parse_date(x.get("arrival_date", "01/01/1900")), reverse=True)
        return recs
    except requests.exceptions.RequestException:
        return []

def get_price_quote(place_text: str, api_key: str, commodity_text: str | None, raw_query: str,
                    recent_days: int = 14, fuzzy_thr: int = 85) -> str:
    """
    Implements the get_price workflow:
    - Parse: commodity, location, quantity
    - Fetch: Agmarknet for that commodity and location
    - Process: unit conversion (quintal -> kg, etc.) when quantity mentioned
    - Generate: grounded response using API data only
    """
    if not api_key:
        return "Market prices are currently unavailable due to API configuration issues."
    place_text = (place_text or "").strip()
    if not place_text or place_text == "N/A":
        return "Please provide a location (city, district, or pincode) to get market prices."

    loc = get_state_and_district(place_text)
    state = loc["state"]
    district_hint = loc["district"]
    if not state:
        return f"I couldn't determine the state for '{place_text}'. Please try with a more specific location or a pincode."

    # Fuzzy match commodity
    all_comms = get_all_commodities(api_key)
    comm_norm = None
    if commodity_text:
        cand = fuzzy_match_commodity(commodity_text, all_comms, threshold=fuzzy_thr)
        if cand:
            comm_norm = cand[0]

    qty = _parse_quantity_from_query(raw_query)

    recs = _fetch_recent_records(api_key, state, recent_days, commodity_exact=comm_norm, district_hint=district_hint)
    if not recs:
        return f"No recent market price data found for {state}. Please try a different location or check back later."

    # pick the most recent record
    rec = recs[0]
    market = (rec.get("market") or "N/A").strip()
    modal_price_qtl = None
    try:
        modal_price_qtl = float(rec.get("modal_price"))
    except Exception:
        pass

    if qty:
        amount, unit = qty
        per_unit = _price_per_unit_from_quintal(modal_price_qtl, "kg" if unit in ["kg", "g"] else unit)
        if per_unit is not None:
            if unit == "g":
                cost = per_unit * amount
                unit_str = "g"
            elif unit == "kg":
                cost = per_unit * amount
                unit_str = "kg"
            elif unit == "quintal":
                cost = per_unit * amount
                unit_str = "quintal"
            else:  # tonne
                cost = per_unit * amount
                unit_str = "tonne"
            # If amount is 1, phrase as per-unit price; else include total
            if amount == 1:
                if unit == "kg":
                    return f"1kg {comm_norm or (commodity_text or 'commodity')} in {district_hint or state} ({market}) is about {_format_currency(per_unit)}/kg."
                if unit == "quintal":
                    return f"1 quintal {comm_norm or (commodity_text or 'commodity')} in {district_hint or state} ({market}) is about {_format_currency(per_unit)}/quintal."
                if unit == "tonne":
                    return f"1 tonne {comm_norm or (commodity_text or 'commodity')} in {district_hint or state} ({market}) is about {_format_currency(per_unit)}/tonne."
                if unit == "g":
                    return f"1g {comm_norm or (commodity_text or 'commodity')} in {district_hint or state} ({market}) is about {_format_currency(per_unit)}/g."
            return f"Estimated cost for {amount}{unit_str} {comm_norm or (commodity_text or 'commodity')} in {district_hint or state} ({market}) is {_format_currency(cost)} (based on modal price)."

    # No quantity: report per quintal and per kg if possible
    if modal_price_qtl is None:
        return f"The latest price of {comm_norm or (commodity_text or 'commodity')} in {district_hint or state} at {market} is unavailable."
    per_kg = _price_per_unit_from_quintal(modal_price_qtl, "kg")
    return f"The price of {comm_norm or (commodity_text or 'commodity')} in {district_hint or state} ({market}) is {_format_currency(modal_price_qtl)} per quintal (~{_format_currency(per_kg)}/kg)."

def compare_market_prices(place_text: str, api_key: str, commodity_text: str | None, raw_query: str,
                          recent_days: int = 14, fuzzy_thr: int = 85) -> str:
    """
    Implements compare_prices workflow:
    - Fetch prices across markets for the commodity (within the state inferred from location)
    - Determine sell/buy intent; pick highest (sell) or lowest (buy) modal price
    - Normalize price per kg if quantity given
    """
    if not api_key:
        return "Market prices are currently unavailable due to API configuration issues."
    if not place_text:
        return "Please provide a location (city, district, or pincode) to compare market prices."

    loc = get_state_and_district(place_text)
    state = loc["state"]
    if not state:
        return f"I couldn't determine the state for '{place_text}'. Please try with a more specific location or a pincode."

    all_comms = get_all_commodities(api_key)
    comm_norm = None
    if commodity_text:
        cand = fuzzy_match_commodity(commodity_text, all_comms, threshold=fuzzy_thr)
        if cand:
            comm_norm = cand[0]

    recs = _fetch_recent_records(api_key, state, recent_days, commodity_exact=comm_norm)
    if not recs:
        return f"No recent market data available for {comm_norm or (commodity_text or 'the commodity')} in {state}."

    # Map latest price by market
    market_to_price_qtl: dict[str, float] = {}
    market_to_date: dict[str, datetime] = {}
    for r in recs:
        try:
            mkt = (r.get("market") or "").strip()
            dt = _parse_date(r.get("arrival_date", "01/01/1900"))
            price = float(r.get("modal_price"))
        except Exception:
                    continue
        if mkt and (mkt not in market_to_date or dt > market_to_date[mkt]):
            market_to_price_qtl[mkt] = price
            market_to_date[mkt] = dt

    if not market_to_price_qtl:
        return f"No recent prices found for {comm_norm or (commodity_text or 'the commodity')} in {state}."

    intent_goal = "sell" if ("sell" in raw_query.lower()) else ("buy" if ("buy" in raw_query.lower()) else "sell")

    best_market = None
    best_price = None
    for mkt, price in market_to_price_qtl.items():
        if best_price is None:
            best_market, best_price = mkt, price
        else:
            if intent_goal == "sell":
                if price > best_price:
                    best_market, best_price = mkt, price
            else:
                if price < best_price:
                    best_market, best_price = mkt, price

    qty = _parse_quantity_from_query(raw_query)
    if qty:
        amount, unit = qty
        per_unit = _price_per_unit_from_quintal(best_price, "kg" if unit in ["kg", "g"] else unit)
        if unit == "kg":
            price_str = f"{_format_currency(per_unit)}/kg"
        elif unit == "g":
            price_str = f"{_format_currency(per_unit)}/g"
        elif unit == "quintal":
            price_str = f"{_format_currency(per_unit)}/quintal"
        else:
            price_str = f"{_format_currency(per_unit)}/tonne"
        return f"The best place to {intent_goal} {amount}{unit} {comm_norm or (commodity_text or 'commodity')} is {best_market}, at {price_str}."

    # Default to per kg in message for readability
    per_kg = _price_per_unit_from_quintal(best_price, "kg") if best_price is not None else None
    if per_kg is None:
        return f"The best place to {intent_goal} {comm_norm or (commodity_text or 'commodity')} is {best_market}, at {_format_currency(best_price)}/quintal."
    return f"The best place to {intent_goal} {comm_norm or (commodity_text or 'commodity')} is {best_market}, at {_format_currency(per_kg)}/kg."

def get_price_trend(place_text: str, api_key: str, commodity_text: str | None,
                    days: int = 14, fuzzy_thr: int = 85) -> str:
    """
    Implements trend workflow:
    - Fetch historical data (last N days)
    - Compare earliest vs latest prices and report change direction
    """
    if not api_key:
        return "Market prices are currently unavailable due to API configuration issues."
    if not place_text:
        return "Please provide a location (city, district, or pincode) to analyze price trends."

    loc = get_state_and_district(place_text)
    state = loc["state"]
    district_hint = loc["district"]
    if not state:
        return f"I couldn't determine the state for '{place_text}'. Please try with a more specific location or a pincode."

    all_comms = get_all_commodities(api_key)
    comm_norm = None
    if commodity_text:
        cand = fuzzy_match_commodity(commodity_text, all_comms, threshold=fuzzy_thr)
        if cand:
            comm_norm = cand[0]

    recs = _fetch_recent_records(api_key, state, recent_days=days, commodity_exact=comm_norm, district_hint=district_hint)
    if not recs:
        return f"No recent price history found for {comm_norm or (commodity_text or 'the commodity')} in {district_hint or state}."

    # Keep only date and modal_price for the chosen commodity/location
    series = []
    for r in recs:
        try:
            dt = _parse_date(r.get("arrival_date", "01/01/1900"))
            price = float(r.get("modal_price"))
        except Exception:
            continue
        series.append((dt, price))
    if not series:
        return f"No recent price history found for {comm_norm or (commodity_text or 'the commodity')} in {district_hint or state}."

    series.sort(key=lambda x: x[0])
    start_dt, start_price = series[0]
    end_dt, end_price = series[-1]

    direction = "increased" if end_price > start_price else ("decreased" if end_price < start_price else "remained stable")
    if direction == "remained stable":
        return f"The price of {comm_norm or (commodity_text or 'the commodity')} in {district_hint or state} remained stable around {_format_currency(end_price)} per quintal over the last {days} days."
    return f"The price of {comm_norm or (commodity_text or 'the commodity')} in {district_hint or state} {direction} from {_format_currency(start_price)} to {_format_currency(end_price)} over the last {days} days."

# ================== New: Agmark QnA Router and Pipelines ==================

def _extract_offer_price(query: str):
    try:
        # capture patterns like 70, ₹70, 70/kg, ₹70 per kg, 2500/qtl
        offer_match = re.search(r"₹?\s*(\d+(?:\.\d+)?)\s*(?:/(kg|qtl|quintal)|\s*per\s*(kg|qtl|quintal))?", query, re.IGNORECASE)
        if offer_match:
            val = float(offer_match.group(1))
            unit = offer_match.group(2) or offer_match.group(3)
            if unit:
                unit = unit.lower()
                if unit in ["qtl", "quintal"]:
                    unit = "quintal"
                if unit == "kg":
                    unit = "kg"
            return {"price": val, "unit": unit or None}
    except Exception:
        pass
    return None

def _get_unit_for_dataset() -> str:
    # Agmark dataset prices are in ₹/Quintal
    return "quintal"

def _record_price_qtl(rec: dict) -> tuple[float | None, bool]:
    """Return (price_per_quintal, used_modal) using modal else avg(min,max) else min/max."""
    try:
        if rec.get("modal_price") not in (None, "", "N/A"):
            return float(rec.get("modal_price")), True
    except Exception:
        pass
    # average of min/max
    try:
        min_p = float(rec.get("min_price")) if rec.get("min_price") not in (None, "", "N/A") else None
        max_p = float(rec.get("max_price")) if rec.get("max_price") not in (None, "", "N/A") else None
        if min_p is not None and max_p is not None:
            return (min_p + max_p) / 2.0, False
        if min_p is not None:
            return min_p, False
        if max_p is not None:
            return max_p, False
    except Exception:
        pass
    return None, False

def _compute_confidence(days_old: int, modal_present: bool) -> str:
    if days_old <= 7 and modal_present:
        return "High"
    if days_old <= 14:
        return "Medium"
    return "Low (stale data)"

def _resolve_commodity_and_variety(raw_commodity: str | None) -> tuple[str | None, str | None]:
    if not raw_commodity:
        return None, None
    text = raw_commodity.strip().lower()
    variety = "Basmati" if "basmati" in text else None
    try:
        choices = get_all_commodities(AGMARKNET_API_KEY)
        cand = fuzzy_match_commodity(text, choices, threshold=80)
        if cand:
            return cand[0], variety
    except Exception:
        pass
    # fallback to title-cased input
    return raw_commodity.title(), variety

def _resolve_scope(location_raw: str | None) -> dict:
    # Return dict: {scope_type, scope_label, filters}
    if not location_raw:
        return {"scope_type": "national", "scope_label": "India", "filters": {}}
    loc = get_state_and_district(location_raw)
    state = loc.get("state")
    district = loc.get("district")
    if state and district:
        return {"scope_type": "district", "scope_label": f"{district}, {state}", "filters": {"state": state}}
    if state:
        return {"scope_type": "state", "scope_label": state, "filters": {"state": state}}
    # fallback to national if no resolution
    return {"scope_type": "national", "scope_label": location_raw, "filters": {}}

def _query_agmark(filters: dict, limit: int = 500, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    params = {"api-key": AGMARKNET_API_KEY, "format": "json", "limit": str(limit)}
    for k, v in filters.items():
        if v:
            params[f"filters[{k}]"] = v
    if from_date:
        params["filters[arrival_date]"] = from_date  # dataset doesn't support range directly; we'll filter post hoc
    try:
        r = requests.get(f"{AGMARK_API}/{AGMARK_RESOURCE}", params=params, timeout=18)
        r.raise_for_status()
        recs = r.json().get("records", [])
        # optional to_date filtering post fetch
        def in_range(rec):
            d = _parse_date(rec.get("arrival_date", "01/01/1900"))
            ok_from = True if not from_date else d >= _parse_date(datetime.strptime(from_date, "%Y-%m-%d").strftime("%d/%m/%Y"))
            ok_to = True if not to_date else d <= _parse_date(datetime.strptime(to_date, "%Y-%m-%d").strftime("%d/%m/%Y"))
            return ok_from and ok_to
        return [x for x in recs if in_range(x)]
    except requests.exceptions.RequestException:
        return []

def _select_top_by_recency_and_completeness(recs: list[dict], top_n: int = 3) -> list[dict]:
    def keyf(r):
        d = _parse_date(r.get("arrival_date", "01/01/1900"))
        complete = 1 if r.get("modal_price") not in (None, "", "N/A") else 0
        return (d, complete)
    return sorted(recs, key=keyf, reverse=True)[:top_n]

def _format_get_price_response(commodity_name: str, scope_label: str, price_qtl: float, used_modal: bool,
                               date_str: str, markets_used: list[str]) -> str:
    perkg = _price_per_unit_from_quintal(price_qtl, "kg") or 0.0
    days_old = (datetime.now() - _parse_date(date_str)).days if date_str else 999
    conf = _compute_confidence(days_old, used_modal)
    unit = _get_unit_for_dataset()
    primary = f"{commodity_name} price in {scope_label} is {_format_currency(price_qtl)}/{unit} (~{_format_currency(perkg)}/kg) on {date_str or 'N/A'}."
    note = f"Source: Agmarknet; markets: {', '.join(markets_used)}. {conf} confidence."
    return f"{primary} {note}"

def _format_ranked_list(market_to_price_kg: list[tuple[str, float]]) -> str:
    return ", ".join([f"{m} {_format_currency(p)}/kg" for m, p in market_to_price_kg])

def agmark_qna_answer(user_query: str, user_profile: dict | None = None) -> str:
    # Step 0: Resolve Pincode via web if present
    pin_info = _resolve_pincode_via_web(user_query)

    # Step 1: Extract Query Entities via LLM (no hardcoding), enriched with pincode info if present
    parser_system = (
        "You are an intelligent query parser for Agmarknet API. The user will ask questions about agricultural commodity prices.\n"
        "If a pincode resolution JSON is provided, enrich the location fields using it.\n"
        "Extract JSON fields: intent (get_price|best_sell_location), commodity, variety|null, location_type (market|district|state|national|null), location|null, quantity_value|null, quantity_unit (kg|quintal|null), date_or_range (YYYY-MM-DD|last_week|last_month|null).\n"
        "Normalize synonyms (e.g., paddy = rice). Do not guess; leave null if unsure."
    )
    enrich_str = f"\nPincode Resolution: {json.dumps(pin_info)}\n" if pin_info else ""
    parser_input = f"User Query: {user_query}{enrich_str}"
    parsed = run_llm_json(parser_system, parser_input) or {}
    intent = parsed.get("intent") or "get_price"
    raw_comm = parsed.get("commodity")
    variety = parsed.get("variety")
    location_type = parsed.get("location_type")
    location_raw = parsed.get("location")
    quantity_value = parsed.get("quantity_value")
    quantity_unit = parsed.get("quantity_unit")
    date_or_range = parsed.get("date_or_range")

    # Fallbacks from profile for location
    if not location_raw and user_profile:
        location_raw = user_profile.get("location")

    commodity_name, resolved_variety = _resolve_commodity_and_variety(raw_comm)
    if variety is None:
        variety = resolved_variety

    # Ask for clarification if ambiguous location and intent relies on scope
    if not location_raw and intent in ("get_price", "best_sell_location"):
        return "Please share your location (market/district/state) so I can fetch accurate prices."

    # Scope resolution (national allowed)
    scope = _resolve_scope(location_raw) if location_raw else {"scope_type": "national", "scope_label": "India", "filters": {}}

    # Pipelines
    if intent == "get_price":
        # Fetch: commodity and scope
        filters = {}
        if scope["filters"].get("state"):
            filters["state"] = scope["filters"]["state"]
        if commodity_name:
            filters["commodity"] = commodity_name
        recs = _query_agmark(filters)
        if not recs:
            return "No recent market price data available for the specified scope."
        # Filter recent <= 7 days preferred
        recs_sorted = sorted(recs, key=lambda r: _parse_date(r.get("arrival_date", "01/01/1900")), reverse=True)
        top = _select_top_by_recency_and_completeness(recs_sorted, top_n=3)
        # compute aggregate
        prices = []
        markets = []
        used_modal_flags = []
        dates = []
        for r in top:
            pq, used_modal = _record_price_qtl(r)
            if pq is not None:
                prices.append(pq)
                markets.append((r.get("market") or "N/A").strip())
                used_modal_flags.append(used_modal)
                dates.append(r.get("arrival_date", "N/A"))
        if not prices:
            return "No usable price data found in the latest records."
        # median price per qtl
        prices.sort()
        mid = prices[len(prices)//2]
        used_modal_any = any(used_modal_flags)
        date_latest = dates[0] if dates else None
        return _format_get_price_response(commodity_name or "commodity", scope["scope_label"], mid, used_modal_any, date_latest, markets)

    if intent in ("best_sell", "best_buy", "best_sell_location"):
        filters = {}
        if scope["filters"].get("state"):
            filters["state"] = scope["filters"]["state"]
        if commodity_name:
            filters["commodity"] = commodity_name
        recs = _query_agmark(filters)
        if not recs:
            return "No recent market price data available for the specified scope."
        # drop stale > 14 days
        cutoff = datetime.now() - timedelta(days=14)
        recs = [r for r in recs if _parse_date(r.get("arrival_date", "01/01/1900")) >= cutoff]
        # latest per market
        latest_by_market = {}
        for r in recs:
            mkt = (r.get("market") or "").strip()
            d = _parse_date(r.get("arrival_date", "01/01/1900"))
            if not mkt:
                continue
            if mkt not in latest_by_market or d > latest_by_market[mkt]["_d"]:
                latest_by_market[mkt] = {"rec": r, "_d": d}
        market_price_pairs = []
        for mkt, obj in latest_by_market.items():
            pq, _ = _record_price_qtl(obj["rec"])
            if pq is None:
                continue
            perkg = _price_per_unit_from_quintal(pq, "kg") or 0.0
            market_price_pairs.append((mkt, perkg, obj["_d"]))
        if not market_price_pairs:
            return "No usable price data found."
        reverse = True if intent == "best_sell" else False
        ranked = sorted(market_price_pairs, key=lambda x: (x[1], x[2]), reverse=reverse)[:3]
        ranked_list = _format_ranked_list([(m, p) for m, p, _ in ranked])
        latest_date = max([d for _, _, d in ranked]).strftime("%d/%m/%Y")
        conf = _compute_confidence((datetime.now() - max([d for _, _, d in ranked])).days, True)
        primary = ("Best places to SELL " if intent == "best_sell" else "Cheapest markets to BUY ") + f"{commodity_name or 'commodity'}: {ranked_list}. Latest date: {latest_date}. Units normalized to ₹/kg. Source: Agmarknet. {conf}."
        if quantity_value and quantity_unit == "kg":
            # compute total for top market
            top_mkt, top_price, _ = ranked[0]
            total = top_price * quantity_value
            primary += f" Estimated total for {quantity_value}kg at {top_mkt}: {_format_currency(total)}."
        return primary

    if intent == "trend":
        filters = {}
        if scope["filters"].get("state"):
            filters["state"] = scope["filters"]["state"]
        if commodity_name:
            filters["commodity"] = commodity_name
        # fetch last 14 days
        recs = _query_agmark(filters)
        if not recs:
            return "No recent market price data available for the specified scope."
        # keep records for commodity and scope, sort by date
        tuples = []
        for r in recs:
            pq, _ = _record_price_qtl(r)
            if pq is None:
                continue
            tuples.append((_parse_date(r.get("arrival_date", "01/01/1900")), pq))
        if not tuples:
            return "No usable price data to compute trend."
        tuples.sort(key=lambda x: x[0])
        start_dt, start_p = tuples[0]
        end_dt, end_p = tuples[-1]
        if start_p == 0:
            delta_pct = 0.0
        else:
            delta_pct = ((end_p - start_p) / start_p) * 100.0
        unit = _get_unit_for_dataset()
        return f"{commodity_name or 'Commodity'} in {scope['scope_label']} moved from {_format_currency(start_p)}/{unit} to {_format_currency(end_p)}/{unit} (Δ{round(delta_pct,1)}%) between {start_dt.strftime('%d/%m/%Y')} and {end_dt.strftime('%d/%m/%Y')}."

    if intent == "is_offer_good":
        offer = _extract_offer_price(user_query)
        if not offer:
            return "Please provide the offer price (e.g., ₹70/kg) to evaluate."
        offer_perkg = offer["price"] if offer.get("unit") == "kg" else (_price_per_unit_from_quintal(offer["price"], "kg") if offer.get("unit") == "quintal" else offer["price"])
        # Reference price: use scope median per kg today
        filters = {}
        if scope["filters"].get("state"):
            filters["state"] = scope["filters"]["state"]
        if commodity_name:
            filters["commodity"] = commodity_name
        recs = _query_agmark(filters)
        if not recs:
            return "No reference price found for comparison."
        perkg_list = []
        for r in recs:
            pq, _ = _record_price_qtl(r)
            if pq is None:
                continue
            perkg = _price_per_unit_from_quintal(pq, "kg") or 0.0
            perkg_list.append((perkg, r.get("arrival_date", "N/A")))
        if not perkg_list:
            return "No usable reference data to evaluate the offer."
        perkg_list.sort(key=lambda x: x[0])
        ref = perkg_list[len(perkg_list)//2]
        ref_price, ref_date = ref
        delta = offer_perkg - ref_price
        delta_pct = (delta / ref_price) * 100.0 if ref_price else 0.0
        if delta_pct >= 10:
            verdict = "good"
        elif delta_pct <= -10:
            verdict = "poor"
        else:
            verdict = "fair"
        # also compute top market today suggestion
        # group by market and take latest
        latest_by_market = {}
        for r in recs:
            mkt = (r.get("market") or "").strip()
            d = _parse_date(r.get("arrival_date", "01/01/1900"))
            pq, _ = _record_price_qtl(r)
            if pq is None or not mkt:
                continue
            if mkt not in latest_by_market or d > latest_by_market[mkt]["_d"]:
                latest_by_market[mkt] = {"_d": d, "perkg": _price_per_unit_from_quintal(pq, "kg") or 0.0}
        if latest_by_market:
            top_market = max(latest_by_market.items(), key=lambda kv: kv[1]["perkg"])  # top for selling
            top_market_str = f"{top_market[0]} at {_format_currency(top_market[1]['perkg'])}/kg"
        else:
            top_market_str = "N/A"
        return f"Your offer {_format_currency(offer_perkg)}/kg is {verdict} vs {scope['scope_label']} modal {_format_currency(ref_price)}/kg on {ref_date}. Top market today: {top_market_str}. Source: Agmarknet."

    # default safety
    return "Unable to process the request."