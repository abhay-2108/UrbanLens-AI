import unittest
from unittest.mock import patch, MagicMock
from src.scrapers.elevation_scraper import ElevationScraper

class TestElevationScraper(unittest.TestCase):
    @patch('pymongo.MongoClient')
    @patch('psycopg2.connect')
    def setUp(self, mock_pg, mock_mongo):
        self.mock_mongo_client = MagicMock()
        mock_mongo.return_value = self.mock_mongo_client
        self.mock_pg_conn = MagicMock()
        mock_pg.return_value = self.mock_pg_conn
        self.scraper = ElevationScraper()

    @patch('requests.post')
    def test_get_elevation_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [{"elevation": 15.0}]
        }
        mock_post.return_value = mock_resp

        elevation = self.scraper.get_elevation(13.0827, 80.2707)
        self.assertEqual(elevation, 15.0)

    @patch('requests.post')
    @patch('src.scrapers.elevation_scraper.ElevationScraper.ensure_h3_grid_exists')
    def test_scrape_and_ingest(self, mock_grid, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [{"elevation": 15.0}]
        }
        mock_post.return_value = mock_resp

        mock_collection = MagicMock()
        self.scraper.mongo_db = {"climate_resilience_logs": mock_collection}

        mock_cursor = MagicMock()
        self.scraper.postgres_conn = MagicMock()
        self.scraper.postgres_conn.cursor.return_value = mock_cursor

        self.scraper.scrape("Chennai")

        # Ingestion Assertions
        mock_collection.insert_one.assert_called_once()
        mock_cursor.execute.assert_called_once()
        args, kwargs = mock_cursor.execute.call_args
        self.assertIn("climate_resilience", args[0])
        # 15.0 / 30.0 = 0.50 score
        self.assertEqual(args[1][1], 0.50)

if __name__ == "__main__":
    unittest.main()
