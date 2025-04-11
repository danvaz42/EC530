import sqlite3
import pandas as pd
import os
import re
import logging
import time
from openai import OpenAI

client = OpenAI(api_key='insert key')


def setup_logging(log_file):
    """Configures logging to file and console."""
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
    logging.getLogger('pandas').setLevel(logging.WARNING)
    logging.info("--- CLI Application Started ---")
    logging.info("Using database: %s", DB_FILE)
    logging.info("Logging to: %s", log_file)


def sanitize_name(name):
    """Sanitizes table or column names for safe use in SQL."""
    name = str(name).strip()
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if name and name[0].isdigit():
        name = '_' + name
    keywords = {
        'select', 'insert', 'update', 'delete', 'create', 'table',
        'where', 'from', 'index', 'order', 'group'
    }
    if name.lower() in keywords:
        name += '_col'
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
        return 'INTEGER'
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return 'TEXT'
    else:
        return 'TEXT'


def get_existing_schema(conn, table_name):
    """Retrieves the schema of an existing table. Returns dict or None."""
    sanitized_table_name = sanitize_name(table_name)
    cursor = conn.cursor()
    try:
        cursor.execute(f'PRAGMA table_info("{sanitized_table_name}");')
        columns_info = cursor.fetchall()
        if not columns_info:
            return None
        return {info[1]: info[2].upper() for info in columns_info}
    except sqlite3.Error as e:
        logging.error("Error checking schema for table '%s': %s",
                      sanitized_table_name, e)
        return None


def infer_schema_from_csv(csv_file):
    """Infers schema from CSV. Returns schema dict and column definitions list."""
    if not os.path.exists(csv_file):
        logging.error("CSV file not found: %s", csv_file)
        print("Error: CSV file not found at '%s'" % csv_file)
        return None, None
    try:
        logging.info("Inferring schema from: %s", csv_file)
        df_sample = pd.read_csv(csv_file, nrows=100, low_memory=False)
        if df_sample.empty:
            df_sample = pd.read_csv(csv_file, nrows=0)
            if df_sample.empty:
                logging.error("Cannot determine columns from empty CSV: %s", csv_file)
                print("Error: Cannot read columns from empty CSV '%s'" % csv_file)
                return None, None
            inferred_schema = {sanitize_name(col): 'TEXT' for col in df_sample.columns}
            logging.warning("CSV '%s' has headers only. Inferring all columns as TEXT.",
                            csv_file)
        else:
            inferred_schema = {}
            for col_name in df_sample.columns:
                sanitized_col_name = sanitize_name(col_name)
                sqlite_type = map_dtype_to_sqlite(df_sample[col_name].dtype)
                inferred_schema[sanitized_col_name] = sqlite_type

        column_definitions = []
        pk_found = False
        for name, type_ in inferred_schema.items():
            col_def = f'"{name}" {type_}'
            if not pk_found and name.lower() == 'id' and type_ == 'INTEGER':
                col_def += ' PRIMARY KEY'
                pk_found = True
            column_definitions.append(col_def)
        logging.info("Inferred schema for %s: %s", csv_file, inferred_schema)
        return inferred_schema, column_definitions
    except Exception as e:
        logging.error("Error inferring schema for %s: %s", csv_file, e, exc_info=True)
        print("An error occurred while reading the CSV schema: %s" % e)
        return None, None


def compare_schemas(inferred_schema, existing_schema):
    """Compares two schema dictionaries. Basic comparison."""
    if inferred_schema is None or existing_schema is None:
        return False
    if set(inferred_schema.keys()) != set(existing_schema.keys()):
        return False
    for col_name, inferred_type in inferred_schema.items():
        existing_type_base = existing_schema[col_name].split('(')[0].upper()
        if existing_type_base in ('VARCHAR', 'CHARACTER', 'NVARCHAR', 'TEXT', 'CLOB'):
            existing_type_comparable = 'TEXT'
        elif existing_type_base in (
            'INT', 'INTEGER', 'TINYINT', 'SMALLINT', 'MEDIUMINT', 'BIGINT', 'BOOLEAN'
        ):
            existing_type_comparable = 'INTEGER'
        elif existing_type_base in ('REAL', 'FLOAT', 'DOUBLE', 'NUMERIC', 'DECIMAL'):
            existing_type_comparable = 'REAL'
        else:
            existing_type_comparable = existing_type_base
        if inferred_type != existing_type_comparable:
            return False
    return True


