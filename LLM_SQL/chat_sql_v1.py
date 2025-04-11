import sqlite3
import pandas as pd
import os
import re
import logging
import time
from openai import OpenAI

# Replace 'insert key' with your actual OpenAI API key
# Consider using environment variables for security
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", 'insert_key_here'))


def setup_logging(log_file):
    """Configures logging to file and console."""
    # Remove existing handlers to avoid duplicate logs if called multiple times
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'),
            logging.StreamHandler()
        ]
    )
    # Reduce pandas logging noise if desired
    logging.getLogger('pandas').setLevel(logging.WARNING)
    logging.info("--- CLI Application Started ---")
    logging.info("Using database: %s", DB_FILE)
    logging.info("Logging to: %s", log_file)


def sanitize_name(name):
    """Sanitizes table or column names for safe use in SQL."""
    name = str(name).strip()
    # Replace non-alphanumeric characters (except underscore) with underscore
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Prepend underscore if name starts with a digit
    if name and name[0].isdigit():
        name = '_' + name
    # Add suffix if name is a common SQL keyword (case-insensitive)
    keywords = {
        'select', 'insert', 'update', 'delete', 'create', 'table',
        'where', 'from', 'index', 'order', 'group'
        # Add more keywords as needed
    }
    if name.lower() in keywords:
        name += '_col'
    # Ensure the name is not empty
    if not name:
        name = 'unnamed_col'
    return name


def map_dtype_to_sqlite(dtype):
    """Maps pandas dtype to a basic SQLite data type."""
    if pd.api.types.is_integer_dtype(dtype):
        return 'INTEGER'
    elif pd.api.types.is_float_dtype(dtype):
        return 'REAL'
    elif pd.api.types.is_bool_dtype(dtype):
        # SQLite doesn't have a native BOOLEAN, use INTEGER (0/1)
        return 'INTEGER'
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        # Store datetimes as TEXT in ISO format
        return 'TEXT'
    else:
        # Default to TEXT for strings, objects, etc.
        return 'TEXT'


def get_existing_schema(conn, table_name):
    """Retrieves the schema of an existing table. Returns dict or None."""
    sanitized_table_name = sanitize_name(table_name)
    cursor = conn.cursor()
    try:
        cursor.execute(f'PRAGMA table_info("{sanitized_table_name}");')
        columns_info = cursor.fetchall()
        if not columns_info:
            # Table doesn't exist or has no columns
            return None
        # Return a dictionary mapping column name to uppercase type
        return {info[1]: info[2].upper() for info in columns_info}
    except sqlite3.Error as e:
        logging.error("Error checking schema for table '%s': %s",
                      sanitized_table_name, e)
        return None


def infer_schema_from_csv(csv_file):
    """Infers schema from CSV. Returns schema dict, col definitions list."""
    if not os.path.exists(csv_file):
        logging.error("CSV file not found: %s", csv_file)
        print(f"Error: CSV file not found at '{csv_file}'")
        return None, None
    try:
        logging.info("Inferring schema from: %s", csv_file)
        # Read a sample to infer types, handle potential low memory issues
        df_sample = pd.read_csv(csv_file, nrows=100, low_memory=False)

        if df_sample.empty:
            # If even the sample is empty, try reading just headers
            df_sample = pd.read_csv(csv_file, nrows=0)
            if df_sample.empty:
                # If still empty (no headers), cannot infer schema
                logging.error("Cannot determine columns from empty CSV: %s",
                              csv_file)
                print(f"Error: Cannot read columns from empty CSV '{csv_file}'")
                return None, None
            # If headers exist but no rows, assume all TEXT
            inferred_schema = {
                sanitize_name(col): 'TEXT' for col in df_sample.columns
            }
            logging.warning(
                "CSV '%s' has headers only. Inferring all columns as TEXT.",
                csv_file
            )
        else:
            # Infer types from the sample data
            inferred_schema = {}
            for col_name in df_sample.columns:
                sanitized_col_name = sanitize_name(col_name)
                sqlite_type = map_dtype_to_sqlite(df_sample[col_name].dtype)
                inferred_schema[sanitized_col_name] = sqlite_type

        # Prepare column definitions for CREATE TABLE statement
        column_definitions = []
        pk_found = False
        for name, type_ in inferred_schema.items():
            col_def = f'"{name}" {type_}'
            # Basic primary key heuristic: 'id' column of type INTEGER
            if not pk_found and name.lower() == 'id' and type_ == 'INTEGER':
                col_def += ' PRIMARY KEY'
                pk_found = True
            column_definitions.append(col_def)

        logging.info("Inferred schema for %s: %s", csv_file, inferred_schema)
        return inferred_schema, column_definitions
    except Exception as e:
        logging.error("Error inferring schema for %s: %s",
                      csv_file, e, exc_info=True)
        print(f"An error occurred while reading the CSV schema: {e}")
        return None, None


