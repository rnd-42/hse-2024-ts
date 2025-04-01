import unittest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from calculate_regression import compute_rolling_elasticity
from calculate_pointwise import compute_pointwise_elasticity
from db_interaction import merge_and_store_elasticities, read_from_postgres


class ElasticityTestCase(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range(start="2024-01-01", periods=60)
        attribute = np.linspace(1, 1.1, 30).tolist() + np.linspace(1.5, 2, 30).tolist()

        self.df = pd.DataFrame({
            "date": list(dates) * 2,
            "trips": np.random.uniform(100, 200, size=120),
            "attribute": attribute * 2,
            "time_series_id": [1] * 60 + [2] * 60,
            "attribute_id": [101] * 60 + [102] * 60
        })

    def test_compute_rolling_elasticity(self):
        result = compute_rolling_elasticity(self.df, window_size=7)
        self.assertFalse(result.empty)
        self.assertIn("elasticity", result.columns)
        self.assertTrue(result["method"].str.contains("rolling").all())

    def test_compute_pointwise_elasticity(self):
        result = compute_pointwise_elasticity(self.df, window_days=7)
        self.assertIn("elasticity", result.columns)
        self.assertTrue((result["elasticity"].notnull()).all() or result.empty)

    def test_merge_and_store_elasticities_mock(self):
        dummy_df = self.df.copy()
        dummy_df["elasticity"] = 0.5
        dummy_df["method"] = "test_method"

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        merge_and_store_elasticities(dummy_df, dummy_df, dummy_df,
                                     dummy_df, dummy_df, dummy_df,
                                     engine=mock_engine)

        self.assertTrue(mock_conn.execute.called)
        self.assertTrue(mock_conn.commit.called)

    @patch("db_interaction.pd.read_sql")
    def test_read_from_postgres(self, mock_read_sql):
        dummy_data = pd.DataFrame({
            "trips": [100, 150],
            "attribute": [1.2, 1.5],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "time_series_id": [1, 1],
            "attribute_id": [101, 101]
        })

        mock_read_sql.return_value = dummy_data

        df_result = read_from_postgres(engine=MagicMock())

        self.assertTrue(mock_read_sql.called)
        self.assertIsInstance(df_result, pd.DataFrame)
        self.assertListEqual(list(df_result.columns), list(dummy_data.columns))

    def test_pointwise_elasticity_exact_value(self):
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=4),
            "trips": [100, 100, 80, 80],
            "attribute": [10, 10, 12, 12],
            "time_series_id": [1]*4,
            "attribute_id": [101]*4
        })

        result = compute_pointwise_elasticity(df, window_days=1, min_price_change=0.05)

        self.assertEqual(len(result), 1)

        elasticity = result.iloc[0]["elasticity"]
        expected = np.log(80 / 100) / np.log(12 / 10)

        self.assertAlmostEqual(elasticity, expected, places=3)


if __name__ == "__main__":
    unittest.main()
