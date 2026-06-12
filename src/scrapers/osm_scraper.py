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

class OSMScraper:
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
        config = ConfigParser()
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            self.pg_host = config.get("DATABASE", "POSTGRES_HOST", fallback="localhost")
            self.pg_port = config.get("DATABASE", "POSTGRES_PORT", fallback="5432")
            self.pg_db = config.get("DATABASE", "POSTGRES_DB", fallback="urbanlens_ai")
            self.pg_user = config.get("DATABASE", "POSTGRES_USER", fallback="postgres")
            self.pg_pass = config.get("DATABASE", "POSTGRES_PASSWORD", fallback="password")
            
            self.mongo_uri = config.get("DATABASE", "MONGODB_URI", fallback="mongodb://localhost:27017/")
            self.mongo_dbname = config.get("DATABASE", "MONGODB_DB", fallback="urbanlens_ai")
        else:
            logger.warning(f"Config file not found at {self.config_path}. Using default settings.")
            self.pg_host = "localhost"
            self.pg_port = "5432"
            self.pg_db = "urbanlens_ai"
            self.pg_user = "postgres"
            self.pg_pass = "password"
            self.mongo_uri = "mongodb://localhost:27017/"
            self.mongo_dbname = "urbanlens_ai"

    def init_connections(self):
        # Connect to MongoDB
        try:
            self.mongo_client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2000)
            # Try a ping to verify connection
            self.mongo_client.admin.command('ping')
            self.mongo_db = self.mongo_client[self.mongo_dbname]
            logger.info("[OK] Connected to MongoDB successfully.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to MongoDB: {e}")
            self.mongo_db = None

        # Connect to PostgreSQL
        try:
            self.postgres_conn = psycopg2.connect(
                host=self.pg_host,
                port=self.pg_port,
                dbname=self.pg_db,
                user=self.pg_user,
                password=self.pg_pass
            )
            self.postgres_conn.autocommit = True
            logger.info("[OK] Connected to PostgreSQL successfully.")
        except Exception as e:
            logger.warning(f"[WARNING] PostgreSQL connection failed: {e}. Running in MongoDB/File fallback mode.")
            self.postgres_conn = None

    def query_overpass(self, city_name: str) -> dict:
        """Fetch amenities for a city from Overpass API"""
        logger.info(f"Querying Overpass API for city: {city_name}...")
        
        # Overpass query to find amenities, leisure points, and shops
        overpass_query = f"""
        [out:json][timeout:90];
        area[name="{city_name}"]->.searchArea;
        (
          node["amenity"~"hospital|clinic|pharmacy|restaurant|cafe|fast_food|marketplace|supermarket|bus_station|subway_entrance|police|fire_station|gym|school"](area.searchArea);
          node["leisure"~"park|playground|sports_centre|fitness_centre"](area.searchArea);
          node["shop"~"supermarket|mall|convenience"](area.searchArea);
          way["amenity"~"hospital|clinic|pharmacy|restaurant|cafe|fast_food|marketplace|supermarket|bus_station|subway_entrance|police|fire_station|gym|school"](area.searchArea);
          way["leisure"~"park|playground|sports_centre|fitness_centre"](area.searchArea);
          way["shop"~"supermarket|mall|convenience"](area.searchArea);
        );
        out center;
        """
        
        overpass_url = "https://overpass-api.de/api/interpreter"
        headers = {
            "User-Agent": "UrbanLensAI/1.0 (contact: support@urbanlens.ai)"
        }
        try:
            response = requests.post(overpass_url, data={'data': overpass_query}, headers=headers, timeout=120)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully retrieved {len(data.get('elements', []))} features from OSM.")
                return data
            else:
                logger.error(f"Overpass API returned status code {response.status_code}: {response.text}")
                return {}
        except Exception as e:
            logger.error(f"Error querying Overpass API: {e}")
            return {}

    def ensure_h3_grid_exists(self, cursor, h3_index: str, city_id: str):
        """Helper to ensure H3 cell exists in urban_grids to prevent foreign key errors"""
        cursor.execute("SELECT 1 FROM urban_grids WHERE h3_index = %s", (h3_index,))
        if cursor.fetchone() is None:
            # Generate WKT boundary polygon
            boundary = h3.cell_to_boundary(h3_index)
            # convert from (lat, lon) to (lon, lat) and repeat first point to close
            coords = [(lon, lat) for lat, lon in boundary]
            coords.append(coords[0])
            wkt_polygon = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in coords)}))"
            
            try:
                cursor.execute("""
                    INSERT INTO urban_grids (h3_index, city_id, boundary, overall_score, data_completeness)
                    VALUES (%s, %s, ST_GeomFromText(%s, 4326), 0.0, 0.0)
                """, (h3_index, city_id, wkt_polygon))
                logger.debug(f"Inserted placeholder H3 grid cell: {h3_index}")
            except Exception as e:
                logger.error(f"Failed to insert H3 cell {h3_index}: {e}")

    def scrape(self, city_name: str, export_geojson=True):
        data = self.query_overpass(city_name)
        elements = data.get("elements", [])
        if not elements:
            logger.warning("No data retrieved from Overpass API.")
            return

        mongo_docs = []
        pg_rows = []
        geojson_features = []
        
        scraped_at = datetime.utcnow()

        logger.info("Processing retrieved elements...")
        for elem in elements:
            # Extract coordinates (node has lat/lon, way has center)
            lat = elem.get("lat") or (elem.get("center", {}).get("lat") if "center" in elem else None)
            lon = elem.get("lon") or (elem.get("center", {}).get("lon") if "center" in elem else None)
            
            if lat is None or lon is None:
                continue

            # Calculate H3 index (Resolution 8)
            try:
                h3_index = h3.latlng_to_cell(lat, lon, 8)
            except Exception:
                continue

            tags = elem.get("tags", {})
            name = tags.get("name", "Unnamed")
            
            # Determine category and subcategory
            category = "unknown"
            subcategory = "unknown"
            
            if "amenity" in tags:
                category = tags["amenity"]
                subcategory = "amenity"
            elif "leisure" in tags:
                category = tags["leisure"]
                subcategory = "leisure"
            elif "shop" in tags:
                category = tags["shop"]
                subcategory = "shop"

            osm_id = str(elem.get("id"))

            # Form document for MongoDB
            mongo_doc = {
                "osm_id": osm_id,
                "category": category,
                "subcategory": subcategory,
                "name": name,
                "lat": float(lat),
                "lon": float(lon),
                "h3_index": h3_index,
                "opening_hours": tags.get("opening_hours"),
                "phone": tags.get("phone"),
                "website": tags.get("website"),
                "tags": list(tags.keys()),
                "source": "osm",
                "scraped_at": scraped_at
            }
            mongo_docs.append(mongo_doc)

            # Form row for Postgres
            metadata = {
                "osm_id": osm_id,
                "subcategory": subcategory,
                "opening_hours": tags.get("opening_hours"),
                "phone": tags.get("phone"),
                "website": tags.get("website"),
                "full_tags": tags
            }
            
            pg_row = {
                "category": category,
                "name": name,
                "lon": float(lon),
                "lat": float(lat),
                "h3_index": h3_index,
                "source": "osm",
                "metadata": metadata
            }
            pg_rows.append(pg_row)

            # Form feature for GeoJSON
            geojson_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]
                },
                "properties": {
                    "id": osm_id,
                    "name": name,
                    "category": category,
                    "subcategory": subcategory,
                    "h3_index": h3_index
                }
            })

        # Save to MongoDB
        if self.mongo_db is not None and mongo_docs:
            try:
                collection = self.mongo_db["raw_amenities"]
                # Avoid bulk insert error by deleting existing osm_ids or just inserting
                # To prevent duplicates, we can bulk upsert or delete previous ones
                collection.delete_many({"osm_id": {"$in": [d["osm_id"] for d in mongo_docs]}})
                collection.insert_many(mongo_docs)
                logger.info(f"[OK] Saved {len(mongo_docs)} records to MongoDB (raw_amenities).")
            except Exception as e:
                logger.error(f"Failed to save to MongoDB: {e}")

        # Save to PostgreSQL
        if self.postgres_conn is not None and pg_rows:
            try:
                cursor = self.postgres_conn.cursor()
                logger.info("Writing to PostgreSQL database...")
                
                success_count = 0
                for row in pg_rows:
                    # 1. Ensure H3 index exists in urban_grids
                    self.ensure_h3_grid_exists(cursor, row["h3_index"], city_name)
                    
                    # 2. Insert amenity
                    try:
                        cursor.execute("""
                            INSERT INTO amenities (category, name, location, h3_index, source, metadata)
                            VALUES (%s, %s, ST_SetSRID(ST_Point(%s, %s), 4326), %s, %s, %s)
                        """, (
                            row["category"],
                            row["name"],
                            row["lon"],
                            row["lat"],
                            row["h3_index"],
                            row["source"],
                            json.dumps(row["metadata"])
                        ))
                        success_count += 1
                    except Exception as ex:
                        logger.debug(f"Failed to insert amenity {row['name']}: {ex}")
                        
                logger.info(f"[OK] Saved {success_count} records to PostgreSQL (amenities).")
            except Exception as e:
                logger.error(f"Failed to save to PostgreSQL: {e}")

        # File Export Fallback/Backup
        if export_geojson and geojson_features:
            geojson_data = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {
                        "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
                    }
                },
                "features": geojson_features
            }
            
            output_dir = "data/ingested"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"amenities_{city_name.lower().replace(' ', '_')}.geojson")
            
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(geojson_data, f, indent=2)
                logger.info(f"[OK] Exported GeoJSON backup file: {output_path}")
            except Exception as e:
                logger.error(f"Failed to write GeoJSON file: {e}")

    def close(self):
        if self.mongo_client:
            self.mongo_client.close()
        if self.postgres_conn:
            self.postgres_conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UrbanLens AI: OpenStreetMap Ingestion Scraper")
    parser.add_argument("--city", type=str, default="Chennai", help="Name of the city to scrape (e.g. Chennai)")
    args = parser.parse_args()

    scraper = OSMScraper()
    try:
        scraper.scrape(args.city)
    finally:
        scraper.close()
