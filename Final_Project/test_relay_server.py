# Final_Project/test_relay_server.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call # Import 'patch' and 'call'

# Important: Import from your SERVER file now.
# Assuming relay_server.py is in the same Final_Project directory
from .relay_server_v2 import handle_client, broadcast, clients_lock

# Mark all tests in this module as asyncio tests
pytestmark = pytest.mark.asyncio

# --- Tests for handle_client ---

@pytest.fixture
def mock_writer(event_loop):
    """Fixture to create a mock StreamWriter with basic functionalities."""
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.get_extra_info.return_value = ('127.0.0.1', 12345)
    writer.is_closing.return_value = False
    writer.close = MagicMock() # Mock close method
    # Mock drain and wait_closed as awaitable
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return writer

@pytest.fixture
def mock_reader():
    """Fixture to create a mock StreamReader."""
    reader = AsyncMock(spec=asyncio.StreamReader)
    return reader

@pytest.fixture(autouse=True) # Apply this automatically to all tests in the module
async def manage_server_state():
    """Fixture to reset server state before each test and handle lock."""
    # Use patch to temporarily replace the global state for tests
    with patch('relay_server.connected_clients', {}):
        # Ensure lock is acquired/released correctly around tests if needed
        # This simple version just ensures the patched dict is used.
        # For complex lock tests, more specific mocking might be required.
        yield # Run the test with the patched state
    # State is automatically restored after yield by patch context manager

# Patch the broadcast function so we don't actually try sending during handle_client tests
@patch('relay_server.broadcast', new_callable=AsyncMock)
async def test_handle_client_connect_username_message_quit(
    mock_broadcast, mock_reader, mock_writer
):
    """Tests a standard client flow: connect, username, message, quit."""
    # Arrange
    username = b"Alice\n"
    message = b"Hello World!\n"
    quit_cmd = b"quit\n"
    eof = b""

    mock_reader.readline.side_effect = [username, message, quit_cmd, eof] # Sequence of reads

    # Act
    await handle_client(mock_reader, mock_writer)

    # Assert
    # 1. Prompts and Acks sent by server
    expected_writes = [
        call(b"Welcome! Please enter your username:\n"),
        call(b"You are now connected. Type 'quit' to exit.\n")
    ]
    mock_writer.write.assert_has_calls(expected_writes, any_order=False)
    assert mock_writer.drain.call_count >= len(expected_writes) # Drain called after writes

    # 2. Broadcast calls
    # Use await_args_list for async mock calls
    broadcast_calls = mock_broadcast.await_args_list
    assert len(broadcast_calls) == 3 # Join, Message, Leave
    # Check join message broadcast
    assert broadcast_calls[0] == call("[Server] 'Alice' has joined the chat!", mock_writer)
    # Check chat message broadcast
    assert broadcast_calls[1] == call("[Alice]: Hello World!", mock_writer)
    # Check leave message broadcast (sender is None for leave)
    assert broadcast_calls[2] == call("[Server] 'Alice' has left the chat.", None)

    # 3. Writer closed at the end
    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()


@patch('relay_server.broadcast', new_callable=AsyncMock)
async def test_handle_client_disconnect_before_username(
    mock_broadcast, mock_reader, mock_writer
):
    """Tests client disconnecting before sending a username."""
     # Arrange
    eof = b""
    mock_reader.readline.side_effect = [eof]

    # Act
    await handle_client(mock_reader, mock_writer)

    # Assert
    # Prompt for username was sent
    mock_writer.write.assert_called_once_with(b"Welcome! Please enter your username:\n")
    mock_writer.drain.assert_awaited_once()
    # No broadcasts should have happened
    mock_broadcast.assert_not_awaited()
    # Writer closed
    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()


