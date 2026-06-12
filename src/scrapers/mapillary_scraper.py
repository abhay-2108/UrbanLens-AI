import os
import sys
import json
import logging
import argparse
import requests
import h3
import pymongo
from configparser import ConfigParser
from datetime import datetime

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class MapillaryScraper:
    def __init__(self, config_path="config/settings.conf"):
        self.config_path = config_path
        self.mongo_client = None
        self.mongo_db = None
        
        # Load Config
        self.load_config()
        # Setup connection
        self.init_connection()

    def load_config(self):
        # Read from environment, fallback to settings.conf
        self.token = os.getenv("MAPILLARY_CLIENT_TOKEN")
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.mongo_dbname = os.getenv("MONGODB_DB")

        config = ConfigParser()
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            if not self.token: self.token = config.get("APIS", "MAPILLARY_TOKEN", fallback="")
            if not self.mongo_uri: self.mongo_uri = config.get("DATABASE", "MONGODB_URI", fallback="mongodb://localhost:27017/")
            if not self.mongo_dbname: self.mongo_dbname = config.get("DATABASE", "MONGODB_DB", fallback="urbanlens_ai")
        else:
            if not self.token: self.token = ""
            if not self.mongo_uri: self.mongo_uri = "mongodb://localhost:27017/"
            if not self.mongo_dbname: self.mongo_dbname = "urbanlens_ai"

    def init_connection(self):
        try:
            self.mongo_client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2000)
            self.mongo_client.admin.command('ping')
            self.mongo_db = self.mongo_client[self.mongo_dbname]
            logger.info("[OK] Connected to MongoDB in MapillaryScraper.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to MongoDB in MapillaryScraper: {e}")
            self.mongo_db = None

    def fetch_city_coordinates(self, city_name: str) -> tuple:
        cities = {
            "chennai": (13.0827, 80.2707),
            "bangalore": (12.9716, 77.5946),
            "bengaluru": (12.9716, 77.5946),
            "mumbai": (19.0760, 72.8777),
            "delhi": (28.6139, 77.2090),
            "san francisco": (37.7749, -122.4194),
        }
        key = city_name.lower().strip()
        return cities.get(key, (13.0827, 80.2707))

    def create_mock_street_image(self, filepath: str):
        """Creates a simple colored PNG image to act as a fallback image for testing models"""
        try:
            # We can use Pillow to generate a synthetic landscape/street view image
            from PIL import Image, ImageDraw
            # 640x640 green grass + blue sky + asphalt road to test YOLO and DeepLabV3!
            img = Image.new('RGB', (640, 640), color = (135, 206, 235)) # Blue Sky
            draw = ImageDraw.Draw(img)
            # Draw green park canopy/bushes on sides
            draw.rectangle([0, 300, 640, 640], fill=(34, 139, 34)) # Grass/Trees
            # Draw road in center
            draw.polygon([(200, 640), (440, 640), (320, 350)], fill=(105, 105, 105)) # Grey Road
            # Draw sidewalk
            draw.polygon([(170, 640), (200, 640), (320, 350)], fill=(211, 211, 211)) # Left Sidewalk
            img.save(filepath)
            logger.info(f"[OK] Generated synthetic placeholder street image: {filepath}")
        except Exception as e:
            logger.error(f"Failed to generate mock image: {e}")

    def fetch_mapillary_images(self, h3_index: str, output_dir="data/sample_images", max_images=2) -> list:
        """Fetch images inside the H3 index bounding box"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Calculate cell bounding box
        boundary = h3.cell_to_boundary(h3_index)
        lats = [pt[0] for pt in boundary]
        lons = [pt[1] for pt in boundary]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        saved_paths = []

        if not self.token or self.token == "your_mapillary_client_token_here":
            logger.warning("[WARNING] Mapillary token missing or default. Using mock fallback street image.")
            mock_path = os.path.join(output_dir, f"mock_street_{h3_index}.png")
            self.create_mock_street_image(mock_path)
            return [mock_path]

        # Query Mapillary API v4
        # bbox parameter order: min_lon,min_lat,max_lon,max_lat
        url = "https://graph.mapillary.com/images"
        params = {
            "access_token": self.token,
            "fields": "id,geometry",
            "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
            "limit": max_images
        }
        
        try:
            response = requests.get(url, params=params, timeout=20)
            if response.status_code == 200:
                images = response.json().get("data", [])
                logger.info(f"Found {len(images)} street-level images in Mapillary for H3 {h3_index}.")
                
                for idx, img in enumerate(images):
                    img_id = img["id"]
                    # Fetch thumbnail url
                    thumb_url = f"https://graph.mapillary.com/{img_id}"
                    thumb_params = {
                        "access_token": self.token,
                        "fields": "thumb_1024_url"
                    }
                    thumb_resp = requests.get(thumb_url, params=thumb_params, timeout=15)
                    if thumb_resp.status_code == 200:
                        thumb_data = thumb_resp.json()
                        download_url = thumb_data.get("thumb_1024_url")
                        
                        if download_url:
                            # Download image
                            img_data = requests.get(download_url, timeout=15).content
                            filename = f"mapillary_{h3_index}_{img_id}.jpg"
                            filepath = os.path.join(output_dir, filename)
                            with open(filepath, "wb") as f:
                                f.write(img_data)
                            logger.info(f"[OK] Downloaded Mapillary image: {filepath}")
                            saved_paths.append(filepath)
                            
            else:
                logger.error(f"Mapillary API returned status code {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error calling Mapillary API: {e}")

        # Fallback if no images found or query failed
        if not saved_paths:
            logger.warning("No images downloaded. Falling back to mock street imagery.")
            mock_path = os.path.join(output_dir, f"mock_street_{h3_index}.png")
            self.create_mock_street_image(mock_path)
            saved_paths.append(mock_path)

        return saved_paths

    def scrape(self, city_name: str) -> list:
        logger.info(f"Running Mapillary crawler for {city_name}...")
        lat, lon = self.fetch_city_coordinates(city_name)
        h3_index = h3.latlng_to_cell(lat, lon, 8)
        
        image_paths = self.fetch_mapillary_images(h3_index)
        
        # Ingest metadata into MongoDB log
        if self.mongo_db is not None:
            try:
                collection = self.mongo_db["cv_processing_logs"]
                collection.delete_many({"h3_index": h3_index, "processing_stage": "downloaded"})
                
                log_doc = {
                    "h3_index": h3_index,
                    "city": city_name,
                    "image_paths": image_paths,
                    "processing_stage": "downloaded",
                    "timestamp": datetime.utcnow()
                }
                collection.insert_one(log_doc)
                logger.info(f"[OK] Saved image metadata to MongoDB cv_processing_logs.")
            except Exception as e:
                logger.error(f"Failed to log metadata to MongoDB: {e}")
                
        return image_paths

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UrbanLens AI: Mapillary Image Scraper")
    parser.add_argument("--city", type=str, default="Chennai", help="Name of the city")
    args = parser.parse_args()

    scraper = MapillaryScraper()
    scraper.scrape(args.city)
