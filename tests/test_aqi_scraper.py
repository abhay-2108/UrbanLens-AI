import unittest
from unittest.mock import patch, MagicMock
from src.scrapers.aqi_scraper import AQIScraper

class TestAQIScraper(unittest.TestCase):
    @patch('pymongo.MongoClient')
    @patch('psycopg2.connect')
    def setUp(self, mock_pg, mock_mongo):
        self.mock_mongo_client = MagicMock()
        mock_mongo.return_value = self.mock_mongo_client
        
        self.mock_pg_conn = MagicMock()
        mock_pg.return_value = self.mock_pg_conn
        
        # Patch HAS_ML_MODELS to False for deterministic formulaic testing
        self.patcher = patch('src.scrapers.aqi_scraper.HAS_ML_MODELS', False)
        self.patcher.start()
        
        self.scraper = AQIScraper()

    def tearDown(self):
        self.patcher.stop()

    def test_fetch_city_coordinates(self):
        lat, lon = self.scraper.fetch_city_coordinates("Chennai")
        self.assertEqual(lat, 13.0827)
        self.assertEqual(lon, 80.2707)

        # Test fallback
        lat_fb, lon_fb = self.scraper.fetch_city_coordinates("UnknownCity")
        self.assertEqual(lat_fb, 13.0827)
        self.assertEqual(lon_fb, 80.2707)

    def test_generate_synthetic_aqi_data(self):
        metrics = self.scraper.generate_synthetic_aqi_data(13.0827, 80.2707)
        self.assertIn("aqi", metrics)
        self.assertIn("risk_category", metrics)
        self.assertIn("liveability_score", metrics)
        self.assertTrue(0.0 <= metrics["liveability_score"] <= 1.0)
        self.assertEqual(metrics["risk_category"], "Low")

    @patch('src.scrapers.aqi_scraper.AQIScraper.ensure_h3_grid_exists')
    def test_scrape_and_ingest(self, mock_grid_check):
        # Setup mock database targets
        mock_collection = MagicMock()
        self.scraper.mongo_db = {"air_quality_logs": mock_collection}
        
        mock_cursor = MagicMock()
        self.scraper.postgres_conn = MagicMock()
        self.scraper.postgres_conn.cursor.return_value = mock_cursor

        # Run scraper
        self.scraper.scrape("Chennai")

        # Assert data was inserted into local MongoDB
        mock_collection.insert_one.assert_called_once()
        inserted_doc = mock_collection.insert_one.call_args[0][0]
        self.assertEqual(inserted_doc["city"], "Chennai")
        self.assertEqual(inserted_doc["metrics"]["risk_category"], "Low")

        # Assert PostgreSQL execution was called
        mock_cursor.execute.assert_called_once()
        args, kwargs = mock_cursor.execute.call_args
        self.assertIn("environment", args[0])
        self.assertIn("air_quality", args[0])

if __name__ == "__main__":
    unittest.main()