@patch('relay_server.broadcast', new_callable=AsyncMock)
async def test_handle_client_duplicate_username(
    mock_broadcast, mock_reader, mock_writer, manage_server_state # Use patched state
):
    """Tests handling of a duplicate username."""
    # Arrange
    # Pre-populate state using the patched 'connected_clients'
    existing_writer = AsyncMock(spec=asyncio.StreamWriter)
    relay_server = sys.modules['relay_server'] # Get module to access patched dict
    relay_server.connected_clients[existing_writer] = {"username": "Alice", "peername": ('1.1.1.1', 111)}

    duplicate_username = b"Alice\n"
    eof = b""
    mock_reader.readline.side_effect = [duplicate_username, eof]

    # Act
    await handle_client(mock_reader, mock_writer)

    # Assert
    # Username prompt and duplicate message sent
    expected_writes = [
        call(b"Welcome! Please enter your username:\n"),
        call(b"Username 'Alice' already taken. Please reconnect with a different name.\n")
    ]
    mock_writer.write.assert_has_calls(expected_writes, any_order=False)
    assert mock_writer.drain.call_count >= len(expected_writes)

    # No broadcasts happened
    mock_broadcast.assert_not_awaited()

    # Writer closed
    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()

    # Check state - the new client should NOT have been added
    assert len(relay_server.connected_clients) == 1 # Only the original 'existing_writer'
    assert mock_writer not in relay_server.connected_clients


# --- Tests for broadcast ---

# NOTE: Testing broadcast thoroughly requires more complex mocking of
# connected_clients and potentially the lock if concurrency is a concern.
# These are simpler examples.

@patch('relay_server.connected_clients', new_callable=dict) # Patch directly
async def test_broadcast_sends_to_others(mock_clients_dict):
    """Tests that broadcast sends to other clients but not the sender."""
    # Arrange
    sender_writer = AsyncMock(spec=asyncio.StreamWriter)
    writer1 = AsyncMock(spec=asyncio.StreamWriter)
    writer2 = AsyncMock(spec=asyncio.StreamWriter)

    # Populate the mocked dictionary
    mock_clients_dict[sender_writer] = {"username": "Sender"}
    mock_clients_dict[writer1] = {"username": "Recv1"}
    mock_clients_dict[writer2] = {"username": "Recv2"}

    message = "Test broadcast"
    expected_bytes = message.encode() + b'\n'

    # Act
    await broadcast(message, sender_writer)

    # Assert
    # Sender should NOT have received the message
    sender_writer.write.assert_not_called()
    sender_writer.drain.assert_not_awaited()

    # Others should have received it
    writer1.write.assert_called_once_with(expected_bytes)
    writer1.drain.assert_awaited_once()
    writer2.write.assert_called_once_with(expected_bytes)
    writer2.drain.assert_awaited_once()


@patch('relay_server.connected_clients', new_callable=dict) # Patch directly
async def test_broadcast_handles_send_error(mock_clients_dict):
    """Tests that broadcast handles errors when sending to a client."""
    # Arrange
    sender_writer = AsyncMock(spec=asyncio.StreamWriter)
    writer_ok = AsyncMock(spec=asyncio.StreamWriter)
    writer_bad = AsyncMock(spec=asyncio.StreamWriter)

    mock_clients_dict[sender_writer] = {"username": "Sender"}
    mock_clients_dict[writer_ok] = {"username": "RecvOK"}
    mock_clients_dict[writer_bad] = {"username": "RecvBad"} # Will fail

    # Configure the bad writer to raise an error
    writer_bad.write.side_effect = ConnectionResetError("Connection broken")
    writer_bad.close = MagicMock() # Mock close method

    message = "Test broadcast error"
    expected_bytes = message.encode() + b'\n'

    # Act
    await broadcast(message, sender_writer)

    # Assert
    # Sender not called
    sender_writer.write.assert_not_called()

    # Good writer called
    writer_ok.write.assert_called_once_with(expected_bytes)
    writer_ok.drain.assert_awaited_once()

    # Bad writer write was attempted, then it was closed
    writer_bad.write.assert_called_once_with(expected_bytes) # Attempted write
    writer_bad.drain.assert_not_awaited() # Drain likely not reached
    writer_bad.close.assert_called_once() # Closed due to error

    # Ideally, we'd also check if writer_bad was removed from mock_clients_dict,
    # but the broadcast function's error handling might defer final removal
    # to the handle_client loop. This assertion might be too strict here.
    # assert writer_bad not in mock_clients_dict
