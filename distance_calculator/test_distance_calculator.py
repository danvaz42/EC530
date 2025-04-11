import os
import unittest
import tempfile
import pandas as pd
import numpy as np
import logging

# Since test_distance_calculator.py is in the same directory as distance_calculator.py,
# you can import the module directly.
import distance_calculator as dc


class TestDistanceCalculator(unittest.TestCase):
    
    def setUp(self):
        # Optionally disable logging to reduce noise during test output.
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Re-enable logging after tests.
        logging.disable(logging.NOTSET)
        # Remove any generated results file to keep tests independent.
        if os.path.exists("results.csv"):
            os.remove("results.csv")

    def test_validate_coord_valid(self):
        # Prepare a valid DataFrame with two numeric columns.
        df = pd.DataFrame({
            "X": [1.0, 2.0, 3.0],
            "Y": [4.0, 5.0, 6.0]
        })
        # Ensure no exception is raised.
        try:
            dc.validate_coord(df, "dummy.csv")
        except ValueError:
            self.fail("validate_coord raised ValueError unexpectedly for a valid DataFrame.")

    def test_validate_coord_invalid_columns(self):
        # DataFrame with less than two columns.
        df = pd.DataFrame({
            "X": [1.0, 2.0, 3.0]
        })
        with self.assertRaises(ValueError):
            dc.validate_coord(df, "dummy.csv")

    def test_validate_coord_non_numeric(self):
        # DataFrame with a non-numeric second column.
        df = pd.DataFrame({
            "X": [1.0, 2.0, 3.0],
            "Y": ["a", "b", "c"]
        })
        with self.assertRaises(ValueError):
            dc.validate_coord(df, "dummy.csv")

    def test_load_coord(self):
        # Create a temporary CSV file with valid coordinates.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tf:
            df = pd.DataFrame({
                "X": [10.0, 20.0],
                "Y": [30.0, 40.0]
            })
            df.to_csv(tf.name, index=False)
            tf.flush()
            # Load coordinates using the function and verify they match the CSV contents.
            coords = dc.load_coord(tf.name)
            expected = df.to_numpy()
            np.testing.assert_array_almost_equal(coords, expected)
        os.remove(tf.name)

    def test_compute_distance_matrix(self):
        # Create two small arrays of points.
        a1 = np.array([[0, 0], [1, 1]])
        a2 = np.array([[0, 1], [1, 2]])
        # Compute distance matrix with the function.
        dist_matrix = dc.compute_distance_matrix(a1, a2)
        # Expected distances computed manually.
        expected = np.array([
            [1.0, np.sqrt(5)],
            [1.0, np.sqrt(2)]
        ])
        np.testing.assert_array_almost_equal(dist_matrix, expected)

    def test_find_closest_points(self):
        # Set up arrays for points.
        a1 = np.array([[0, 0], [1, 1]])
        a2 = np.array([[0, 1], [1, 2]])
        dist_matrix = dc.compute_distance_matrix(a1, a2)
        # Run function to generate results.csv.
        dc.find_closest_points(a1, a2, dist_matrix)
        # Verify that results.csv exists.
        self.assertTrue(os.path.exists("results.csv"), "results.csv was not created.")
        # Load the results and check expected columns.
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
