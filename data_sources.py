# data_sources.py
import requests
import pgeocode
import re
import os


# Initialize geocoders for India
geo_pincode = pgeocode.Nominatim('in')

from dotenv import load_dotenv


# Initialize the geocoder for India. It downloads data on first use.
geo_pincode = pgeocode.Nominatim('in')

def get_state_from_location(location_name: str):
    """
    Finds the state for a given Indian city or district name.
    """
    print(f"Looking up state for: {location_name}")
    # pgeocode's query_location is good for this
    location_info = geo_pincode.query_location(location_name)
    if not location_info.empty and 'state_name' in location_info:
        # It might return multiple matches, we'll take the first one
        state = location_info['state_name'].iloc[0]
        # Handle potential NaN values
        if isinstance(state, str):
            print(f"Found state: {state}")
            return state
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

def get_market_prices(district: str):
    """
    Fetches real-time commodity prices. It now automatically finds the state.
    """
    if not AGMARKNET_API_KEY:
        return "Error: AGMARKNET_API_KEY is not configured."

    # CHANGE: Dynamically find the state instead of hardcoding
    state = get_state_from_location(district)
    if not state:
        return f"Could not determine the state for '{district}' to fetch market prices."

    api_url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    
    params = {
        "api-key": AGMARKNET_API_KEY,
        "format": "json",
        "limit": "20",
        "filters[state]": state,
        "filters[district]": district
    }

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()

        if not data or 'records' not in data or not data['records']:
            return f"No recent market price data found for {district}, {state}."

        price_context = f"Recent commodity prices in {district}, {state}:\n"
        for record in data['records']:
            commodity = record.get('commodity', 'N/A')
            modal_price = record.get('modal_price', 'N/A')
            price_context += f"- {commodity}: Modal Price ₹{modal_price}/Quintal\n"
        
        return price_context.strip()

    except requests.exceptions.RequestException as e:
        return f"Error fetching market price data: {e}"
