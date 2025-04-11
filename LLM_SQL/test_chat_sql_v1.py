import sqlite3
import pandas as pd
import pytest  # Re-added for pytest.raises

# Since this file sits alongside chat_sql_v1.py, we can import directly.
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
    client  # Assuming client might be needed for mocking setup later
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
    # Handle None or other types gracefully
    assert sanitize_name(None) == "None"  # Or decide expected behavior
    assert sanitize_name(123) == "_123"


# --- Test map_dtype_to_sqlite ---
def test_map_dtype_to_sqlite():
    int_series = pd.Series([1, 2, 3], dtype='int64')
    assert map_dtype_to_sqlite(int_series.dtype) == "INTEGER"

    float_series = pd.Series([1.0, 2.5, 3.3], dtype='float64')
    assert map_dtype_to_sqlite(float_series.dtype) == "REAL"

    bool_series = pd.Series([True, False], dtype='bool')
    assert map_dtype_to_sqlite(bool_series.dtype) == "INTEGER"

    datetime_series = pd.Series(pd.to_datetime(["2021-01-01", "2022-02-02"]))
    assert map_dtype_to_sqlite(datetime_series.dtype) == "TEXT"

    # Use pandas string dtype if available, otherwise object
    try:
        str_series = pd.Series(["a", "b", "c"], dtype='string')
    except TypeError:
        str_series = pd.Series(["a", "b", "c"], dtype='object')
    assert map_dtype_to_sqlite(str_series.dtype) == "TEXT"

    object_series = pd.Series(["a", 1, None], dtype='object')  # Mixed types
    assert map_dtype_to_sqlite(object_series.dtype) == "TEXT"


# --- Test compare_schemas ---
def test_compare_schemas():
    # Matching schemas.
    schema1 = {"id": "INTEGER", "name": "TEXT"}
    schema2 = {"id": "INTEGER", "name": "TEXT"}
    assert compare_schemas(schema1, schema2) is True

    # Matching schemas with different case/SQLite type variations.
    schema1_alt = {"id": "INT", "name": "VARCHAR(100)"}
    assert compare_schemas(schema1, schema1_alt) is True

    # Mismatched type.
    schema3 = {"id": "INTEGER", "name": "REAL"}
    assert compare_schemas(schema1, schema3) is False

    # Different columns.
    schema4 = {"id": "INTEGER"}
    assert compare_schemas(schema1, schema4) is False
    schema5 = {"id": "INTEGER", "name": "TEXT", "extra": "REAL"}
    assert compare_schemas(schema1, schema5) is False

    # One schema is None.
    assert compare_schemas(schema1, None) is False
    assert compare_schemas(None, schema2) is False
    assert compare_schemas(None, None) is False


# --- Test infer_schema_from_csv ---
def test_infer_schema_from_csv(tmp_path):
    # Create a temporary CSV file.
    csv_content = "id,Name with Space,Score\n1,Alice,85.5\n2,Bob,92.0"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    inferred_schema, column_definitions = infer_schema_from_csv(str(csv_file))

    # Check sanitized column names and inferred types
    expected_schema = {
        "id": "INTEGER",
        "Name_with_Space": "TEXT",  # Sanitized
        "Score": "REAL"             # Sanitized (no change needed)
    }
    assert inferred_schema == expected_schema

    # 'id' should have been given a PRIMARY KEY designation.
    # Column names in definition should be sanitized.
    expected_columns = [
        '"id" INTEGER PRIMARY KEY',
        '"Name_with_Space" TEXT',
        '"Score" REAL'
    ]
    # Order might vary depending on dict iteration, sort to compare
    assert sorted(column_definitions) == sorted(expected_columns)


# Test empty CSV
def test_infer_schema_empty_csv(tmp_path):
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("")  # Completely empty
    schema, cols = infer_schema_from_csv(str(csv_file))
    assert schema is None
    assert cols is None


# Test CSV with only headers
def test_infer_schema_headers_only_csv(tmp_path):
    csv_file = tmp_path / "headers.csv"
    csv_file.write_text("col1,col 2,3rdCol")  # Headers only
    schema, cols = infer_schema_from_csv(str(csv_file))
    expected_schema = {"col1": "TEXT", "col_2": "TEXT", "_3rdCol": "TEXT"}
    assert schema == expected_schema
    expected_cols = ['"col1" TEXT', '"col_2" TEXT', '"_3rdCol" TEXT']
    # Order might vary, sort to compare
    assert sorted(cols) == sorted(expected_cols)