def create_dynamic_table(conn, table_name, column_definitions):
    """Creates a table dynamically."""
    sanitized_table_name = sanitize_name(table_name)
    cursor = conn.cursor()
    create_sql = (
        f'CREATE TABLE "{sanitized_table_name}" (\n'
        + ",\n".join(column_definitions)
        + "\n);"
    )
    try:
        logging.info("Executing CREATE TABLE for '%s'.", sanitized_table_name)
        cursor.execute(create_sql)
        conn.commit()
        logging.info("Table '%s' created.", sanitized_table_name)
        return True
    except sqlite3.Error as e:
        logging.error("Error creating table '%s': %s", sanitized_table_name, e)
        print("Error: Could not create table '%s': %s" %
              (sanitized_table_name, e))
        conn.rollback()
        return False


def drop_table(conn, table_name):
    """Drops the specified table."""
    sanitized_table_name = sanitize_name(table_name)
    cursor = conn.cursor()
    try:
        logging.warning("Dropping table '%s'...", sanitized_table_name)
        cursor.execute(f'DROP TABLE IF EXISTS "{sanitized_table_name}";')
        conn.commit()
        logging.info("Table '%s' dropped.", sanitized_table_name)
        return True
    except sqlite3.Error as e:
        logging.error("Error dropping table '%s': %s", sanitized_table_name, e)
        print("Error: Could not drop table '%s': %s" %
              (sanitized_table_name, e))
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
        df = pd.read_csv(csv_file)
        original_columns = df.columns.tolist()
        sanitized_columns = [sanitize_name(col) for col in original_columns]
        if original_columns != sanitized_columns:
            df.columns = sanitized_columns
            logging.info("Renamed DataFrame columns for loading: %s",
                         dict(zip(original_columns, sanitized_columns)))

        df.to_sql(sanitized_table_name, conn, if_exists=if_exists_strategy,
                  index=False, chunksize=1000)
        conn.commit()
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{sanitized_table_name}"')
        count = cursor.fetchone()[0]
        logging.info("Successfully loaded data. Table '%s' now has %s rows.",
                     sanitized_table_name, count)
        print("Successfully loaded %s rows into table '%s'. Total rows: %s." %
              (len(df), sanitized_table_name, count))
        return True
    except Exception as e:
        logging.error("Error loading CSV %s into %s: %s",
                      csv_file, sanitized_table_name, e, exc_info=True)
        print("Error: Failed to load data from '%s' into '%s'. Check logs (%s) for details." %
              (csv_file, sanitized_table_name, LOG_FILE))
        conn.rollback()
        return False