def compare_schemas(inferred_schema, existing_schema):
    """Compares two schema dictionaries. Basic comparison."""
    if inferred_schema is None or existing_schema is None:
        return False
    # Check if column names match exactly
    if set(inferred_schema.keys()) != set(existing_schema.keys()):
        return False
    # Check if data types are compatible (basic check)
    for col_name, inferred_type in inferred_schema.items():
        # Normalize existing type (handle TEXT variants, INTEGER variants etc.)
        existing_type_base = existing_schema[col_name].split('(')[0].upper()
        if existing_type_base in ('VARCHAR', 'CHARACTER', 'NVARCHAR',
                                  'TEXT', 'CLOB'):
            existing_type_comparable = 'TEXT'
        elif existing_type_base in ('INT', 'INTEGER', 'TINYINT', 'SMALLINT',
                                    'MEDIUMINT', 'BIGINT', 'BOOLEAN'):
            existing_type_comparable = 'INTEGER'
        elif existing_type_base in ('REAL', 'FLOAT', 'DOUBLE', 'NUMERIC',
                                    'DECIMAL'):
            existing_type_comparable = 'REAL'
        else:
            existing_type_comparable = existing_type_base  # e.g., BLOB

        # Direct comparison after normalization
        if inferred_type != existing_type_comparable:
            return False
    return True


def create_dynamic_table(conn, table_name, column_definitions):
    """Creates a table dynamically."""
    sanitized_table_name = sanitize_name(table_name)
    cursor = conn.cursor()
    # Construct CREATE TABLE SQL statement
    create_sql = (
        f'CREATE TABLE "{sanitized_table_name}" (\n'
        + ",\n".join(f"  {col_def}" for col_def in column_definitions)
        + "\n);"
    )
    try:
        logging.info("Executing CREATE TABLE for '%s'. SQL: %s",
                     sanitized_table_name, create_sql)
        cursor.execute(create_sql)
        conn.commit()
        logging.info("Table '%s' created successfully.", sanitized_table_name)
        return True
    except sqlite3.Error as e:
        logging.error("Error creating table '%s': %s", sanitized_table_name, e)
        print(f"Error: Could not create table '{sanitized_table_name}': {e}")
        conn.rollback()  # Rollback changes on error
        return False


def drop_table(conn, table_name):
    """Drops the specified table."""
    sanitized_table_name = sanitize_name(table_name)
    cursor = conn.cursor()
    try:
        logging.warning("Dropping table '%s'...", sanitized_table_name)
        cursor.execute(f'DROP TABLE IF EXISTS "{sanitized_table_name}";')
        conn.commit()
        logging.info("Table '%s' dropped successfully.", sanitized_table_name)
        return True
    except sqlite3.Error as e:
        logging.error("Error dropping table '%s': %s", sanitized_table_name, e)
        print(f"Error: Could not drop table '{sanitized_table_name}': {e}")
        conn.rollback()
        return False