# --- Test create_dynamic_table and drop_table ---
def test_create_and_drop_table():
    conn = sqlite3.connect(":memory:")  # Use in-memory DB for testing
    table_name = "test Create Drop Table"  # Name with space
    sanitized_name = sanitize_name(table_name)
    column_definitions = ['"id" INTEGER PRIMARY KEY', '"value" TEXT']

    # Create the table.
    assert create_dynamic_table(conn, table_name, column_definitions) is True

    # Verify schema using sanitized name
    schema = get_existing_schema(conn, sanitized_name)
    assert schema is not None
    assert "id" in schema
    assert schema["id"] == "INTEGER"  # Check type from PRAGMA
    assert "value" in schema
    assert schema["value"] == "TEXT"

    # Drop the table using original (unsanitized) name - drop should sanitize
    assert drop_table(conn, table_name) is True
    assert get_existing_schema(conn, sanitized_name) is None  # Verify gone
    conn.close()


# --- Test load_csv_to_table ---
def test_load_csv_to_table(tmp_path):
    csv_content = "User ID,Activity Name\n1,Login\n2,Logout\n3,Login"
    csv_file = tmp_path / "test_load.csv"
    csv_file.write_text(csv_content)

    conn = sqlite3.connect(":memory:")
    table_name = "activity log"  # Needs sanitization
    sanitized_name = sanitize_name(table_name)

    # Need to create the table first before loading with 'append' or 'replace'
    # Let's use infer_schema and create_dynamic_table
    schema, col_defs = infer_schema_from_csv(str(csv_file))
    assert create_dynamic_table(conn, table_name, col_defs) is True

    # Test loading data (using 'replace' strategy for simplicity here)
    result = load_csv_to_table(conn, str(csv_file), table_name,
                               if_exists_strategy="replace")
    assert result is True

    # Verify data using sanitized name
    cursor = conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{sanitized_name}"')
    count = cursor.fetchone()[0]
    assert count == 3

    # Verify column names were sanitized in the table and data loaded correctly
    cursor.execute(
        f'SELECT "User_ID", "Activity_Name" FROM "{sanitized_name}" '
        'WHERE "User_ID" = 1'
    )
    row = cursor.fetchone()
    # Assuming User_ID is INTEGER, Activity_Name TEXT
    assert row == (1, "Login")

    conn.close()


# --- Test chatgpt_sql_prompt with a fake API response ---

# Define fake response classes *outside* the test function for clarity
class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeCompletion:
    def __init__(self, choices):
        self.choices = choices


def test_chatgpt_sql_prompt(monkeypatch):
    # Define the fake create function
    def fake_create(*args, **kwargs):
        # Simulate a valid response structure
        fake_content = (
            "```sql\n"
            "SELECT product_name, total_revenue \n"
            "FROM sample_2c \n"
            "ORDER BY total_revenue DESC;\n"
            "```\n"
            "Explanation:\n"
            "This query retrieves product names and their revenues from the \n"
            "sample_2c table, ordering them by revenue in descending order."
        )
        fake_message = FakeMessage(content=fake_content)
        fake_choice = FakeChoice(message=fake_message)
        return FakeCompletion(choices=[fake_choice])

    # Use monkeypatch to replace the actual API call with our fake
    monkeypatch.setattr(client.chat.completions, "create", fake_create)

    # Call the function being tested
    user_query = "Show products ordered by revenue"
    sql_query, explanation = chatgpt_sql_prompt(user_query)

    # Assertions on the parsed output
    expected_sql = ("SELECT product_name, total_revenue \n"
                    "FROM sample_2c \n"
                    "ORDER BY total_revenue DESC;")
    expected_explanation = ("This query retrieves product names and their "
                            "revenues from the \n"
                            "sample_2c table, ordering them by revenue in "
                            "descending order.")

    # Ensure leading/trailing ws removed and compare
    assert sql_query == expected_sql.strip()
    assert explanation == expected_explanation.strip()


# Test case for malformed API response
def test_chatgpt_sql_prompt_malformed(monkeypatch):
    # Fake class definitions corrected for E701
    # These are simple structures just for this test's mock response
    class MockMessage:
        content: str

    class MockChoice:
        message: MockMessage

    class MockCompletion:
        choices: list[MockChoice]

    def fake_create(*args, **kwargs):
        # Simulate a response missing the 'Explanation:' delimiter
        fake_content = "SELECT * FROM sample_2c;"
        # We need instances, not just types
        message = MockMessage()
        message.content = fake_content
        choice = MockChoice()
        choice.message = message
        completion = MockCompletion()
        completion.choices = [choice]
        return completion

    monkeypatch.setattr(client.chat.completions, "create", fake_create)

    # Expect a ValueError because parsing will fail
    # Use pytest.raises to check for the expected exception
    with pytest.raises(ValueError, match="delimiter not found"):
        chatgpt_sql_prompt("get all data")
