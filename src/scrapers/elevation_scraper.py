import os
import sys
import json
import logging
import argparse
import requests
import h3
import pymongo
import psycopg2
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

class ElevationScraper:
    def __init__(self, config_path="config/settings.conf"):
        self.config_path = config_path
        self.postgres_conn = None
        self.mongo_client = None
        self.mongo_db = None
        
        # Load Config
        self.load_config()
        # Setup connections
        self.init_connections()

    def load_config(self):
        # Prefer environment variables (no hardcoding), fallback to config file
        self.pg_host = os.getenv("POSTGRES_HOST")
        self.pg_port = os.getenv("POSTGRES_PORT")
        self.pg_db = os.getenv("POSTGRES_DB")
        self.pg_user = os.getenv("POSTGRES_USER")
        self.pg_pass = os.getenv("POSTGRES_PASSWORD")
        
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.mongo_dbname = os.getenv("MONGODB_DB")

        # Fallback to config file if env vars are missing
        config = ConfigParser()
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            if not self.pg_host: self.pg_host = config.get("DATABASE", "POSTGRES_HOST", fallback="localhost")
            if not self.pg_port: self.pg_port = config.get("DATABASE", "POSTGRES_PORT", fallback="5432")
            if not self.pg_db: self.pg_db = config.get("DATABASE", "POSTGRES_DB", fallback="urbanlens_ai")
            if not self.pg_user: self.pg_user = config.get("DATABASE", "POSTGRES_USER", fallback="postgres")
            if not self.pg_pass: self.pg_pass = config.get("DATABASE", "POSTGRES_PASSWORD", fallback="password")
            if not self.mongo_uri: self.mongo_uri = config.get("DATABASE", "MONGODB_URI", fallback="mongodb://localhost:27017/")
            if not self.mongo_dbname: self.mongo_dbname = config.get("DATABASE", "MONGODB_DB", fallback="urbanlens_ai")
        else:
            if not self.pg_host: self.pg_host = "localhost"
            if not self.pg_port: self.pg_port = "5432"
            if not self.pg_db: self.pg_db = "urbanlens_ai"
            if not self.pg_user: self.pg_user = "postgres"
            if not self.pg_pass: self.pg_pass = "password"
            if not self.mongo_uri: self.mongo_uri = "mongodb://localhost:27017/"
            if not self.mongo_dbname: self.mongo_dbname = "urbanlens_ai"

    def init_connections(self):
        try:
            self.mongo_client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2000)
            self.mongo_client.admin.command('ping')
            self.mongo_db = self.mongo_client[self.mongo_dbname]
            logger.info("[OK] Connected to MongoDB in ElevationScraper.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to MongoDB in ElevationScraper: {e}")
            self.mongo_db = None

        try:
            self.postgres_conn = psycopg2.connect(
                host=self.pg_host,
                port=self.pg_port,
                dbname=self.pg_db,
                user=self.pg_user,
                password=self.pg_pass
            )
            self.postgres_conn.autocommit = True
            logger.info("[OK] Connected to PostgreSQL in ElevationScraper.")
        except Exception as e:
            logger.warning(f"[WARNING] PostgreSQL connection failed in ElevationScraper: {e}.")
            self.postgres_conn = None

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

    def get_elevation(self, lat: float, lon: float) -> float:
        """Call the free public Open-Elevation API"""
        url = "https://api.open-elevation.com/api/v1/lookup"
        payload = {
            "locations": [
                {"latitude": lat, "longitude": lon}
            ]
        }
        headers = {"User-Agent": "UrbanLensAI/1.0"}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    elevation = results[0].get("elevation", 0.0)
                    logger.info(f"Retrieved elevation: {elevation} meters for ({lat}, {lon})")
                    return float(elevation)
            logger.warning(f"Elevation API returned status {response.status_code}. Using fallback of 5.0m.")
            return 5.0
        except Exception as e:
            logger.error(f"Error querying Elevation API: {e}. Using fallback.")
            return 5.0

    def ensure_h3_grid_exists(self, cursor, h3_index: str, city_id: str):
        cursor.execute("SELECT 1 FROM urban_grids WHERE h3_index = %s", (h3_index,))
        if cursor.fetchone() is None:
            boundary = h3.cell_to_boundary(h3_index)
            coords = [(lon, lat) for lat, lon in boundary]
            coords.append(coords[0])
            wkt_polygon = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in coords)}))"
            try:
                cursor.execute("""
                    INSERT INTO urban_grids (h3_index, city_id, boundary, overall_score, data_completeness)
                    VALUES (%s, %s, ST_GeomFromText(%s, 4326), 0.0, 0.0)
                """, (h3_index, city_id, wkt_polygon))
            except Exception as e:
                logger.error(f"Failed to insert H3 cell: {e}")

    def scrape(self, city_name: str):
        lat, lon = self.fetch_city_coordinates(city_name)
        h3_index = h3.latlng_to_cell(lat, lon, 8)
        
        # Get elevation and score
        elevation = self.get_elevation(lat, lon)
        # Resilient elevation score (higher is safer from flood, capped at 30m)
        score = min(1.0, max(0.0, elevation / 30.0))
        
        scraped_at = datetime.utcnow()
        doc = {
            "h3_index": h3_index,
            "city": city_name,
            "coordinates": {"lat": lat, "lon": lon},
            "elevation_meters": elevation,
            "score": round(score, 2),
            "timestamp": scraped_at
        }
        
        # Save to MongoDB
        if self.mongo_db is not None:
            try:
                collection = self.mongo_db["climate_resilience_logs"]
                collection.delete_many({"h3_index": h3_index})
                collection.insert_one(doc)
                logger.info(f"[OK] Saved elevation logs to MongoDB for {h3_index}.")
            except Exception as e:
                logger.error(f"Failed to save to MongoDB: {e}")

        # Save to Postgres
        if self.postgres_conn is not None:
            try:
                cursor = self.postgres_conn.cursor()
                self.ensure_h3_grid_exists(cursor, h3_index, city_name)
                cursor.execute("""
                    INSERT INTO factor_scores (h3_index, factor_name, sub_factor_name, score, confidence, data_source)
                    VALUES (%s, 'environment', 'climate_resilience', %s, 0.85, 'elevation_scraper')
                    ON CONFLICT (h3_index, factor_name, sub_factor_name)
                    DO UPDATE SET score = EXCLUDED.score, last_updated = NOW()
                """, (h3_index, score))
                logger.info(f"[OK] Ingested environment/climate_resilience score: {score} into PostgreSQL.")
            except Exception as e:
                logger.error(f"Failed to save to PostgreSQL: {e}")

        # Backup File
        output_dir = "data/ingested"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"elevation_{city_name.lower().replace(' ', '_')}.json")
        try:
            serializable_doc = doc.copy()
            if "_id" in serializable_doc:
                serializable_doc["_id"] = str(serializable_doc["_id"])
            serializable_doc["timestamp"] = scraped_at.isoformat()
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(serializable_doc, f, indent=2)
            logger.info(f"[OK] Exported JSON backup file: {output_path}")
        except Exception as e:
            logger.error(f"Failed to write JSON backup file: {e}")

    def close(self):
        if self.mongo_client:
            self.mongo_client.close()
        if self.postgres_conn:
            self.postgres_conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UrbanLens AI: Climate & Elevation Scraper")
    parser.add_argument("--city", type=str, default="Chennai", help="Name of the city")
    args = parser.parse_args()

    scraper = ElevationScraper()
    try:
        scraper.scrape(args.city)
    finally:
        scraper.close()
