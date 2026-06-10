"""
UrbanLens AI: 15-Minute Walkability Engine
Purpose: Generate isochrones (walk zones) and calculate walkability scores
Uses: OSRM for routing + GeoPandas for spatial analysis
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon
import aiohttp
import h3
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

logger = logging.getLogger(__name__)

class WalkabilityEngine:
    """Calculate 15-minute walkability for urban grids"""
    
    def __init__(
        self,
        osrm_url: str = "http://localhost:5000",
        db_connection: psycopg2.extensions.connection = None,
        mongodb_client = None
    ):
        """
        Initialize the walkability engine
        
        Args:
            osrm_url: URL to OSRM routing service
            db_connection: PostgreSQL connection
            mongodb_client: MongoDB connection
        """
        self.osrm_url = osrm_url
        self.db = db_connection
        self.mongo = mongodb_client
        self.session = None
        
    async def initialize_session(self):
        """Create async HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close async HTTP session"""
        if self.session:
            await self.session.close()
    
    async def get_isochrone(
        self,
        lat: float,
        lon: float,
        walk_time_minutes: int = 15,
        profile: str = "foot"
    ) -> Optional[Polygon]:
        """
        Generate an isochrone (walking zone) using OSRM
        
        Args:
            lat: Center latitude
            lon: Center longitude
            walk_time_minutes: Walking time in minutes (default 15)
            profile: Routing profile (foot, bike, car)
        
        Returns:
            Shapely Polygon representing the walk boundary
        """
        await self.initialize_session()
        
        try:
            # OSRM Isochrone API endpoint
            url = f"{self.osrm_url}/isochrone/v1/{profile}/{lon},{lat}"
            params = {
                "contours": walk_time_minutes,
                "generalize": 100,  # Simplify polygon for performance
            }
            
            async with self.session.get(url, params=params, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("features"):
                        coordinates = data["features"][0]["geometry"]["coordinates"][0]
                        return Polygon(coordinates)
                else:
                    logger.warning(f"OSRM returned status {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching isochrone: {e}")
            return None
    
    async def generate_isochrones_for_grid(
        self,
        h3_index: str,
        grid_center: Tuple[float, float],
        amenity_types: List[str] = ["pharmacy", "supermarket", "transit"]
    ) -> Dict[str, Dict]:
        """
        Generate isochrones for a single H3 grid cell
        
        Args:
            h3_index: H3 hexagon identifier
            grid_center: (lat, lon) tuple
            amenity_types: List of amenity categories to check
        
        Returns:
            Dictionary with isochrones for each amenity type
        """
        results = {}
        
        for amenity_type in amenity_types:
            isochrone = await self.get_isochrone(grid_center[0], grid_center[1])
            if isochrone:
                results[amenity_type] = {
                    "polygon": isochrone,
                    "area_sq_km": isochrone.area / 1e6,
                    "generated_at": datetime.utcnow()
                }
        
        return results
    
    def calculate_15_minute_walkability(
        self,
        h3_index: str,
        grid_boundary: Polygon,
        grid_center: Tuple[float, float]
    ) -> float:
        """
        Calculate the 15-minute walkability score
        
        Algorithm:
        1. Generate 15-minute isochrone from grid center
        2. Check if essential amenities fall within the polygon
        3. Score = (amenities_in_zone / total_expected_amenities)
        
        Args:
            h3_index: H3 cell ID
            grid_boundary: Polygon of the grid
            grid_center: (lat, lon) center point
        
        Returns:
            Float between 0.0 and 1.0
        """
        try:
            # Fetch 15-minute walk zone
            isochrone = asyncio.run(
                self.get_isochrone(grid_center[0], grid_center[1], walk_time_minutes=15)
            )
            
            if not isochrone:
                return 0.0
            
            # Query essential amenities from database
            cursor = self.db.cursor()
            
            # Essential amenity categories
            essential_categories = [
                "supermarket", "grocery", "pharmacy", "public_transit",
                "hospital", "clinic", "cafe", "restaurant"
            ]
            
            # Check each category
            amenities_found = 0
            total_expected = len(essential_categories)
            
            for category in essential_categories:
                cursor.execute("""
                    SELECT COUNT(*) FROM amenities
                    WHERE h3_index = %s 
                    AND category = %s
                    AND ST_Intersects(
                        location,
                        ST_GeomFromText(%s, 4326)
                    )
                """, (h3_index, category, isochrone.wkt))
                
                count = cursor.fetchone()[0]
                if count > 0:
                    amenities_found += 1
            
            walkability_score = amenities_found / total_expected
            
            logger.info(f"H3 {h3_index}: Walkability = {walkability_score:.2f}")
            return walkability_score
        
        except Exception as e:
            logger.error(f"Error calculating walkability for {h3_index}: {e}")
            return 0.0
    
    def batch_generate_isochrones(
        self,
        city_id: str,
        h3_resolution: int = 10
    ) -> pd.DataFrame:
        """
        Batch generate isochrones for all H3 cells in a city
        
        Args:
            city_id: City identifier (e.g., "Chennai")
            h3_resolution: H3 resolution level (0-15)
        
        Returns:
            DataFrame with isochrone results
        """
        try:
            cursor = self.db.cursor()
            
            # Fetch all H3 cells for the city
            cursor.execute("""
                SELECT h3_index, ST_Y(center_point) as lat, ST_X(center_point) as lon
                FROM urban_grids
                WHERE city_id = %s
                ORDER BY h3_index
            """, (city_id,))
            
            grids = cursor.fetchall()
            results = []
            
            for h3_index, lat, lon in grids:
                walkability_score = self.calculate_15_minute_walkability(
                    h3_index, None, (lat, lon)
                )
                
                results.append({
                    "h3_index": h3_index,
                    "walkability_score": walkability_score,
                    "processed_at": datetime.utcnow()
                })
            
            # Store results in database
            if results:
                cursor.execute("""
                    UPDATE urban_grids 
                    SET overall_score = overall_score + %s
                    WHERE h3_index = %s
                """, [(r["walkability_score"] * 0.1, r["h3_index"]) for r in results])
                
                self.db.commit()
            
            return pd.DataFrame(results)
        
        except Exception as e:
            logger.error(f"Batch isochrone generation failed: {e}")
            self.db.rollback()
            return pd.DataFrame()


class AccessibilityAnalyzer:
    """Analyze accessibility patterns using spatial queries"""
    
    def __init__(self, db_connection: psycopg2.extensions.connection):
        """Initialize the accessibility analyzer"""
        self.db = db_connection
    
    def find_nearest_amenity(
        self,
        h3_index: str,
        category: str,
        max_distance_m: float = 1000
    ) -> Optional[Dict]:
        """
        Find the nearest amenity of a specific category
        
        Args:
            h3_index: H3 cell ID
            category: Amenity category
            max_distance_m: Maximum search radius in meters
        
        Returns:
            Dictionary with amenity info and distance
        """
        try:
            cursor = self.db.cursor()
            
            cursor.execute("""
                SELECT 
                    a.id, 
                    a.name, 
                    a.category,
                    ST_Distance_Sphere(ug.center_point, a.location) as distance_m
                FROM amenities a
                JOIN urban_grids ug ON ug.h3_index = %s
                WHERE a.category = %s
                AND ST_DistanceSphere(ug.center_point, a.location) <= %s
                ORDER BY distance_m
                LIMIT 1
            """, (h3_index, category, max_distance_m))
            
            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "category": result[2],
                    "distance_m": result[3]
                }
            return None
        
        except Exception as e:
            logger.error(f"Error finding nearest amenity: {e}")
            return None
    
    def calculate_amenity_density(
        self,
        h3_index: str,
        category: str,
        radius_m: float = 1000
    ) -> float:
        """
        Calculate density of amenities in a radius
        
        Args:
            h3_index: H3 cell ID
            category: Amenity category
            radius_m: Search radius in meters
        
        Returns:
            Count of amenities per square kilometer
        """
        try:
            cursor = self.db.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as amenity_count,
                    ST_Area(
                        ST_Buffer(ug.center_point::geography, %s)::geometry
                    ) / 1e6 as area_sq_km
                FROM amenities a
                JOIN urban_grids ug ON ug.h3_index = %s
                WHERE a.category = %s
                AND ST_DistanceSphere(ug.center_point, a.location) <= %s
            """, (radius_m, h3_index, category, radius_m))
            
            result = cursor.fetchone()
            if result and result[1] > 0:
                return result[0] / result[1]
            return 0.0
        
        except Exception as e:
            logger.error(f"Error calculating amenity density: {e}")
            return 0.0


# Example usage
async def main():
    """Example: Generate walkability for a city"""
    import psycopg2
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        dbname="urbanlens_ai",
        user="postgres",
        password="password",
        host="localhost"
    )
    
    # Initialize engine
    engine = WalkabilityEngine(
        osrm_url="http://localhost:5000",
        db_connection=conn
    )
    
    # Generate isochrones for Chennai
    results = engine.batch_generate_isochrones(city_id="Chennai")
    print(f"Processed {len(results)} grids")
    print(results.head())
    
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
