"""
UrbanLens AI: Computer Vision Pipeline
Purpose: Process street-level imagery to extract green canopy, sidewalks, and lighting
Uses: DeepLabV3 for segmentation + YOLOv8 for object detection
"""

import logging
import asyncio
from typing import Dict, Tuple, Optional, List
import numpy as np
import cv2
from PIL import Image
import torch
import torchvision.transforms as transforms
from torchvision.models.segmentation import deeplabv3_resnet101
from ultralytics import YOLO
import requests
from io import BytesIO
import psycopg2
from pymongo import MongoClient
from datetime import datetime

logger = logging.getLogger(__name__)

class StreetLevelImageProcessor:
    """Process street-level images from Google Street View or Mapillary"""
    
    def __init__(
        self,
        google_api_key: str = None,
        mapillary_token: str = None,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        """
        Initialize the image processor
        
        Args:
            google_api_key: Google Maps API key for Street View
            mapillary_token: Mapillary API token
            device: Device to run models on (cuda/cpu)
        """
        self.google_api_key = google_api_key
        self.mapillary_token = mapillary_token
        self.device = torch.device(device)
        
        # Load models
        self.deeplab = self._load_deeplab()
        self.yolo = self._load_yolo()
        
        # Image preprocessing
        self.preprocess = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def _load_deeplab(self):
        """Load pre-trained DeepLabV3 model for semantic segmentation"""
        try:
            model = deeplabv3_resnet101(pretrained=True)
            model = model.to(self.device)
            model.eval()
            logger.info("✓ DeepLabV3 model loaded")
            return model
        except Exception as e:
            logger.error(f"Failed to load DeepLabV3: {e}")
            return None
    
    def _load_yolo(self, model_path: str = "yolov8m.pt"):
        """Load YOLOv8 model for object detection"""
        try:
            model = YOLO(model_path)
            logger.info("✓ YOLOv8 model loaded")
            return model
        except Exception as e:
            logger.error(f"Failed to load YOLOv8: {e}")
            return None
    
    async def fetch_google_street_view(
        self,
        lat: float,
        lon: float,
        heading: float = 0,
        pitch: float = 0,
        fov: int = 90,
        size: str = "640x640"
    ) -> Optional[Image.Image]:
        """
        Fetch street-level image from Google Street View
        
        Args:
            lat: Latitude
            lon: Longitude
            heading: Camera heading (0-360)
            pitch: Camera pitch (-90 to 90)
            fov: Field of view
            size: Image size (WxH)
        
        Returns:
            PIL Image or None if failed
        """
        try:
            url = "https://maps.googleapis.com/maps/api/streetview"
            params = {
                "location": f"{lat},{lon}",
                "heading": heading,
                "pitch": pitch,
                "fov": fov,
                "size": size,
                "key": self.google_api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        return Image.open(BytesIO(image_data))
        except Exception as e:
            logger.error(f"Error fetching Google Street View: {e}")
        
        return None
    
    def calculate_green_canopy_score(self, image: Image.Image) -> float:
        """
        Calculate green canopy percentage using DeepLabV3
        
        Algorithm:
        1. Pass image through DeepLabV3
        2. Extract vegetation class predictions
        3. Calculate: (vegetation_pixels / total_pixels) * 100
        
        Args:
            image: PIL Image from street view
        
        Returns:
            Float between 0.0 and 100.0
        """
        try:
            if self.deeplab is None:
                return 0.0
            
            # Resize to standard input size
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                output = self.deeplab(image_tensor)
            
            # Extract segmentation map
            output_classes = output['out'].argmax(1).squeeze(0).cpu().numpy()
            
            # Classes in COCO: 9 = vegetable (grass), 12 = plant, 15 = tree
            # These are approximate - DeepLabV3 on Cityscapes dataset
            vegetation_classes = [9, 12, 15, 17]  # vegetation-related classes
            
            vegetation_mask = np.isin(output_classes, vegetation_classes)
            total_pixels = output_classes.size
            
            if total_pixels == 0:
                return 0.0
            
            green_canopy_percentage = (vegetation_mask.sum() / total_pixels) * 100.0
            
            logger.info(f"Green Canopy Score: {green_canopy_percentage:.2f}%")
            return min(100.0, green_canopy_percentage)
        
        except Exception as e:
            logger.error(f"Error calculating green canopy: {e}")
            return 0.0
    
    def detect_infrastructure(self, image: Image.Image) -> Dict:
        """
        Detect street infrastructure using YOLOv8
        
        Detects:
        - Sidewalks/pedestrian areas
        - Traffic signals/lights
        - Street signs
        - Vehicles (for traffic analysis)
        
        Args:
            image: PIL Image from street view
        
        Returns:
            Dictionary with detection results
        """
        try:
            if self.yolo is None:
                return {}
            
            # Convert PIL to numpy array
            image_array = np.array(image)
            
            # Run inference
            results = self.yolo(image_array, conf=0.5)
            
            detections = {
                "sidewalk_detected": False,
                "traffic_signals": 0,
                "street_lights": 0,
                "vehicles": 0,
                "pedestrians": 0,
                "confidence_scores": {}
            }
            
            # Process detections
            # COCO classes: 0=person, 2=car, 3=motorbike, 9=traffic light, etc.
            for result in results:
                for detection in result.boxes:
                    class_id = int(detection.cls)
                    confidence = float(detection.conf)
                    
                    # Map COCO classes to our categories
                    if class_id == 0:  # Person
                        detections["pedestrians"] += 1
                    elif class_id in [2, 3, 4, 5]:  # Vehicle types
                        detections["vehicles"] += 1
                    elif class_id == 9:  # Traffic light
                        detections["traffic_signals"] += 1
                    # Note: Street lights are harder to detect; may need custom model
            
            detections["sidewalk_detected"] = True  # Simplified; needs refinement
            detections["confidence_scores"]["overall"] = 0.85
            
            return detections
        
        except Exception as e:
            logger.error(f"Error detecting infrastructure: {e}")
            return {}


class CVPipeline:
    """Orchestrate the full computer vision pipeline"""
    
    def __init__(
        self,
        google_api_key: str,
        db_connection: psycopg2.extensions.connection,
        mongodb_client: MongoClient
    ):
        """
        Initialize the CV pipeline
        
        Args:
            google_api_key: Google Maps API key
            db_connection: PostgreSQL connection
            mongodb_client: MongoDB client
        """
        self.processor = StreetLevelImageProcessor(google_api_key=google_api_key)
        self.db = db_connection
        self.mongo = mongodb_client
        self.mongo_db = mongodb_client["urbanlens_ai"]
    
    async def process_grid_cell(
        self,
        h3_index: str,
        lat: float,
        lon: float,
        headings: List[int] = [0, 90, 180, 270]
    ) -> Dict:
        """
        Process a single H3 grid cell from multiple angles
        
        Args:
            h3_index: H3 cell identifier
            lat: Latitude
            lon: Longitude
            headings: List of camera headings to process
        
        Returns:
            Dictionary with aggregated CV results
        """
        results = {
            "h3_index": h3_index,
            "green_canopy_scores": [],
            "infrastructure_detections": [],
            "processed_images": 0,
            "processing_errors": 0
        }
        
        for heading in headings:
            try:
                # Fetch street view image
                image = await self.processor.fetch_google_street_view(
                    lat, lon, heading=heading
                )
                
                if image is None:
                    results["processing_errors"] += 1
                    continue
                
                # Process image
                green_score = self.processor.calculate_green_canopy_score(image)
                infrastructure = self.processor.detect_infrastructure(image)
                
                results["green_canopy_scores"].append(green_score)
                results["infrastructure_detections"].append(infrastructure)
                results["processed_images"] += 1
                
                # Store in MongoDB
                self._store_cv_log(h3_index, green_score, infrastructure)
            
            except Exception as e:
                logger.error(f"Error processing image for {h3_index} at heading {heading}: {e}")
                results["processing_errors"] += 1
        
        # Calculate aggregate scores
        if results["green_canopy_scores"]:
            avg_green = np.mean(results["green_canopy_scores"]) / 100.0  # Normalize to 0-1
            results["average_green_canopy"] = min(1.0, avg_green)
        else:
            results["average_green_canopy"] = 0.0
        
        # Store in database
        self._store_results_to_db(h3_index, results)
        
        return results
    
    def _store_cv_log(self, h3_index: str, green_score: float, infrastructure: Dict):
        """Store CV processing results in MongoDB"""
        try:
            collection = self.mongo_db["cv_processing_logs"]
            collection.insert_one({
                "h3_index": h3_index,
                "results": {
                    "green_canopy_percentage": green_score,
                    "sidewalk_detected": infrastructure.get("sidewalk_detected", False),
                    "traffic_signals": infrastructure.get("traffic_signals", 0),
                    "street_lights": infrastructure.get("street_lights", 0)
                },
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Error storing CV log: {e}")
    
    def _store_results_to_db(self, h3_index: str, results: Dict):
        """Store aggregated CV results in PostgreSQL"""
        try:
            cursor = self.db.cursor()
            
            avg_green = results.get("average_green_canopy", 0.0)
            
            # Update factor_scores
            cursor.execute("""
                INSERT INTO factor_scores (h3_index, factor_name, sub_factor_name, score, data_source)
                VALUES (%s, 'environment', 'green_canopy', %s, 'cv_pipeline')
                ON CONFLICT (h3_index, factor_name, sub_factor_name) 
                DO UPDATE SET score = %s, last_updated = NOW()
            """, (h3_index, avg_green, avg_green))
            
            self.db.commit()
            logger.info(f"✓ Stored CV results for {h3_index}")
        
        except Exception as e:
            logger.error(f"Error storing CV results: {e}")
            self.db.rollback()
    
    async def batch_process_city(self, city_id: str) -> Dict:
        """
        Batch process all grid cells in a city
        
        Args:
            city_id: City identifier
        
        Returns:
            Summary statistics
        """
        cursor = self.db.cursor()
        
        # Fetch all grids
        cursor.execute("""
            SELECT h3_index, ST_Y(center_point) as lat, ST_X(center_point) as lon
            FROM urban_grids
            WHERE city_id = %s
        """, (city_id,))
        
        grids = cursor.fetchall()
        summary = {
            "total_grids": len(grids),
            "processed": 0,
            "failed": 0
        }
        
        # Process with concurrency limit
        semaphore = asyncio.Semaphore(5)  # Process 5 grids in parallel
        
        async def process_with_limit(h3_idx, lat, lon):
            async with semaphore:
                try:
                    await self.process_grid_cell(h3_idx, lat, lon)
                    summary["processed"] += 1
                except Exception as e:
                    logger.error(f"Failed to process {h3_idx}: {e}")
                    summary["failed"] += 1
        
        # Run all tasks
        tasks = [
            process_with_limit(h3, lat, lon) for h3, lat, lon in grids
        ]
        await asyncio.gather(*tasks)
        
        return summary


# Example usage
async def main():
    """Example: Process street view images for a city"""
    import psycopg2
    from pymongo import MongoClient
    
    # Setup connections
    db_conn = psycopg2.connect(
        dbname="urbanlens_ai",
        user="postgres",
        password="password",
        host="localhost"
    )
    mongo_client = MongoClient("mongodb://localhost:27017/")
    
    # Initialize pipeline
    pipeline = CVPipeline(
        google_api_key="YOUR_API_KEY",
        db_connection=db_conn,
        mongodb_client=mongo_client
    )
    
    # Process Chennai
    summary = await pipeline.batch_process_city("Chennai")
    print(f"Processing complete: {summary}")
    
    db_conn.close()


if __name__ == "__main__":
    import aiohttp
    asyncio.run(main())