def process_csv_file_interactive(conn, target_table_name, csv_file):
    """Handles processing for a single CSV file, including interactive conflict resolution."""
    logging.info("\n=== Processing CSV '%s' for table '%s' ===",
                 csv_file, target_table_name)
    print("\nProcessing '%s'..." % csv_file)

    inferred_schema, column_definitions = infer_schema_from_csv(csv_file)
    if not inferred_schema:
        return None

    sanitized_target_name = sanitize_name(target_table_name)
    existing_schema = get_existing_schema(conn, sanitized_target_name)
    final_table_name = sanitized_target_name
    load_strategy = 'append'

    if existing_schema:
        logging.info("Table '%s' exists. Comparing schemas.",
                     sanitized_target_name)
        if compare_schemas(inferred_schema, existing_schema):
            logging.info("Schemas match. Will append data by default.")
            print("Table '%s' exists and schema matches. Data will be appended." %
                  sanitized_target_name)
            load_strategy = 'append'
        else:
            logging.warning("Schema conflict detected for table '%s'!",
                            sanitized_target_name)
            print("\n! Schema conflict detected for table '%s'." %
                  sanitized_target_name)
            print("  Existing: %s" % existing_schema)
            print("  New CSV : %s" % inferred_schema)
            while True:
                choice = input(
                    "  Choose action: [O]verwrite table, "
                    "[A]ppend anyway (may fail), [R]ename new table, [S]kip this file? "
                ).strip().upper()
                if choice == 'O':
                    logging.info("User chose: Overwrite.")
                    if drop_table(conn, sanitized_target_name):
                        if create_dynamic_table(conn, sanitized_target_name, column_definitions):
                            load_strategy = 'replace'
                            final_table_name = sanitized_target_name
                            print("Table '%s' will be overwritten." %
                                  sanitized_target_name)
                            break
                        else:
                            final_table_name = None
                            break
                    else:
                        final_table_name = None
                        break
                elif choice == 'A':
                    logging.info("User chose: Append anyway (schema mismatch).")
                    print("Warning: Appending data with mismatched schema might lead to errors.")
                    load_strategy = 'append'
                    final_table_name = sanitized_target_name
                    break
                elif choice == 'R':
                    logging.info("User chose: Rename.")
                    while True:
                        new_name_base = input("  Enter a new base name for the table: ").strip()
                        if not new_name_base:
                            print("Name cannot be empty.")
                            continue
                        potential_new_name = sanitize_name(
                            f"{new_name_base}_{int(time.time())}"
                        )
                        print("  Suggested sanitized name: '%s'" % potential_new_name)
                        confirm_rename = input(
                            "  Create table as '%s'? [Y/N] " % potential_new_name
                        ).strip().upper()
                        if confirm_rename == 'Y':
                            if get_existing_schema(conn, potential_new_name) is None:
                                final_table_name = potential_new_name
                                if create_dynamic_table(conn, final_table_name, column_definitions):
                                    load_strategy = 'replace'
                                    print("Data will be loaded into new table '%s'." %
                                          final_table_name)
                                    break
                                else:
                                    print("Error: Failed to create table '%s'. "
                                          "Please try again or choose another option." %
                                          final_table_name)
                            else:
                                print("Error: Table '%s' already exists. Try a different base name." %
                                      potential_new_name)
                        else:
                            print("Rename cancelled. Please choose O, A, R, or S again.")
                            break
                    if final_table_name == potential_new_name:
                        break
                elif choice == 'S':
                    logging.info("User chose: Skip.")
                    print("Skipping file '%s'." % csv_file)
                    final_table_name = None
                    break
                else:
                    print("Invalid choice.")
    else:
        logging.info("Table '%s' does not exist. Creating.", sanitized_target_name)
        if create_dynamic_table(conn, sanitized_target_name, column_definitions):
            load_strategy = 'replace'
            final_table_name = sanitized_target_name
            print("Created new table '%s'." % sanitized_target_name)
        else:
            final_table_name = None

    if final_table_name:
        load_csv_to_table(conn, csv_file, final_table_name,
                          if_exists_strategy=load_strategy)
        return final_table_name
    else:
        logging.warning("No data loaded for CSV '%s'.", csv_file)
        return None


def chatgpt_sql_prompt(user_query):
    """
    Sends the user's natural language query to the ChatGPT API using the new interface.
    It returns the generated SQL query along with a short explanation.
    """
    system_instructions = (
        "You are an AI assistant tasked with converting user queries into SQL statements. "
        "The database uses SQLite and contains the following tables:\n"
        "- sample_2c (product_name, total_revenue)\n"
        "Your task is to:\n"
        "1. Generate a SQL query that accurately answers the user's question.\n"
        "2. Ensure the SQL is compatible with SQLite syntax.\n"
        "3. Provide a short comment explaining what the query does.\n"
        "Output Format:\n"
        "- SQL Query\n"
        "- Explanation"
    )

    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_query}
    ]

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=250,
        temperature=0
    )

    text = completion.choices[0].message.content.strip()
    text = text.replace("```sql", "").replace("```", "").strip()
    logging.info("Raw API response text after markdown removal: %s", text)

    if "Explanation:" not in text:
        raise ValueError(
            "Failed to parse response from ChatGPT API: 'Explanation:' delimiter not found."
        )

    parts = text.split("Explanation:")
    if len(parts) < 2:
        raise ValueError(
            "Failed to parse response from ChatGPT API after splitting by 'Explanation:'"
        )

    sql_query = parts[0].replace("SQL Query:", "").strip()
    explanation = parts[1].strip()
    return sql_query, explanation