def load_csv_to_table(conn, csv_file, table_name, if_exists_strategy='append'):
    """Loads data from CSV into the specified table using pandas."""
    sanitized_table_name = sanitize_name(table_name)
    logging.info(
        "Attempting to load '%s' into '%s' (strategy: %s)",
        csv_file, sanitized_table_name, if_exists_strategy
    )
    try:
        # Read the entire CSV into a DataFrame
        df = pd.read_csv(csv_file, low_memory=False) # Added low_memory=False

        # Sanitize DataFrame column names to match table schema
        original_columns = df.columns.tolist()
        sanitized_columns = [sanitize_name(col) for col in original_columns]
        if original_columns != sanitized_columns:
            df.columns = sanitized_columns
            col_mapping = dict(zip(original_columns, sanitized_columns))
            logging.info("Renamed DataFrame columns for loading: %s",
                         col_mapping)

        # Use pandas.to_sql for efficient loading
        df.to_sql(sanitized_table_name, conn, if_exists=if_exists_strategy,
                  index=False, chunksize=1000)  # Use chunksize for large files
        conn.commit()

        # Verify row count after loading
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{sanitized_table_name}"')
        count = cursor.fetchone()[0]
        logging.info("Successfully loaded data. Table '%s' now has %d rows.",
                     sanitized_table_name, count)
        print(f"Successfully loaded {len(df)} rows into table "
              f"'{sanitized_table_name}'. Total rows: {count}.")
        return True
    except Exception as e:
        logging.error("Error loading CSV %s into %s: %s",
                      csv_file, sanitized_table_name, e, exc_info=True)
        print(f"Error: Failed to load data from '{csv_file}' into "
              f"'{sanitized_table_name}'. Check logs ({LOG_FILE}) for details.")
        conn.rollback()
        return False


def process_csv_file_interactive(conn, target_table_name, csv_file):
    """Handles processing for a CSV, including interactive conflict resolution."""
    logging.info("\n=== Processing CSV '%s' for table '%s' ===",
                 csv_file, target_table_name)
    print(f"\nProcessing '{csv_file}'...")

    # Infer schema from the CSV file
    inferred_schema, column_definitions = infer_schema_from_csv(csv_file)
    if not inferred_schema or not column_definitions:
        return None  # Error occurred during schema inference

    sanitized_target_name = sanitize_name(target_table_name)
    existing_schema = get_existing_schema(conn, sanitized_target_name)
    final_table_name = sanitized_target_name
    load_strategy = 'append'  # Default strategy if table exists

    if existing_schema:
        logging.info("Table '%s' exists. Comparing schemas.",
                     sanitized_target_name)
        if compare_schemas(inferred_schema, existing_schema):
            logging.info("Schemas match. Will append data by default.")
            print(f"Table '{sanitized_target_name}' exists and schema matches. "
                  "Data will be appended.")
            load_strategy = 'append'
        else:
            # Schema conflict
            logging.warning("Schema conflict detected for table '%s'!",
                            sanitized_target_name)
            print(f"\n! Schema conflict detected for table '{sanitized_target_name}'.")
            print(f"  Existing: {existing_schema}")
            print(f"  New CSV : {inferred_schema}")

            while True:
                action_prompt = (
                    "  Choose action: [O]verwrite table, "
                    "[A]ppend anyway (may fail), [R]ename new table, "
                    "[S]kip this file? "
                )
                choice = input(action_prompt).strip().upper()

                if choice == 'O':
                    logging.info("User chose: Overwrite.")
                    if drop_table(conn, sanitized_target_name):
                        if create_dynamic_table(conn, sanitized_target_name,
                                                column_definitions):
                            load_strategy = 'replace' # replace implies recreate
                            final_table_name = sanitized_target_name
                            print(f"Table '{sanitized_target_name}' will be "
                                  "overwritten.")
                            break
                        else:
                            # Failed to recreate table after dropping
                            final_table_name = None
                            break
                    else:
                        # Failed to drop table
                        final_table_name = None
                        break

                elif choice == 'A':
                    logging.info("User chose: Append anyway (schema mismatch).")
                    print("Warning: Appending data with mismatched schema "
                          "might lead to errors.")
                    load_strategy = 'append'
                    final_table_name = sanitized_target_name
                    break

                elif choice == 'R':
                    logging.info("User chose: Rename.")
                    while True:
                        new_name_base = input(
                            "  Enter a new base name for the table: "
                        ).strip()
                        if not new_name_base:
                            print("Name cannot be empty.")
                            continue

                        # Suggest a unique name using timestamp
                        ts = int(time.time())
                        potential_new_name = sanitize_name(f"{new_name_base}_{ts}")
                        print(f"  Suggested sanitized name: '{potential_new_name}'")

                        confirm_rename = input(
                            f"  Create table as '{potential_new_name}'? [Y/N] "
                        ).strip().upper()

                        if confirm_rename == 'Y':
                            # Check if this suggested name already exists
                            if get_existing_schema(conn, potential_new_name) is None:
                                final_table_name = potential_new_name
                                # Create the new table with the chosen name
                                if create_dynamic_table(conn, final_table_name,
                                                        column_definitions):
                                    load_strategy = 'replace' # Fresh table
                                    print("Data will be loaded into new table "
                                          f"'{final_table_name}'.")
                                    break # Exit inner rename loop
                                else:
                                    print(f"Error: Failed to create table "
                                          f"'{final_table_name}'. Please try "
                                          "again or choose another option.")
                                    # Stay in inner rename loop
                            else:
                                print(f"Error: Table '{potential_new_name}' "
                                      "already exists. Try a different base name.")
                                # Stay in inner rename loop
                        else:
                            print("Rename cancelled. Please choose O, A, R, "
                                  "or S again.")
                            # Break inner rename loop, go back to main choice
                            break
                    # If we successfully created/chose a renamed table, exit outer loop
                    if final_table_name == potential_new_name and load_strategy == 'replace':
                        break

                elif choice == 'S':
                    logging.info("User chose: Skip.")
                    print(f"Skipping file '{csv_file}'.")
                    final_table_name = None # Signal to skip loading
                    break # Exit choice loop

                else:
                    print("Invalid choice.")
                    # Repeat choice loop

    else:
        # Table does not exist, create it
        logging.info("Table '%s' does not exist. Creating.", sanitized_target_name)
        if create_dynamic_table(conn, sanitized_target_name, column_definitions):
            load_strategy = 'replace'  # Loading into a newly created table
            final_table_name = sanitized_target_name
            print(f"Created new table '{sanitized_target_name}'.")
        else:
            # Failed to create the table
            final_table_name = None

    # Proceed with loading data if a valid table name was determined
    if final_table_name:
        load_csv_to_table(conn, csv_file, final_table_name,
                          if_exists_strategy=load_strategy)
        return final_table_name # Return the name of the table used
    else:
        logging.warning("No data loaded for CSV '%s'.", csv_file)
        return None


