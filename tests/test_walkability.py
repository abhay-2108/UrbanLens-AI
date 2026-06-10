import unittest
from unittest.mock import MagicMock, patch
from src.pipelines.walkability_engine import WalkabilityEngine

class TestWalkabilityEngine(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.engine = WalkabilityEngine(
            osrm_url="http://mock-osrm",
            db_connection=self.mock_db
        )

    def test_calculate_walkability_logic(self):
        """Test that walkability score is calculated correctly based on amenities"""
        # Mocking the DB response for amenities
        self.mock_db.cursor().execute.return_value = None
        self.mock_db.cursor().fetchone.side_effect = [(1,), (0,), (1,), (0,), (0,), (0,), (0,), (0,)]
        
        # Mocking the isochrone fetch
        with patch('src.pipelines.walkability_engine.WalkabilityEngine.get_isochrone', 
                   return_value=MagicMock(wkt="POLYGON(...)")):
            score = self.engine.calculate_15_minute_walkability(
                h3_index="8828308281fffff",
                grid_boundary=None,
                grid_center=(13.08, 80.27)
            )
            # 2 amenities found out of 8 = 0.25
            self.assertEqual(score, 0.25)

if __name__ == "__main__":
    unittest.main()