def execute_sql_query(conn):
    """
    Prompts the user for a natural language query, sends it to the ChatGPT API
    to generate a SQL query plus an explanation, displays the output,
    and then executes the SQL.
    """
    print("\nEnter your natural language query (or type 'cancel' to return):")
    user_input = input("> ").strip()

    if user_input.lower() == 'cancel':
        print("Query cancelled.")
        return

    print("\nGenerating SQL query using ChatGPT API...")
    try:
        sql_query, explanation = chatgpt_sql_prompt(user_input)
        print("\nGenerated SQL Query:")
        print(sql_query)
        print("\nExplanation:")
        print(explanation)
    except Exception as e:
        logging.error("Error getting SQL from ChatGPT API: %s", e, exc_info=True)
        print("\nError: Failed to generate SQL query from the ChatGPT API. %s" % e)
        return

    cursor = conn.cursor()
    try:
        start_time = time.time()
        logging.info("Executing generated SQL query: %s", sql_query)
        cursor.execute(sql_query)
        if cursor.description:
            results = cursor.fetchall()
            if results:
                col_names = [desc[0] for desc in cursor.description]
                print("\nQuery Results:")
                print(" | ".join(col_names))
                print("-" * (sum(len(name) for name in col_names) +
                             3 * (len(col_names) - 1)))
                for row in results[:50]:
                    display_row = [
                        str(col)[:50] + '...' if len(str(col)) > 50 else str(col)
                        for col in row
                    ]
                    print(" | ".join(display_row))
                if len(results) > 50:
                    print("... (showing first 50 of %s rows)" % len(results))
            else:
                print("\nQuery executed successfully, but returned no results.")
        else:
            conn.commit()
            rows_affected = cursor.rowcount
            print("\nQuery executed successfully.")
            if rows_affected != -1:
                print("%s rows affected." % rows_affected)
        end_time = time.time()
        logging.info("Query executed successfully in %.3f seconds.",
                     end_time - start_time)
    except sqlite3.Error as e:
        logging.error("Error executing generated query: %s", e, exc_info=True)
        print("\nError executing the generated SQL query: %s" % e)
        conn.rollback()


def list_tables(conn):
    """Lists user tables in the database."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()
        if not tables:
            print("\nNo user tables found in the database.")
        else:
            print("\nTables in database:")
            for table in tables:
                print("- %s" % table[0])
    except sqlite3.Error as e:
        logging.error("Error listing tables: %s", e)
        print("Error: Could not list tables: %s" % e)


def connect_db(db_file):
    """Creates a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(db_file)
        logging.info("Successfully connected to database: %s", db_file)
        return conn
    except sqlite3.Error as e:
        logging.error("Error connecting to database %s: %s", db_file, e, exc_info=True)
        print("FATAL ERROR: Could not connect to database '%s'. Exiting." % db_file)
        return None


DB_FILE = 'my_project_step4.db'
LOG_FILE = 'error_log_step4.txt'


def run_cli():
    """Runs the main command-line interface loop."""
    setup_logging(LOG_FILE)
    conn = connect_db(DB_FILE)

    if not conn:
        return

    print("\n--- Simple DB Interaction CLI ---")
    print("Connected to: %s" % DB_FILE)
    print("Logging to: %s" % LOG_FILE)

    try:
        while True:
            print("\nOptions:")
            print("  1. Load CSV file into database")
            print("  2. List tables")
            print("  3. Run natural language query (via ChatGPT)")
            print("  4. Exit")
            choice = input("Enter your choice: ").strip()

            if choice == '1':
                csv_path = input("Enter the path to the CSV file: ").strip()
                if not os.path.exists(csv_path):
                    print("Error: File not found at '%s'" % csv_path)
                    logging.warning("User provided non-existent CSV path: %s", csv_path)
                    continue

                suggested_name = sanitize_name(os.path.splitext(os.path.basename(csv_path))[0])
                table_name = input("Enter target table name (suggestion: '%s'): " %
                                    suggested_name).strip()
                if not table_name:
                    table_name = suggested_name
                if not table_name:
                    print("Error: Invalid table name.")
                    logging.warning("Invalid table name provided by user.")
                    continue

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
        logging.critical("An unexpected error occurred in the main CLI loop: %s", e, exc_info=True)
        print("\nAn unexpected critical error occurred: %s. Check logs." % e)
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")
            print("Database connection closed.")


if __name__ == "__main__":
    run_cli()
