import os
import unittest
import tempfile
import pandas as pd
import numpy as np
import logging

# Directly import the module since both test and module are in the same directory.
import distance_calculator as dc


class TestDistanceCalculator(unittest.TestCase):
    
    def setUp(self):
        # Disable logging to keep test output clean.
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Re-enable logging after tests.
        logging.disable(logging.NOTSET)
        # Remove any generated results file after each test.
        if os.path.exists("results.csv"):
            os.remove("results.csv")

    def test_validate_coord_valid(self):
        # Create a valid DataFrame with two numeric columns.
        df = pd.DataFrame({
            "X": [1.0, 2.0, 3.0],
            "Y": [4.0, 5.0, 6.0]
        })
        # Should not raise an exception.
        try:
            dc.validate_coord(df, "dummy.csv")
        except ValueError:
            self.fail("validate_coord raised ValueError unexpectedly for a valid DataFrame.")

    def test_validate_coord_invalid_columns(self):
        # DataFrame with only one column.
        df = pd.DataFrame({
            "X": [1.0, 2.0, 3.0]
        })
        with self.assertRaises(ValueError):
            dc.validate_coord(df, "dummy.csv")

    def test_validate_coord_non_numeric(self):
        # DataFrame where second column is non-numeric.
        df = pd.DataFrame({
            "X": [1.0, 2.0, 3.0],
            "Y": ["a", "b", "c"]
        })
        with self.assertRaises(ValueError):
            dc.validate_coord(df, "dummy.csv")

    def test_load_coord(self):
        # Create a temporary CSV file containing valid coordinate data.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tf:
            df = pd.DataFrame({
                "X": [10.0, 20.0],
                "Y": [30.0, 40.0]
            })
            df.to_csv(tf.name, index=False)
            tf.flush()
            # Load coordinates using the load_coord function.
            coords = dc.load_coord(tf.name)
            expected = df.to_numpy()
            np.testing.assert_array_almost_equal(coords, expected)
        os.remove(tf.name)

    def test_compute_distance_matrix(self):
        # Create two small arrays of points.
        a1 = np.array([[0, 0], [1, 1]])
        a2 = np.array([[0, 1], [1, 2]])
        # Compute the distance matrix.
        dist_matrix = dc.compute_distance_matrix(a1, a2)
        # Expected distances computed manually:
        # For (0, 0) -> (0, 1): 1.0, (0, 0) -> (1, 2): sqrt(5)
        # For (1, 1) -> (0, 1): 1.0, (1, 1) -> (1, 2): 1.0
        expected = np.array([
            [1.0, np.sqrt(5)],
            [1.0, 1.0]
        ])
        np.testing.assert_array_almost_equal(dist_matrix, expected, decimal=6)

    def test_find_closest_points(self):
        # Set up arrays for points.
        a1 = np.array([[0, 0], [1, 1]])
        a2 = np.array([[0, 1], [1, 2]])
        dist_matrix = dc.compute_distance_matrix(a1, a2)
        # Run the function to generate results.csv.
        dc.find_closest_points(a1, a2, dist_matrix)
        # Verify that results.csv exists.
        self.assertTrue(os.path.exists("results.csv"), "results.csv was not created.")
        # Read the file and check that it has the expected columns.
        results_df = pd.read_csv("results.csv")
        expected_columns = [
            "Point in a1 (X)",
            "Point in a1 (Y)",
            "Closest Point in a2 (X)",
            "Closest Point in a2 (Y)",
            "Distance"
        ]
        self.assertListEqual(list(results_df.columns), expected_columns)


if __name__ == '__main__':
    unittest.main()
