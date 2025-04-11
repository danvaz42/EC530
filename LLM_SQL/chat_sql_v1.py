import sqlite3
import pandas as pd
import os
import re
import logging
import time
from openai import OpenAI

# Replace 'insert key' with your actual OpenAI API key
# Consider using environment variables for security
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "insert_key_here"))


def setup_logging(log_file):
    """Configures logging to file and console."""
    for handler in logging.root.handlers[:]:  # Remove existing handlers
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="a"),
            logging.StreamHandler()
        ]
    )
    logging.getLogger("pandas").setLevel(logging.WARNING)  # Reduce pandas logging noise
    logging.info("--- CLI Application Started ---")


def sanitize_name(name):
    """Sanitizes table or column names for safe use in SQL."""
    name = str(name).strip()
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)  # Replace non-alphanumeric chars
    if name and name[0].isdigit():  # Prepend underscore if name starts with a digit
        name = "_" + name
    keywords = {
        "select", "insert", "update", "delete", "create", "table",
        "where", "from", "index", "order", "group"
    }
    if name.lower() in keywords:  # Add suffix if name is SQL keyword
        name += "_col"
    return name or "unnamed_col"  # Ensure name is not empty


def map_dtype_to_sqlite(dtype):
    """Maps pandas dtype to a basic SQLite data type."""
    if pd.api.types.is_integer_dtype(dtype):
        return "INTEGER"
    if pd.api.types.is_float_dtype(dtype):
        return "REAL"
    if pd.api.types.is_bool_dtype(dtype):
        return "INTEGER"  # SQLite doesn't have a native BOOLEAN
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "TEXT"  # Store datetimes as TEXT in ISO format
    return "TEXT"  # Default to TEXT for strings, objects, etc.


def get_existing_schema(conn, table_name):
    """Retrieves the schema of an existing table. Returns dict or None."""
    sanitized_table_name = sanitize_name(table_name)
    cursor = conn.cursor()
    try:
        cursor.execute(f'PRAGMA table_info("{sanitized_table_name}");')
        columns_info = cursor.fetchall()
        if not columns_info:
            return None  # Table doesn't exist or has no columns
        return {info[1]: info[2].upper() for info in columns_info}
    except sqlite3.Error as e:
        logging.error("Error checking schema for table '%s': %s", sanitized_table_name, e)
        return None


def infer_schema_from_csv(csv_file):
    """Infers schema from CSV. Returns schema dict, col definitions list."""
    if not os.path.exists(csv_file):
        logging.error("CSV file not found: %s", csv_file)
        print(f"Error: CSV file not found at '{csv_file}'")
        return None, None
    try:
        logging.info("Inferring schema from: %s", csv_file)
        df_sample = pd.read_csv(csv_file, nrows=100, low_memory=False)  # Read sample
        if df_sample.empty:
            df_sample = pd.read_csv(csv_file, nrows=0)  # Try reading just headers
            if df_sample.empty:
                logging.error("Cannot determine columns from empty CSV: %s", csv_file)
                print(f"Error: Cannot read columns from empty CSV '{csv_file}'")
                return None, None
            inferred_schema = {sanitize_name(col): "TEXT" for col in df_sample.columns}
            logging.warning(
                "CSV '%s' has headers only. Inferring all columns as TEXT.", csv_file
            )
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
            if not pk_found and name.lower() == "id" and type_ == "INTEGER":
                col_def += " PRIMARY KEY"
                pk_found = True
            column_definitions.append(col_def)

        logging.info("Inferred schema for %s: %s", csv_file, inferred_schema)
        return inferred_schema, column_definitions
    except Exception as e:
        logging.error("Error inferring schema for %s: %s", csv_file, e, exc_info=True)
        print(f"An error occurred while reading the CSV schema: {e}")
        return None, None


def compare_schemas(inferred_schema, existing_schema):
    """Compares two schema dictionaries. Basic comparison."""
    if not inferred_schema or not existing_schema:
        return False
    if set(inferred_schema.keys()) != set(existing_schema.keys()):  # Compare columns
        return False
    for col_name, inferred_type in inferred_schema.items():
        existing_type_base = existing_schema[col_name].split("(")[0].upper()
        existing_type_comparable = (
            "TEXT" if existing_type_base in ("VARCHAR", "CHARACTER", "CLOB")
            else "INTEGER" if existing_type_base in ("INT", "BIGINT", "BOOLEAN")
            else "REAL" if existing_type_base in ("REAL", "FLOAT", "DOUBLE")
            else existing_type_base
        )
        if inferred_type != existing_type_comparable:
            logging.info(
                "Schema mismatch on column '%s': Inferred '%s', "
                "Existing '%s' (normalized to '%s')",
                col_name, inferred_type, existing_schema[col_name], existing_type_comparable
            )
            return False
    return True