def chatgpt_sql_prompt(user_query):
    """
    Sends the user's query to the OpenAI API to get a SQL query + explanation.
    """
    # Define instructions for the AI model
    system_instructions = """
You are an AI assistant tasked with converting user queries into SQL statements.
The database uses SQLite and contains the following tables:
- sample_2c (product_name, total_revenue)
Your task is to:
1. Generate a SQL query that accurately answers the user's question based on the provided table(s).
2. Ensure the SQL is compatible with standard SQLite syntax. Avoid database-specific functions unless necessary for SQLite.
3. Provide a short, clear comment explaining what the SQL query does.
Output Format:
SQL Query:
[Your generated SQL query here]
Explanation:
[Your brief explanation here]
"""

    messages = [
        {"role": "system", "content": system_instructions.strip()},
        {"role": "user", "content": user_query}
    ]

    try:
        logging.info("Sending query to OpenAI API: %s", user_query)
        completion = client.chat.completions.create(
            model="gpt-4o",  # Or your preferred model
            messages=messages,
            max_tokens=250,  # Adjust as needed
            temperature=0.0   # Low temperature for deterministic results
        )
        response_text = completion.choices[0].message.content.strip()
        logging.info("Raw API response: %s", response_text)

        # Clean up potential markdown code blocks
        cleaned_text = re.sub(r"```sql\n?", "", response_text)
        cleaned_text = re.sub(r"\n?```", "", cleaned_text).strip()
        logging.info("API response after markdown removal: %s", cleaned_text)

        # Parse the response based on the expected format
        if "Explanation:" not in cleaned_text:
            logging.error("Could not find 'Explanation:' delimiter in API response.")
            raise ValueError("Failed to parse response from API: "
                             "'Explanation:' delimiter not found.")

        parts = cleaned_text.split("Explanation:", 1) # Split only once
        if len(parts) < 2:
            logging.error("Splitting by 'Explanation:' resulted in < 2 parts.")
            raise ValueError("Failed to parse response from API after "
                             "splitting by 'Explanation:'")

        sql_query = parts[0].replace("SQL Query:", "").strip()
        explanation = parts[1].strip()

        if not sql_query:
             logging.warning("Parsed SQL query is empty.")
             # Decide if this should be an error or just return empty
             # raise ValueError("Parsed SQL query from API response is empty.")

        logging.info("Parsed SQL: %s", sql_query)
        logging.info("Parsed Explanation: %s", explanation)
        return sql_query, explanation

    except Exception as e:
        logging.error("Error communicating with or parsing OpenAI API response: %s",
                      e, exc_info=True)
        # Re-raise or handle as appropriate for the application flow
        raise ValueError(f"Error generating SQL via API: {e}")


