# Closest Point Finder

This script finds the closest point in a second set of coordinates (from `file2.csv`) for each point provided in a first set of coordinates (from `file1.csv`), based on Euclidean distance.

## Features

*   Loads X, Y coordinates from two separate CSV files.
*   Validates that input files have at least two numeric columns.
*   Efficiently calculates the pairwise Euclidean distances between all points in the first file and all points in the second file using SciPy.
*   Identifies the closest point in the second file for each point in the first file.
*   Outputs the results (original point, closest point, distance) to the console.
*   Saves the detailed results to a CSV file named `results.csv`.
*   Includes detailed logging to `distance_calculator.log`.
*   Includes performance profiling for individual functions (logged) and the overall script (saved to `profile_results.prof`).

## Requirements

*   Python 3
*   NumPy (pip install numpy)
*   Pandas (pip install pandas)
*   SciPy (pip install scipy)

## Input Format

The script expects two input CSV files (`file1.csv` and `file2.csv` by default). Each file must contain at least two columns, where:

*   The first column represents the X coordinate.
*   The second column represents the Y coordinate.
*   These first two columns must contain numeric data.
*   Additional columns are ignored.

Example `file1.csv`:

X,Y,Label
1.0,2.5,PointA
3.2,4.1,PointB

Example `file2.csv`:

Longitude,Latitude,ID
0.9,2.6,Ref1
5.0,5.0,Ref2
3.0,4.0,Ref3

## Usage

1.  Prepare your input CSV files according to the format described above.
2.  Modify the script: Open the python script and change the `file1` and `file2` variables within the `main()` function to match the paths to your actual input CSV files:

    def main():
        file1 = "path/to/your/first_coordinates.csv"  # <-- CHANGE THIS
        file2 = "path/to/your/second_coordinates.csv" # <-- CHANGE THIS
        # ... rest of the function

3.  Run the script from your terminal:

    python your_script_name.py

    (Replace `your_script_name.py` with the actual name you saved the script as).

## Output

*   Console: Prints the mapping for each point in the first file to its closest point in the second file, along with the calculated distance.
*   `results.csv`: A CSV file containing the following columns:
    *   `Point in a1 (X)`: X coordinate from the first file.
    *   `Point in a1 (Y)`: Y coordinate from the first file.
    *   `Closest Point in a2 (X)`: X coordinate of the closest point from the second file.
    *   `Closest Point in a2 (Y)`: Y coordinate of the closest point from the second file.
    *   `Distance`: The calculated Euclidean distance (rounded).
*   `distance_calculator.log`: A log file containing detailed information about the script's execution, including validation steps, loading progress, calculation steps, errors, and profiling results for decorated functions.
*   `profile_results.prof`: A file containing detailed performance profiling statistics for the entire script execution. This can be analyzed further using Python's `pstats` module.

## Profiling Notes

*   Individual function performance is logged to `distance_calculator.log`.
*   To disable this per-function profiling (e.g., for slightly faster execution), set the environment variable `DISABLE_PROFILING` to `True` before running the script:
    *   Linux/macOS: export DISABLE_PROFILING=True; python your_script_name.py
    *   Windows (cmd): set DISABLE_PROFILING=True && python your_script_name.py
    *   Windows (PowerShell): $env:DISABLE_PROFILING="True"; python your_script_name.py
*   Overall script profiling is always performed and saved to `profile_results.prof`.
