# data_sources.py
import requests
import pgeocode
import re

# Initialize the geocoder for India.
geo_pincode = pgeocode.Nominatim('in')

def get_coords_for_location(location_query: str):
    """Gets latitude and longitude for an Indian pincode or city name."""
    # 1. Check for a 6-digit pincode first.
    pincode_match = re.search(r'\b\d{6}\b', location_query)
    if pincode_match:
        pincode = pincode_match.group(0)
        location_data = geo_pincode.query_postal_code(pincode)
        if not location_data.empty and 'latitude' in location_data and location_data.latitude > 0:
            return {"lat": location_data.latitude, "lon": location_data.longitude}

    # 2. If not a pincode, use the Open-Meteo geocoding API for city names.
    try:
        geo_api_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_query}&count=1&language=en&format=json"
        response = requests.get(geo_api_url, timeout=10)
        response.raise_for_status()
        geo_data = response.json()
        if geo_data.get("results"):
            first_result = geo_data["results"][0]
            # Ensure the result is within India.
            if first_result.get("country_code") == "IN":
                return {"lat": first_result["latitude"], "lon": first_result["longitude"]}
    except requests.exceptions.RequestException as e:
        print(f"API error when geocoding city: {e}")
    return None

def get_weather_forecast(location_query: str):
    """Fetches and formats a daily weather forecast with agricultural parameters."""
    coords = get_coords_for_location(location_query)
    if not coords:
        return f"Sorry, I couldn't find the location '{location_query}'. Please be more specific."

    # Request specific agricultural weather parameters.
    daily_params = [
        "temperature_2m_max", "temperature_2m_min", "relative_humidity_2m_mean",
        "precipitation_sum", "precipitation_probability_max", "windspeed_10m_max",
        "shortwave_radiation_sum", "et0_fao_evapotranspiration",
        "soil_temperature_0_to_7cm_mean", "soil_moisture_0_to_7cm_mean"
    ]
    api_url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&daily={','.join(daily_params)}&timezone=Asia/Kolkata"

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Format the data into a clean, readable string for the user.
        daily = data['daily']
        # We provide the forecast for tomorrow (index 1 in the API response).
        return (
            f"Agricultural Weather Forecast for {location_query} on {daily['time'][1]}:\n"
            f"- Air Temperature: Max {daily['temperature_2m_max'][1]}°C, Min {daily['temperature_2m_min'][1]}°C.\n"
            f"- Humidity: Average of {daily['relative_humidity_2m_mean'][1]}%.\n"
            f"- Precipitation: {daily['precipitation_sum'][1]}mm expected, with a {daily['precipitation_probability_max'][1]}% chance of rain.\n"
            f"- Soil Conditions: Average soil temperature (0-7cm) of {daily['soil_temperature_0_to_7cm_mean'][1]}°C. Average soil moisture of {daily['soil_moisture_0_to_7cm_mean'][1]} m³/m³.\n"
            f"- Wind Speed: Max of {daily['windspeed_10m_max'][1]} km/h.\n"
            f"- Sunlight: Total solar radiation of {daily['shortwave_radiation_sum'][1]} MJ/m².\n"
            f"- Water Loss (Evapotranspiration ET₀): {daily['et0_fao_evapotranspiration'][1]} mm."
        ).strip()
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"