def execute_sql_query(conn):
    """
    Prompts user for natural language query, gets SQL from API, executes it.
    """
    print("\nEnter your natural language query (or type 'cancel' to return):")
    user_input = input("> ").strip()

    if user_input.lower() == 'cancel':
        print("Query cancelled.")
        return

    if not user_input:
        print("Query cannot be empty.")
        return

    print("\nGenerating SQL query using ChatGPT API...")
    try:
        sql_query, explanation = chatgpt_sql_prompt(user_input)
        if not sql_query:
            print("\nWarning: The API returned an empty SQL query.")
            # Optionally ask user if they want to proceed or retry
            return

        print("\nGenerated SQL Query:")
        print(sql_query)
        print("\nExplanation:")
        print(explanation)

    except ValueError as e:
        # Catch specific error from API communication/parsing
        print(f"\nError: {e}")
        return
    except Exception as e:
        # Catch unexpected errors during API call
        logging.error("Unexpected error getting SQL from API: %s", e, exc_info=True)
        print(f"\nError: Failed to generate SQL query from the API. {e}")
        return

    # Confirmation before execution (optional but recommended)
    confirm_exec = input("Execute this query? [Y/N]: ").strip().upper()
    if confirm_exec != 'Y':
        print("Execution cancelled by user.")
        logging.info("User cancelled execution of query: %s", sql_query)
        return

    cursor = conn.cursor()
    try:
        start_time = time.time()
        logging.info("Executing user-confirmed generated SQL: %s", sql_query)
        cursor.execute(sql_query)

        # Check if the query was a SELECT statement (has results)
        if cursor.description:
            results = cursor.fetchall()
            if results:
                col_names = [desc[0] for desc in cursor.description]
                # Format header
                header = " | ".join(col_names)
                separator = "-" * len(header)
                print("\nQuery Results:")
                print(header)
                print(separator)
                # Print rows (limit output for display)
                MAX_ROWS_DISPLAY = 50
                for i, row in enumerate(results):
                    if i >= MAX_ROWS_DISPLAY:
                        print(f"... (showing first {MAX_ROWS_DISPLAY} "
                              f"of {len(results)} rows)")
                        break
                    # Truncate long cell values for display
                    display_row = []
                    for col in row:
                        col_str = str(col)
                        if len(col_str) > 50:
                             display_row.append(col_str[:47] + '...')
                        else:
                             display_row.append(col_str)
                    print(" | ".join(display_row))

            else:
                print("\nQuery executed successfully, but returned no results.")
        else:
            # Query was likely an INSERT, UPDATE, DELETE, CREATE, etc.
            conn.commit() # Commit changes for non-SELECT queries
            rows_affected = cursor.rowcount
            print("\nQuery executed successfully.")
            # rowcount is -1 for non-DML statements or if not applicable
            if rows_affected != -1:
                print(f"{rows_affected} rows affected.")

        end_time = time.time()
        duration = end_time - start_time
        logging.info("Query executed successfully in %.3f seconds. Rows affected/returned: %s",
                     duration, len(results) if cursor.description else rows_affected)

    except sqlite3.Error as e:
        logging.error("Error executing generated query '%s': %s",
                      sql_query, e, exc_info=True)
        print(f"\nError executing the generated SQL query: {e}")
        conn.rollback() # Rollback any potential changes from the failed query


