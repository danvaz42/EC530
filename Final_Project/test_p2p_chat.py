# Final_Project/test_p2p_chat_.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock  # Use AsyncMock for awaitables

# Important: Make sure your chat code is importable.
# If p2p_chat_v1.py is in the same directory (Final_Project), this should work.
from .p2p_chat_v1 import handle_received_data # Relative import

# Mark all tests in this module as asyncio tests
pytestmark = pytest.mark.asyncio

async def test_handle_received_data_single_message(capsys):
    """Tests if a single message is received and printed correctly."""
    # Arrange
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_writer = MagicMock(spec=asyncio.StreamWriter) # No async methods needed here for this test

    # Configure peername for output message
    mock_writer.get_extra_info.return_value = ('127.0.0.1', 12345)

    # Configure mock reader to return one message then simulate connection close (empty bytes)
    test_message = b"Hello from test\n"
    mock_reader.readline.side_effect = [test_message, b""] # Return message, then EOF

    # Act
    # Run the handler function we want to test
    await handle_received_data(mock_reader, mock_writer)

    # Assert
    # Check that readline was called twice (once for message, once for EOF)
    assert mock_reader.readline.call_count == 2

    # Capture the printed output
    captured = capsys.readouterr()

    # Check if the welcome message and the received message were printed
    assert "Connection established with ('127.0.0.1', 12345)" in captured.out
    assert "Received from ('127.0.0.1', 12345): Hello from test" in captured.out
    assert "Connection with ('127.0.0.1', 12345) closed by peer." in captured.out

async def test_handle_received_data_multiple_messages(capsys):
    """Tests if multiple messages are received and printed correctly."""
    # Arrange
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_writer = MagicMock(spec=asyncio.StreamWriter)
    mock_writer.get_extra_info.return_value = ('peer_host', 54321)

    msg1 = b"First message\n"
    msg2 = b"Second message\n"
    # Sequence of return values for readline
    mock_reader.readline.side_effect = [msg1, msg2, b""]

    # Act
    await handle_received_data(mock_reader, mock_writer)

    # Assert
    assert mock_reader.readline.call_count == 3
    captured = capsys.readouterr()
    assert "Connection established with ('peer_host', 54321)" in captured.out
    assert "Received from ('peer_host', 54321): First message" in captured.out
    assert "Received from ('peer_host', 54321): Second message" in captured.out
    assert "Connection with ('peer_host', 54321) closed by peer." in captured.out

async def test_handle_received_data_empty_line(capsys):
    """Tests that empty lines (e.g., just pressing Enter) are ignored."""
    # Arrange
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_writer = MagicMock(spec=asyncio.StreamWriter)
    mock_writer.get_extra_info.return_value = ('empty_test', 1111)

    empty_line = b"\n" # Represents sending just a newline
    mock_reader.readline.side_effect = [empty_line, b""]

    # Act
    await handle_received_data(mock_reader, mock_writer)

    # Assert
    assert mock_reader.readline.call_count == 2
    captured = capsys.readouterr()
    assert "Connection established with ('empty_test', 1111)" in captured.out
    # Crucially, the "Received from..." line for the empty message should NOT be present
    assert "Received from ('empty_test', 1111):" not in captured.out.splitlines()[1] # Check line after connection established
    assert "Connection with ('empty_test', 1111) closed by peer." in captured.out

# --- Add more tests ---
# - Test handle_sending_data (more complex due to input(), might need mocking input or refactoring)
# - Test connection_handler integration (would need more complex mocks or actual local server/client setup)
# - Test error conditions (e.g., ConnectionResetError)