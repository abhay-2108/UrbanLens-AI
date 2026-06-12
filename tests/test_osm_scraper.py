import unittest
from unittest.mock import patch, MagicMock
from src.scrapers.osm_scraper import OSMScraper

class TestOSMScraper(unittest.TestCase):
    @patch('pymongo.MongoClient')
    @patch('psycopg2.connect')
    def setUp(self, mock_pg, mock_mongo):
        # Setup mock clients to prevent actual database connections
        self.mock_mongo_client = MagicMock()
        mock_mongo.return_value = self.mock_mongo_client
        
        self.mock_pg_conn = MagicMock()
        mock_pg.return_value = self.mock_pg_conn
        
        self.scraper = OSMScraper()

    @patch('requests.post')
    def test_query_overpass_success(self, mock_post):
        # Mock successful response from Overpass API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {
                    "type": "node",
                    "id": 123456,
                    "lat": 13.0827,
                    "lon": 80.2707,
                    "tags": {
                        "amenity": "pharmacy",
                        "name": "Apollo Pharmacy",
                        "opening_hours": "24/7"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        data = self.scraper.query_overpass("Chennai")
        self.assertEqual(len(data.get("elements", [])), 1)
        self.assertEqual(data["elements"][0]["tags"]["amenity"], "pharmacy")

    @patch('requests.post')
    @patch('src.scrapers.osm_scraper.OSMScraper.ensure_h3_grid_exists')
    def test_scrape_and_ingest(self, mock_grid_check, mock_post):
        # Mock Overpass response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {
                    "type": "node",
                    "id": 1001,
                    "lat": 13.0827,
                    "lon": 80.2707,
                    "tags": {
                        "amenity": "hospital",
                        "name": "General Hospital"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        # Setup mock collections and cursors
        mock_collection = MagicMock()
        self.scraper.mongo_db = {"raw_amenities": mock_collection}
        
        mock_cursor = MagicMock()
        self.scraper.postgres_conn = MagicMock()
        self.scraper.postgres_conn.cursor.return_value = mock_cursor

        # Run scrape (passing export_geojson=False to avoid writing files in test)
        self.scraper.scrape("Chennai", export_geojson=False)

        # Assert MongoDB inserts were called
        mock_collection.delete_many.assert_called_once()
        mock_collection.insert_many.assert_called_once()

        # Assert PostgreSQL execution was called
        mock_cursor.execute.assert_called_once()
        args, kwargs = mock_cursor.execute.call_args
        self.assertIn("General Hospital", args[1])
        self.assertIn("hospital", args[1])

if __name__ == "__main__":
    unittest.main()
