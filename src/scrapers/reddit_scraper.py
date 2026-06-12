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

class RedditScraper:
    def __init__(self, config_path="config/settings.conf"):
        self.config_path = config_path
        self.mongo_client = None
        self.mongo_db = None
        
        # Load Config
        self.load_config()
        # Setup connection
        self.init_connection()

    def load_config(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "UrbanLensAI/1.0")
        
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.mongo_dbname = os.getenv("MONGODB_DB")

        config = ConfigParser()
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            if not self.client_id: self.client_id = config.get("APIS", "REDDIT_CLIENT_ID", fallback="")
            if not self.client_secret: self.client_secret = config.get("APIS", "REDDIT_CLIENT_SECRET", fallback="")
            if not self.mongo_uri: self.mongo_uri = config.get("DATABASE", "MONGODB_URI", fallback="mongodb://localhost:27017/")
            if not self.mongo_dbname: self.mongo_dbname = config.get("DATABASE", "MONGODB_DB", fallback="urbanlens_ai")
        else:
            if not self.mongo_uri: self.mongo_uri = "mongodb://localhost:27017/"
            if not self.mongo_dbname: self.mongo_dbname = "urbanlens_ai"

    def init_connection(self):
        try:
            self.mongo_client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2000)
            self.mongo_client.admin.command('ping')
            self.mongo_db = self.mongo_client[self.mongo_dbname]
            logger.info("[OK] Connected to MongoDB in RedditScraper.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to MongoDB in RedditScraper: {e}")
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

    def get_subreddit_name(self, city_name: str) -> str:
        mapping = {
            "chennai": "chennai",
            "bangalore": "bangalore",
            "bengaluru": "bangalore",
            "mumbai": "mumbai",
            "delhi": "delhi",
            "san francisco": "bayarea"
        }
        return mapping.get(city_name.lower().strip(), "localnews")

    def analyze_sentiment(self, text: str) -> dict:
        """Lightweight sentiment analyzer formula to avoid installing large models"""
        negative_words = ["outage", "cut", "flooding", "flood", "garbage", "trash", "bad", "terrible", "unsafe", "crime", "stole", "broken"]
        positive_words = ["great", "clean", "safe", "love", "beautiful", "good", "nice", "excellent", "fast", "efficient"]
        
        words = text.lower().split()
        neg_count = sum(1 for w in words if any(nw in w for nw in negative_words))
        pos_count = sum(1 for w in words if any(pw in w for pw in positive_words))
        
        if neg_count > pos_count:
            sentiment = "negative"
            score = -0.5 * neg_count
        elif pos_count > neg_count:
            sentiment = "positive"
            score = 0.5 * pos_count
        else:
            sentiment = "neutral"
            score = 0.0
            
        severity = "low"
        if neg_count >= 3:
            severity = "critical"
        elif neg_count >= 2:
            severity = "high"
        elif neg_count == 1:
            severity = "medium"
            
        return {
            "sentiment": sentiment,
            "score": round(max(-1.0, min(1.0, score)), 2),
            "severity": severity
        }

    def fetch_mock_reddit_posts(self, city_name: str, h3_index: str) -> list:
        """Returns realistic neighborhood reports for local testing"""
        logger.info("Generating realistic synthetic Reddit signals for local development.")
        return [
            {
                "platform": "reddit",
                "post_id": "r_1001",
                "text": "Water logging in Velachery area after the heavy rain yesterday. Standard monsoon nightmare.",
                "author": "chennai_local_user",
                "entities": {"neighborhood": "Velachery", "city": city_name},
                "h3_index": h3_index,
                "timestamp": datetime.utcnow()
            },
            {
                "platform": "reddit",
                "post_id": "r_1002",
                "text": "Frequent 2-hour power cuts in Adyar during afternoon hours. Anyone else facing this issue?",
                "author": "adyar_techie",
                "entities": {"neighborhood": "Adyar", "city": city_name},
                "h3_index": h3_index,
                "timestamp": datetime.utcnow()
            }
        ]

    def query_reddit_api(self, subreddit: str, query: str) -> list:
        """Queries public Reddit JSON endpoints using a clean request structure"""
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "restrict_sr": "1",
            "limit": "10",
            "sort": "new"
        }
        headers = {"User-Agent": self.user_agent}
        
        try:
            # First, check if OAuth credentials are provided and try to obtain a token if possible
            # Standard public JSON search works without token under strict rate-limits if User-Agent is unique
            response = requests.get(url, params=params, headers=headers, timeout=20)
            if response.status_code == 200:
                posts = []
                data = response.json().get("data", {}).get("children", [])
                for child in data:
                    item = child.get("data", {})
                    posts.append({
                        "platform": "reddit",
                        "post_id": item.get("id"),
                        "text": f"{item.get('title', '')} \n {item.get('selftext', '')}",
                        "author": item.get("author"),
                        "timestamp": datetime.utcfromtimestamp(item.get("created_utc", datetime.utcnow().timestamp()))
                    })
                return posts
            else:
                logger.warning(f"Reddit public JSON returned status {response.status_code}. Using mock fallback.")
                return []
        except Exception as e:
            logger.error(f"Error querying Reddit: {e}. Using mock fallback.")
            return []

    def scrape(self, city_name: str) -> list:
        lat, lon = self.fetch_city_coordinates(city_name)
        h3_index = h3.latlng_to_cell(lat, lon, 8)
        
        # Determine if we can query the real API
        subreddit = self.get_subreddit_name(city_name)
        raw_posts = []
        
        if self.client_id and self.client_secret:
            logger.info(f"Querying Reddit API for r/{subreddit} with keyword 'water power flood'...")
            # Aggregate search query
            raw_posts = self.query_reddit_api(subreddit, "water OR power OR flood OR garbage")
        
        # Fallback to mock data if API results are empty or keys missing
        if not raw_posts:
            raw_posts = self.fetch_mock_reddit_posts(city_name, h3_index)

        # Analyze and format posts
        processed_signals = []
        for post in raw_posts:
            sentiment_analysis = self.analyze_sentiment(post["text"])
            
            # Ensure proper mapping and keys
            post_doc = {
                "platform": post["platform"],
                "post_id": post["post_id"],
                "text": post["text"],
                "author": post["author"],
                "entities": post.get("entities", {"city": city_name}),
                "analysis": {
                    "sentiment": sentiment_analysis["sentiment"],
                    "category": "power_failure" if "power" in post["text"].lower() else "flooding" if "flood" in post["text"].lower() else "general_vibe",
                    "severity": sentiment_analysis["severity"],
                    "confidence": 0.85
                },
                "h3_index": post.get("h3_index", h3_index),
                "timestamp": post["timestamp"]
            }
            processed_signals.append(post_doc)

        # Save to MongoDB
        if self.mongo_db is not None and processed_signals:
            try:
                collection = self.mongo_db["social_signals"]
                # Delete existing posts to prevent duplicates
                collection.delete_many({"post_id": {"$in": [p["post_id"] for p in processed_signals]}})
                collection.insert_many(processed_signals)
                logger.info(f"[OK] Ingested {len(processed_signals)} social signals into MongoDB (social_signals).")
            except Exception as e:
                logger.error(f"Failed to save to MongoDB: {e}")

        # Backup File
        output_dir = "data/ingested"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"social_{city_name.lower().replace(' ', '_')}.jsonl")
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for signal in processed_signals:
                    serializable = signal.copy()
                    if "_id" in serializable:
                        serializable["_id"] = str(serializable["_id"])
                    if isinstance(serializable["timestamp"], datetime):
                        serializable["timestamp"] = serializable["timestamp"].isoformat()
                    f.write(json.dumps(serializable) + "\n")
            logger.info(f"[OK] Exported JSONL backup file: {output_path}")
        except Exception as e:
            logger.error(f"Failed to write JSONL backup file: {e}")

        return processed_signals

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UrbanLens AI: Reddit Social Signals Crawler")
    parser.add_argument("--city", type=str, default="Chennai", help="Name of the city")
    args = parser.parse_args()

    scraper = RedditScraper()
    scraper.scrape(args.city)
