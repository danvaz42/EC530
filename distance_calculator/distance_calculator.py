import os
import numpy as np
import pandas as pd
import logging
import cProfile
import pstats
import io
from scipy.spatial.distance import cdist  # scipy package

# configure logging
logging.basicConfig(
    filename="distance_calculator.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def profile_function(func):
    """Decorator to profile a function and log its execution time."""
    def wrapper(*args, **kwargs):
        # Disable profiling if environment variable DISABLE_PROFILING is set to "True"
        if os.environ.get("DISABLE_PROFILING", "False") == "True":
            return func(*args, **kwargs)

        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        # Save profiling stats to a string
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats(pstats.SortKey.TIME)
        ps.print_stats()
        logging.info(f"Profiling results for {func.__name__}:\n{s.getvalue()}")

        return result
    return wrapper


@profile_function
def validate_coord(df, file_path):
    # check that the csv contains two numeric columns
    logging.info(f"Validating coordinate format in {file_path}")

    if df.shape[1] < 2:
        logging.error(f"File {file_path} must have at least two columns (X and Y coordinates).")
        raise ValueError(f"File {file_path} must have at least two columns (X and Y coordinates).")

    try:
        df.iloc[:, 0].astype(float)
        df.iloc[:, 1].astype(float)
    except ValueError:
        logging.error(f"File {file_path} contains non-numeric values in coordinate columns.")
        raise ValueError(f"File {file_path} contains non-numeric values in coordinate columns.")

    logging.info(f"File {file_path} passed validation.")


@profile_function
def load_coord(file_path):
    # load x and y coordinates from a .csv file (first and second columns)
    try:
        logging.info(f"Loading coordinates from {file_path}")
        df = pd.read_csv(file_path)

        # run coordinate check
        validate_coord(df, file_path)

        # extract the first two columns as x,y coordinates
        coordinates = df.iloc[:, [0, 1]].to_numpy()
        logging.info(f"Successfully loaded {coordinates.shape[0]} coordinates from {file_path}.")

        return coordinates

    except Exception as e:
        logging.exception(f"Error loading file {file_path}")
        raise


@profile_function
def compute_distance_matrix(a1, a2):
    # calculate the pairwise euclidean distance matrix
    logging.info("Computing distance matrix.")
    distance_matrix = cdist(a1, a2)
    logging.info(f"Computed distance matrix of shape {distance_matrix.shape}.")
    return distance_matrix


@profile_function
def find_closest_points(a1, a2, distance_matrix):
    # find the closest points and save results to csv
    logging.info("Finding closest points.")

    # find the index of the smallest value => the min distance - along each row of the distance matrix
    closest_indices = np.argmin(distance_matrix, axis=1)

    results = []
    for i, idx in enumerate(closest_indices):
        closest_point = a2[idx]
        distance = distance_matrix[i, idx]
        result = {
            "Point in a1 (X)": a1[i][0],
            "Point in a1 (Y)": a1[i][1],
            "Closest Point in a2 (X)": closest_point[0],
            "Closest Point in a2 (Y)": closest_point[1],
            "Distance": round(distance, 2)
        }
        results.append(result)
        print(f"Starting Point: ({a1[i][0]}, {a1[i][1]}) => Closest Point: ({closest_point[0]}, {closest_point[1]}), with Distance: {round(distance, 2)}")
        logging.debug(f"Matched {result}")

    # save results
    results_df = pd.DataFrame(results)
    results_df.to_csv("results.csv", index=False)
    logging.info("Results saved to results.csv")


def main():
    file1 = "file1.csv"  # replace with actual csv path
    file2 = "file2.csv"  # replace with actual csv path

    try:
        a1 = load_coord(file1)
        a2 = load_coord(file2)

        distance_matrix = compute_distance_matrix(a1, a2)
        find_closest_points(a1, a2, distance_matrix)

        print("Results saved to results.csv")

    except ValueError as e:
        logging.error(f"Error: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    # Profile the entire script
    profiler = cProfile.Profile()
    profiler.enable()

    main()

    profiler.disable()

    # Save profiling results to a file
    with open("profile_results.prof", "w") as f:
        ps = pstats.Stats(profiler, stream=f)
        ps.sort_stats(pstats.SortKey.TIME)
        ps.print_stats()

    print("Profiling results saved to profile_results.prof")

    ps = pstats.Stats(profiler)
    ps.sort_stats(pstats.SortKey.TIME)  # sort by execution time
    ps.print_stats(10)  # displays top 10 slowest functions
