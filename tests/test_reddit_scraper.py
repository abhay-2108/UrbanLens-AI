import unittest
from unittest.mock import patch, MagicMock
from src.scrapers.reddit_scraper import RedditScraper

class TestRedditScraper(unittest.TestCase):
    @patch('pymongo.MongoClient')
    def setUp(self, mock_mongo):
        self.mock_mongo_client = MagicMock()
        mock_mongo.return_value = self.mock_mongo_client
        self.scraper = RedditScraper()

    def test_analyze_sentiment(self):
        # Negative post
        analysis_neg = self.scraper.analyze_sentiment("Frequent power cut and water outage in my area!")
        self.assertEqual(analysis_neg["sentiment"], "negative")
        self.assertEqual(analysis_neg["severity"], "high")

        # Positive post
        analysis_pos = self.scraper.analyze_sentiment("Very clean park and nice beautiful street.")
        self.assertEqual(analysis_pos["sentiment"], "positive")

        # Neutral post
        analysis_neut = self.scraper.analyze_sentiment("The road has a subway entrance.")
        self.assertEqual(analysis_neut["sentiment"], "neutral")

    def test_scrape_mock_fallback(self):
        # Trigger mock run
        self.scraper.client_id = ""
        self.scraper.client_secret = ""
        
        mock_collection = MagicMock()
        self.scraper.mongo_db = {"social_signals": mock_collection}

        signals = self.scraper.scrape("Chennai")
        self.assertEqual(len(signals), 2)
        
        # Ingestion Assertions
        mock_collection.delete_many.assert_called_once()
        mock_collection.insert_many.assert_called_once()

if __name__ == "__main__":
    unittest.main()
