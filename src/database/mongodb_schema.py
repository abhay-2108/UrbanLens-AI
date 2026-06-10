"""
UrbanLens AI: MongoDB Schema Definitions
Purpose: Store semi-structured data (real estate, social signals, raw amenities)
"""

from pymongo import ASCENDING, DESCENDING, TEXT
from typing import Dict, List, Optional

class MongoDBCollections:
    """Define MongoDB collections and their indexes"""

    @staticmethod
    def get_real_estate_schema() -> Dict:
        """
        Real Estate Listings Collection
        Used for: Economics & Cost Factor
        """
        return {
            "properties": {
                "listing_id": {"type": "string", "description": "Unique identifier from source platform"},
                "platform": {"type": "string", "enum": ["zillow", "99acres", "magicbricks", "housing_com"]},
                "location": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["Point"]},
                        "coordinates": {"type": "array", "items": {"type": "number"}}
                    }
                },
                "h3_index": {"type": "string", "description": "H3 cell identifier"},
                "details": {
                    "type": "object",
                    "properties": {
                        "price": {"type": "number"},
                        "currency": {"type": "string"},
                        "bhk": {"type": "integer"},
                        "sq_ft": {"type": "number"},
                        "property_type": {"type": "string", "enum": ["apartment", "house", "condo", "townhouse"]},
                        "furnishing": {"type": "string", "enum": ["furnished", "semi-furnished", "unfurnished"]},
                        "age_years": {"type": "integer"},
                        "parking": {"type": "boolean"}
                    }
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "amenities": {"type": "array"},
                        "broker_name": {"type": "string"},
                        "contact": {"type": "string"}
                    }
                },
                "scraped_at": {"type": "date"}
            }
        }

    @staticmethod
    def get_social_signals_schema() -> Dict:
        """
        Social Media Signals Collection
        Used for: Utility Resilience & Sentiment Factor
        """
        return {
            "properties": {
                "post_id": {"type": "string"},
                "platform": {"type": "string", "enum": ["twitter", "reddit", "civic_forum", "nextdoor"]},
                "text": {"type": "string"},
                "author": {"type": "string"},
                "entities": {
                    "type": "object",
                    "properties": {
                        "neighborhood": {"type": "string"},
                        "city": {"type": "string"},
                        "street": {"type": "string"}
                    }
                },
                "analysis": {
                    "type": "object",
                    "properties": {
                        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                        "category": {"type": "string", "enum": [
                            "power_failure", "water_scarcity", "flooding", "safety_concern",
                            "traffic_issue", "noise_pollution", "construction", "general_vibe"
                        ]},
                        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                        "model_version": {"type": "string"},
                        "confidence": {"type": "number"}
                    }
                },
                "h3_index": {"type": "string"},
                "timestamp": {"type": "date"},
                "engagement": {
                    "type": "object",
                    "properties": {
                        "likes": {"type": "integer"},
                        "shares": {"type": "integer"},
                        "replies": {"type": "integer"}
                    }
                }
            }
        }

    @staticmethod
    def get_raw_amenities_schema() -> Dict:
        """
        Raw Amenities Collection
        Used for: Initial data before geospatial indexing
        """
        return {
            "properties": {
                "osm_id": {"type": "string"},
                "category": {"type": "string"},
                "subcategory": {"type": "string"},
                "name": {"type": "string"},
                "lat": {"type": "number"},
                "lon": {"type": "number"},
                "h3_index": {"type": "string"},
                "opening_hours": {"type": "string"},
                "phone": {"type": "string"},
                "website": {"type": "string"},
                "tags": {"type": "array"},
                "source": {"type": "string", "enum": ["osm", "google_places", "gtfs"]},
                "scraped_at": {"type": "date"}
            }
        }

    @staticmethod
    def get_cv_processing_logs_schema() -> Dict:
        """
        Computer Vision Processing Logs
        Used for: Tracking CV pipeline execution
        """
        return {
            "properties": {
                "image_id": {"type": "string"},
                "h3_index": {"type": "string"},
                "url": {"type": "string"},
                "processing_stage": {"type": "string", "enum": ["downloaded", "validated", "segmented", "analyzed"]},
                "models_applied": {"type": "array"},
                "results": {
                    "type": "object",
                    "properties": {
                        "green_canopy_percentage": {"type": "number"},
                        "sidewalk_detected": {"type": "boolean"},
                        "streetlight_count": {"type": "integer"},
                        "confidence_scores": {"type": "object"}
                    }
                },
                "error_log": {"type": "string"},
                "processing_time_ms": {"type": "integer"},
                "timestamp": {"type": "date"}
            }
        }


class MongoDBIndexes:
    """Define all necessary indexes for optimal query performance"""

    @staticmethod
    def get_indexes() -> Dict[str, List]:
        """Returns a dictionary of collection names and their required indexes"""
        return {
            "real_estate_listings": [
                {"keys": [("location", "2dsphere")], "name": "idx_location_geospatial"},
                {"keys": [("h3_index", ASCENDING)], "name": "idx_h3_index"},
                {"keys": [("platform", ASCENDING), ("scraped_at", DESCENDING)], "name": "idx_platform_date"},
                {"keys": [("details.price", ASCENDING)], "name": "idx_price"},
                {"keys": [("details.bhk", ASCENDING)], "name": "idx_bhk"},
            ],
            "social_signals": [
                {"keys": [("h3_index", ASCENDING)], "name": "idx_h3_index"},
                {"keys": [("timestamp", DESCENDING)], "name": "idx_timestamp"},
                {"keys": [("platform", ASCENDING), ("category", ASCENDING)], "name": "idx_platform_category"},
                {"keys": [("text", TEXT)], "name": "idx_text_search"},
                {"keys": [("analysis.severity", ASCENDING)], "name": "idx_severity"},
            ],
            "raw_amenities": [
                {"keys": [("location", "2dsphere")], "name": "idx_location_geospatial"},
                {"keys": [("category", ASCENDING)], "name": "idx_category"},
                {"keys": [("h3_index", ASCENDING)], "name": "idx_h3_index"},
                {"keys": [("source", ASCENDING)], "name": "idx_source"},
            ],
            "cv_processing_logs": [
                {"keys": [("h3_index", ASCENDING)], "name": "idx_h3_index"},
                {"keys": [("timestamp", DESCENDING)], "name": "idx_timestamp"},
                {"keys": [("processing_stage", ASCENDING)], "name": "idx_stage"},
            ]
        }


def initialize_mongodb(db_connection):
    """
    Initialize MongoDB collections with indexes
    
    Usage:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/")
        db = client["urbanlens_ai"]
        initialize_mongodb(db)
    """
    indexes = MongoDBIndexes.get_indexes()
    
    for collection_name, index_list in indexes.items():
        collection = db_connection[collection_name]
        for index_spec in index_list:
            keys = index_spec["keys"]
            name = index_spec.get("name")
            try:
                collection.create_index(keys, name=name, background=True)
                print(f"✓ Created index: {collection_name}.{name}")
            except Exception as e:
                print(f"⚠ Index already exists or error: {e}")
