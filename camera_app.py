from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.camera import Camera
from kivy.core.window import Window
from kivy.clock import Clock  # for scheduling
from kivy.clock import mainthread
import cv2
import numpy as np  # for frame handling
import time
import threading

import os
import json
import logging
import requests  # For geolocation
from weather_service import WeatherService
from math import radians, cos, sin, asin, sqrt
from datetime import datetime

try:
    from android.storage import primary_external_storage_path
except ImportError:
    primary_external_storage_path = None

try:
    from plyer import storagepath
except ImportError:
    storagepath = None

# Import configuration parameters
from config import WEATHER_FETCH_INTERVAL, DISTANCE_THRESHOLD, VIDEO_CHUNK_DURATION

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class CameraApp(App):
    abc = "N/A"
    def build(self):
        Window.size = (800, 600)  # Set window size

        self.recording = False

        # Determining storage directory
        if primary_external_storage_path:
            #For Android-specific storage
            self.storage_path = primary_external_storage_path()
        elif storagepath:
            #For Desktop platforms (Documents folder)
            self.storage_path = storagepath.get_documents_dir()
        else:
            # Fallback to app-specific storage
            self.storage_path = App.get_running_app().user_data_dir
        self.camera = Camera(play=True)  # Use Kivy's Camera widget

        self.status_label = Label(text="Press Start to begin recording", size_hint=(1, 0.1))
        self.start_button = Button(text="Start Recording", size_hint=(1, 0.1), on_press=self.start_stop_recording)
        self.save_button = Button(text="Save Data", size_hint=(1, 0.1),
                                 on_press=self.save_json_file)


        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(self.camera)
        layout.add_widget(self.status_label)
        layout.add_widget(self.start_button)
        layout.add_widget(self.save_button)

        
    

        try:
            self.weather_service = WeatherService()
        except ValueError as ve:
            self.status_label.text = str(ve)
            self.start_button.disabled = True
            self.save_button.disabled = True  # Disable Save and Start buttons if WeatherService fails
            logger.error(ve)
            return layout

        # Path for video chunks
        self.video_directory = os.path.join("AutoVision", "videos")
        if not os.path.exists(self.video_directory):
            os.makedirs(self.video_directory)

        # Path for weather and video data
        self.data_file = os.path.join("AutoVision", "weather_videos.json")
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump([], f)

        # Initialize location and weather data
        self.latitude, self.longitude = self.get_geolocation()
        #if self.latitude is not None and self.longitude is not None:
        #    weather_data = self.weather_service.get_current_weather_by_coords(self.latitude, self.longitude)
        #    if weather_data:
        #        self.save_data(CameraApp.abc, weather_data)  # "N/A" for video_path since it's not linked to a video yet
        #        self.update_weather_labels(weather_data)
        #    else:
        #        self.update_status("Failed to fetch initial weather data.")
        #else:
        #    self.update_status("Failed to determine geolocation.")

        # Start the periodic weather data fetcher
        #self.weather_thread = threading.Thread(target=self.periodic_weather_fetcher, daemon=True)
        #self.weather_thread.start()
        self.stop_weather_fetching = True

        return layout

    def get_geolocation(self):
        """
        Fetches the current device's latitude and longitude using ip-api.com.
        Returns:
            tuple: (latitude, longitude) or (None, None) if failed.
        """
        try:
            response = requests.get("http://ip-api.com/json/")
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Geolocation API response: {data}")
            if data['status'] == 'success':
                latitude = data['lat']
                longitude = data['lon']
                logger.info(f"Geolocation determined: Latitude={latitude}, Longitude={longitude}")
                return latitude, longitude
            else:
                logger.error(f"Geolocation API failed: {data.get('message', 'No error message')}")
                return None, None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching geolocation: {e}")
            return None, None


    def start_stop_recording(self, instance):
        if not self.recording:
            self.start_button.text = "Stop Recording"
            self.status_label.text = "Recording..."
            self.recording = True

            # Start recording in a separate thread
            self.stop_weather_fetching = False
            threading.Thread(target=self.record_video, daemon=True).start()
            self.weather_thread = threading.Thread(target=self.periodic_weather_fetcher, daemon=True)
            self.weather_thread.start()
        else:
            self.start_button.text = "Start Recording"
            self.status_label.text = "Recording stopped"
            self.recording = False

            # Reset CameraApp.abc to "N/A" when recording stops
            #CameraApp.abc = "N/A"
            self.stop_weather_fetching = True

    def start_recording(self):
        # Initialize OpenCV VideoWriter
        self.recording_thread = threading.Thread(target=self.record_video, daemon=True)
        self.recording_thread.start()
        

    def save_data(self, video_path, weather_data):
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "video_path": video_path,
            "weather": {
                "city": weather_data.get("city", "N/A"),
                "temperature": weather_data.get("temperature", "N/A"),
                "temperature_min": weather_data.get("temperature_min", "N/A"),
                "temperature_max": weather_data.get("temperature_max", "N/A"),
                "feels_like": weather_data.get("feels_like", "N/A"),
                "pressure": weather_data.get("pressure", "N/A"),
                "humidity": weather_data.get("humidity", "N/A"),
                "visibility": weather_data.get("visibility", "N/A"),
                "clouds": weather_data.get("clouds", "N/A"),
                "wind_speed": weather_data.get("wind_speed", "N/A"),
                "wind_deg": weather_data.get("wind_deg", "N/A"),
                "weather_description": weather_data.get("weather_description", "N/A"),
                "weather_icon": weather_data.get("weather_icon", "N/A"),
                "sunrise": weather_data.get("sunrise", "N/A"),
                "sunset": weather_data.get("sunset", "N/A"),
                "rain": weather_data.get("rain", 0),
                "snow": weather_data.get("snow", 0)
            }
        }
        try:
            with open(self.data_file, 'r+') as f:
                data = json.load(f)
                data.append(record)
                f.seek(0)
                json.dump(data, f, indent=4)
            logger.info(f"Saved weather data for {video_path}")
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            self.update_status("Error saving data.")

    @mainthread
    def update_status(self, message):
        self.status_label.text = message
    
    @mainthread
    def capture_frame(self, out):
        # Getting frame data from Kivy's texture
        frame = self.camera.texture.pixels
        
        # Converting to a NumPy array
        frame = np.frombuffer(frame, np.uint8).reshape((self.camera.texture.height, self.camera.texture.width, 4))
        
        # Converting from RGBA to BGR (Since OpenCV uses BGR format)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

        # Writing the frame to the video file
        out.write(frame)

    def record_video(self):
        chunk_duration = VIDEO_CHUNK_DURATION  # Max duration of each video chunk in seconds
        chunk_count = 0
        fps = 10  # Target frames per second

        while self.recording:
            # Generate a unique file path for the current chunk
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.output_file = f"video_chunk_{chunk_count}_{timestamp}.mp4"
            self.filepath = os.path.join(self.video_directory, self.output_file)

            # Update CameraApp.abc to reflect the current file path
            CameraApp.abc = self.filepath

            # Initialize VideoWriter for the current chunk
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(self.filepath, fourcc, fps, (640, 480))

            logger.info(f"Started recording: {self.output_file}")
            self.update_status(f"Recording: {self.output_file}")

            start_time = time.time()
            frame_duration = 1 / fps  # Frame duration in seconds

            # Capture frames for the specified chunk duration
            while self.recording and (time.time() - start_time) < chunk_duration:
                frame_start_time = time.time()  # Start time for each frame
                self.capture_frame(out)

                # Calculate elapsed time for the frame
                elapsed = time.time() - frame_start_time
                remaining_time = frame_duration - elapsed

                # Wait for the remaining time to achieve the desired frame rate
                if remaining_time > 0:
                    time.sleep(remaining_time)

            # Release the VideoWriter for the current chunk
            out.release()
            logger.info(f"Saved chunk: {self.filepath}")
            self.update_status(f"Saved chunk: {self.output_file}")

            # Fetch and save weather data with the correct video_path
            weather_data = self.weather_service.get_current_weather_by_coords(self.latitude, self.longitude)
            if weather_data:
                self.save_data(self.filepath, weather_data)
          #      self.update_weather_labels(weather_data)
            else:
                logger.error("Failed to fetch weather data for this chunk.")
                self.update_status("Failed to fetch weather data.")

            chunk_count += 1  # Increment chunk count for the next chunk

        # To reset CameraApp.abc when recording stops
        CameraApp.abc = "N/A"
        # Clean up OpenCV resources
        cv2.destroyAllWindows()

    def periodic_weather_fetcher(self):
        """
        Periodically fetches and saves weather data every WEATHER_FETCH_INTERVAL seconds.
        Updates coordinates if the vehicle has moved significantly.
        """

        last_latitude, last_longitude = self.latitude, self.longitude
        distance_threshold = DISTANCE_THRESHOLD  # meters
        check_interval = WEATHER_FETCH_INTERVAL  # seconds

        while not self.stop_weather_fetching:
            time.sleep(check_interval)
            if self.stop_weather_fetching:
                break
            current_latitude, current_longitude = self.get_geolocation()

            if current_latitude is None or current_longitude is None:
                logger.error("Failed to fetch current geolocation.")
                continue

            distance_moved = self.haversine_distance(last_latitude, last_longitude,
                                                    current_latitude, current_longitude)

            logger.debug(f"Distance moved: {distance_moved:.2f} meters")

            if distance_moved >= distance_threshold:
                logger.info(f"Significant movement detected: {distance_moved:.2f} meters")
                self.latitude, self.longitude = current_latitude, current_longitude
                last_latitude, last_longitude = current_latitude, current_longitude
            else:
                logger.debug(f"Movement below threshold: {distance_moved:.2f} meters")

            # Fetch weather data based on current coordinates
            weather_data = self.weather_service.get_current_weather_by_coords(self.latitude, self.longitude)

            # Save weather data using the current CameraApp.abc
            if weather_data:
                self.save_data(CameraApp.abc, weather_data)
                #self.update_weather_labels(weather_data)
            else:
                logger.error("Failed to fetch weather data during periodic update.")
                self.update_status("Failed to fetch periodic weather data.")

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculates the Haversine distance between two points in meters.
        """
        # Convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # Haversine formula
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 

        r = 6371000  # Radius of Earth in meters
        return c * r

    def save_json_file(self, instance):
        """
        Archives the current weather_videos.json file with a timestamp and creates a new one.
        """
        try:
            if os.path.exists(self.data_file):
                # Create a timestamped backup filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"weather_videos_{timestamp}.json"
                backup_path = os.path.join("AutoVision", backup_filename)
                
                # Rename the current JSON file to the backup filename
                os.rename(self.data_file, backup_path)
                logger.info(f"Archived current JSON file as {backup_filename}")
                
                # Create a new empty JSON file
                with open(self.data_file, 'w') as f:
                    json.dump([], f)
                logger.info("Created a new weather_videos.json file.")
                
                # Update status label
                self.update_status(f"Archived data as {backup_filename} and created a new JSON file.")
            else:
                logger.warning(f"{self.data_file} does not exist. Creating a new one.")
                with open(self.data_file, 'w') as f:
                    json.dump([], f)
                logger.info("Created a new weather_videos.json file.")
                self.update_status("Created a new weather_videos.json file.")
        except Exception as e:
            logger.error(f"Error archiving JSON file: {e}")
            self.update_status("Error archiving JSON file.")

    def fetch_weather_data(self):
        # to manually fetch weather data based on geolocation
        if self.latitude is not None and self.longitude is not None:
            weather_data = self.weather_service.get_current_weather_by_coords(self.latitude, self.longitude)
            if weather_data:
                self.save_data(CameraApp.abc, weather_data)  # "N/A" for video_path since it's not linked to a video yet
                self.update_weather_labels(weather_data)
            else:
                logger.error("Failed to fetch weather data.")
                self.update_status("Failed to fetch weather data.")
        else:
            self.update_status("Geolocation not available.")

"""    @mainthread
    def update_weather_labels(self, data):
        # Update UI elements with weather data
        city = data.get('city', 'N/A')
        temperature = data.get('temperature', 'N/A')
        temperature_min = data.get('temperature_min', 'N/A')
        temperature_max = data.get('temperature_max', 'N/A')
        feels_like = data.get('feels_like', 'N/A')
        pressure = data.get('pressure', 'N/A')
        humidity = data.get('humidity', 'N/A')
        visibility = data.get('visibility', 'N/A')
        clouds = data.get('clouds', 'N/A')
        wind_speed = data.get('wind_speed', 'N/A')
        wind_deg = data.get('wind_deg', 'N/A')
        description = data.get('weather_description', 'N/A').capitalize()
        weather_icon = data.get('weather_icon', 'N/A')
        sunrise = data.get('sunrise', 'N/A')
        sunset = data.get('sunset', 'N/A')
        rain = data.get('rain', 0)
        snow = data.get('snow', 0) 

        # Update status label with current weather
        self.status_label.text = (
            f"City: {city} | "
            f"Temperature: {temperature}°C | "
            f"Min: {temperature_min}°C | "
            f"Max: {temperature_max}°C | "
            f"Feels Like: {feels_like}°C | "
            f"Pressure: {pressure} hPa | "
            f"Humidity: {humidity}% | "
            f"Visibility: {visibility} m | "
            f"Clouds: {clouds}% | "
            f"Wind: {wind_speed} m/s ({wind_deg}°) | "
            f"Rain: {rain} mm | "
            f"Snow: {snow} mm | "
            f"Weather: {description} | "
            f"Sunrise: {sunrise} | Sunset: {sunset}"
        )"""
    

if __name__ == '__main__':
    CameraApp().run()