def list_tables(conn):
    """Lists user tables in the database."""
    cursor = conn.cursor()
    try:
        # Query sqlite_master to find tables, excluding sqlite internal tables
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()
        if not tables:
            print("\nNo user tables found in the database.")
        else:
            print("\nTables in database:")
            for table in tables:
                print(f"- {table[0]}")
    except sqlite3.Error as e:
        logging.error("Error listing tables: %s", e)
        print(f"Error: Could not list tables: {e}")


def connect_db(db_file):
    """Creates a connection to the SQLite database."""
    try:
        # Connect, enabling foreign key constraints if needed (optional)
        # conn = sqlite3.connect(db_file, detect_types=sqlite3.PARSE_DECLTYPES)
        # conn.execute("PRAGMA foreign_keys = ON")
        conn = sqlite3.connect(db_file)
        logging.info("Successfully connected to database: %s", db_file)
        return conn
    except sqlite3.Error as e:
        logging.error("Error connecting to database %s: %s",
                      db_file, e, exc_info=True)
        print(f"FATAL ERROR: Could not connect to database '{db_file}'. "
              "Exiting.")
        return None


# --- Configuration ---
DB_FILE = 'my_project_step4.db'
LOG_FILE = 'error_log_step4.txt'


def run_cli():
    """Runs the main command-line interface loop."""
    setup_logging(LOG_FILE)
    conn = connect_db(DB_FILE)

    if not conn:
        return # Exit if database connection failed

    print("\n--- Simple DB Interaction CLI ---")
    print(f"Connected to: {DB_FILE}")
    print(f"Logging to: {LOG_FILE}")

    try:
        while True:
            print("\nOptions:")
            print("  1. Load CSV file into database")
            print("  2. List tables")
            print("  3. Run natural language query (via OpenAI API)")
            print("  4. Exit")
            choice = input("Enter your choice: ").strip()

            if choice == '1':
                csv_path = input("Enter the path to the CSV file: ").strip()
                if not os.path.exists(csv_path):
                    print(f"Error: File not found at '{csv_path}'")
                    logging.warning("User provided non-existent CSV path: %s",
                                    csv_path)
                    continue
                if not csv_path.lower().endswith(".csv"):
                    print("Warning: File does not end with .csv. Proceeding anyway.")
                    logging.warning("User provided non-csv file path: %s", csv_path)

                # Suggest table name based on CSV filename
                base_name = os.path.splitext(os.path.basename(csv_path))[0]
                suggested_name = sanitize_name(base_name)
                table_name_prompt = (
                    "Enter target table name (suggestion: "
                    f"'{suggested_name}'): "
                )
                table_name = input(table_name_prompt).strip()

                # Use suggestion if user enters nothing
                if not table_name:
                    table_name = suggested_name

                # Final check for a valid (non-empty after sanitize) name
                if not sanitize_name(table_name): # Re-sanitize just in case
                    print("Error: Invalid table name provided.")
                    logging.warning("Invalid table name ('%s') resulted in empty "
                                    "sanitized name.", table_name)
                    continue

                # Process the CSV, handling potential table conflicts
                process_csv_file_interactive(conn, table_name, csv_path)

            elif choice == '2':
                list_tables(conn)

            elif choice == '3':
                execute_sql_query(conn)

            elif choice == '4':
                print("Exiting application.")
                logging.info("--- CLI Application Exited ---")
                break

            else:
                print("Invalid choice, please try again.")

    except KeyboardInterrupt:
        print("\nExiting due to keyboard interrupt.")
        logging.warning("Application terminated by KeyboardInterrupt.")
    except Exception as e:
        # Catch-all for unexpected errors in the main loop
        logging.critical("An unexpected error occurred in the main CLI loop: %s",
                         e, exc_info=True)
        print(f"\nAn unexpected critical error occurred: {e}. Check logs.")
    finally:
        # Ensure database connection is closed properly
        if conn:
            conn.close()
            logging.info("Database connection closed.")
            print("Database connection closed.")


if __name__ == "__main__":
    run_cli()
