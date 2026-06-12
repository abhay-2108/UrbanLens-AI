import unittest
import os
from unittest.mock import patch, MagicMock
from src.scrapers.mapillary_scraper import MapillaryScraper

class TestMapillaryScraper(unittest.TestCase):
    @patch('pymongo.MongoClient')
    def setUp(self, mock_mongo):
        self.mock_mongo_client = MagicMock()
        mock_mongo.return_value = self.mock_mongo_client
        self.scraper = MapillaryScraper()

    @patch('requests.get')
    def test_fetch_mapillary_images_fallback(self, mock_get):
        # Set token to empty to trigger mock PNG generator
        self.scraper.token = ""
        mock_collection = MagicMock()
        self.scraper.mongo_db = {"cv_processing_logs": mock_collection}

        image_paths = self.scraper.fetch_mapillary_images("88618c4885fffff", output_dir="data/test_images")
        
        self.assertEqual(len(image_paths), 1)
        self.assertTrue(os.path.exists(image_paths[0]))
        self.assertIn("mock_street_88618c4885fffff.png", image_paths[0])
        
        # Clean up created file
        if os.path.exists(image_paths[0]):
            os.remove(image_paths[0])
            os.rmdir("data/test_images")

if __name__ == "__main__":
    unittest.main()
