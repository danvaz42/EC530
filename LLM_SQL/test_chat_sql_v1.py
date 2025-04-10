import os
import sys
import sqlite3
import pandas as pd
import pytest

# Add the EC530/LLM_SQL directory to the system path so we can import chat_sql_v1
repo_root = os.path.dirname(os.path.abspath(__file__))
module_path = os.path.join(repo_root, "EC530", "LLM_SQL")
if module_path not in sys.path:
    sys.path.insert(0, module_path)

from chat_sql_v1 import (
    sanitize_name,
    map_dtype_to_sqlite,
    compare_schemas,
    infer_schema_from_csv,
    create_dynamic_table,
    drop_table,
    load_csv_to_table,
    get_existing_schema,
    chatgpt_sql_prompt,
    client
)

# --- Test sanitize_name ---
def test_sanitize_name():
    assert sanitize_name("example") == "example"
    # Reserved keyword should get a suffix.
    assert sanitize_name("select") == "select_col"
    # Names that start with a digit are prefixed with an underscore.
    assert sanitize_name("123table") == "_123table"
    # Replace spaces and special characters.
    assert sanitize_name("my table!") == "my_table_"
    # Empty name should become 'unnamed_col'
    assert sanitize_name("") == "unnamed_col"

# --- Test map_dtype_to_sqlite ---
def test_map_dtype_to_sqlite():
    int_series = pd.Series([1, 2, 3])
    assert map_dtype_to_sqlite(int_series.dtype) == "INTEGER"

    float_series = pd.Series([1.0, 2.5, 3.3])
    assert map_dtype_to_sqlite(float_series.dtype) == "REAL"

    bool_series = pd.Series([True, False])
    assert map_dtype_to_sqlite(bool_series.dtype) == "INTEGER"

    datetime_series = pd.Series(pd.date_range("2021-01-01", periods=3))
    assert map_dtype_to_sqlite(datetime_series.dtype) == "TEXT"

    str_series = pd.Series(["a", "b", "c"])
    assert map_dtype_to_sqlite(str_series.dtype) == "TEXT"

# --- Test compare_schemas ---
def test_compare_schemas():
    # Matching schemas.
    schema1 = {"id": "INTEGER", "name": "TEXT"}
    schema2 = {"id": "INTEGER", "name": "TEXT"}
    assert compare_schemas(schema1, schema2) is True

    # Mismatched type.
    schema3 = {"id": "INTEGER", "name": "REAL"}
    assert compare_schemas(schema1, schema3) is False

    # Different columns.
    schema4 = {"id": "INTEGER"}
    assert compare_schemas(schema1, schema4) is False

    # One schema is None.
    assert compare_schemas(schema1, None) is False

# --- Test infer_schema_from_csv ---
def test_infer_schema_from_csv(tmp_path):
    # Create a temporary CSV file.
    csv_content = "id,name,score\n1,Alice,85.5\n2,Bob,92.0"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)
    
    inferred_schema, column_definitions = infer_schema_from_csv(str(csv_file))
    
    # After sanitization, the column names should be "id", "name", "score".
    expected_schema = {"id": "INTEGER", "name": "TEXT", "score": "REAL"}
    assert inferred_schema == expected_schema

    # 'id' should have been given a PRIMARY KEY designation.
    expected_columns = ['"id" INTEGER PRIMARY KEY', '"name" TEXT', '"score" REAL']
    assert column_definitions == expected_columns

# --- Test create_dynamic_table and drop_table ---
def test_create_and_drop_table():
    conn = sqlite3.connect(":memory:")
    table_name = "test_table"
    column_definitions = ['"id" INTEGER PRIMARY KEY', '"value" TEXT']
    
    # Create the table.
    assert create_dynamic_table(conn, table_name, column_definitions) is True
    
    schema = get_existing_schema(conn, table_name)
    assert schema is not None
    assert "id" in schema
    assert "value" in schema

    # Drop the table.
    assert drop_table(conn, table_name) is True
    assert get_existing_schema(conn, table_name) is None
    conn.close()

# --- Test load_csv_to_table ---
def test_load_csv_to_table(tmp_path):
    csv_content = "id,name\n1,Alice\n2,Bob\n3,Charlie"
    csv_file = tmp_path / "test_load.csv"
    csv_file.write_text(csv_content)

    conn = sqlite3.connect(":memory:")
    table_name = "load_table"
    
    # Use 'replace' strategy to ensure table creation.
    result = load_csv_to_table(conn, str(csv_file), table_name, if_exists_strategy="replace")
    assert result is True

    cursor = conn.cursor()
    # Ensure the table name is sanitized before querying.
    sanitized_name = sanitize_name(table_name)
    cursor.execute(f'SELECT COUNT(*) FROM "{sanitized_name}"')
    count = cursor.fetchone()[0]
    assert count == 3
    conn.close()

# --- Test chatgpt_sql_prompt with a fake API response ---
def test_chatgpt_sql_prompt(monkeypatch):
    # Define fake response classes.
    class FakeMessage:
        def __init__(self, content):
            self.content = content

    class FakeChoice:
        def __init__(self, message):
            self.message = message

    class FakeResponse:
        def __init__(self, choices):
            self.choices = choices

    # Fake create function to simulate a ChatGPT API response.
    def fake_create(*args, **kwargs):
        fake_content = (
            "SQL Query: SELECT * FROM sample_2c; "
            "Explanation: This query retrieves all rows from the sample_2c table."
        )
        return FakeResponse(choices=[FakeChoice(FakeMessage(fake_content))])

    monkeypatch.setattr(client.chat.completions, "create", fake_create)
    sql_query, explanation = chatgpt_sql_prompt("get all rows")
    assert "SELECT * FROM sample_2c" in sql_query
    assert "retrieves" in explanation
