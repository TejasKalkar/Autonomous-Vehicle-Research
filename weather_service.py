# weather_service.py
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone
import logging

class WeatherService:
    def __init__(self):
        # Configure logger for this module
        self.logger = logging.getLogger(__name__)
        
        # Specify the absolute path to the API.env file
        dotenv_path = os.path.join(os.path.dirname(__file__), 'API.env')
        load_dotenv(dotenv_path=dotenv_path)
        
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        if not self.api_key:
            self.logger.error("API key not found. Please set OPENWEATHER_API_KEY in your API.env file.")
            raise ValueError("API key not found. Please set OPENWEATHER_API_KEY in your API.env file.")
        else:
            self.logger.debug("API key loaded successfully.")
        
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def get_current_weather_by_coords(self, latitude, longitude):
        """
        To fetch the current weather data for the specified latitude and longitude.
        Parameters:
            latitude (float): Latitude of the location.
            longitude (float): Longitude of the location.
        Returns:
            dict or None: A dictionary containing weather data or None if an error occurs.
        """
        params = {
            'lat': latitude,
            'lon': longitude,
            'appid': self.api_key,
            'units': 'metric'  # Options: 'standard', 'metric', 'imperial'
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()  # To raise HTTPError for bad responses (4XX or 5XX)
            data = response.json()
            
            # Log the complete API response for debugging
            self.logger.debug(f"Complete API response: {data}")

            # Extracting and formatting sunrise and sunset times
            sunrise_ts = data.get("sys", {}).get("sunrise")
            sunset_ts = data.get("sys", {}).get("sunset")
            
            if sunrise_ts:
                sunrise = datetime.fromtimestamp(sunrise_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            else:
                sunrise = "N/A"
                self.logger.warning("Sunrise timestamp not found in API response.")

            if sunset_ts:
                sunset = datetime.fromtimestamp(sunset_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            else:
                sunset = "N/A"
                self.logger.warning("Sunset timestamp not found in API response.")
            
            weather = {
                "city": data.get("name"),
                "temperature": data.get("main", {}).get("temp"),
                "temperature_min": data.get("main", {}).get("temp_min"),
                "temperature_max": data.get("main", {}).get("temp_max"),
                "feels_like": data.get("main", {}).get("feels_like"),
                "pressure": data.get("main", {}).get("pressure"),
                "humidity": data.get("main", {}).get("humidity"),
                "visibility": data.get("visibility"),
                "clouds": data.get("clouds", {}).get("all"),
                "wind_speed": data.get("wind", {}).get("speed"),
                "wind_deg": data.get("wind", {}).get("deg"),
                "weather_description": data.get("weather", [{}])[0].get("description"),
                "weather_icon": data.get("weather", [{}])[0].get("icon"),
                "sunrise": sunrise,
                "sunset": sunset,
                "rain": data.get("rain", {}).get("1h", 0),  # mm of rain in last 1 hour
                "snow": data.get("snow", {}).get("1h", 0)   # mm of snow in last 1 hour
            }

            self.logger.debug(f"Extracted weather data: {weather}")
            return weather
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"HTTP error occurred: {http_err}")  # e.g., 401 Client Error
        except Exception as err:
            self.logger.error(f"An error occurred: {err}")
        return None
