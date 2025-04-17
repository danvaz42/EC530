# Final_Project/test_relay_server.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import sys # Need sys to access modules for state check

# Use absolute import - this seems correct based on previous fix
from Final_Project.relay_server_v2 import handle_client, broadcast, clients_lock

# Mark all tests in this module as asyncio tests
pytestmark = pytest.mark.asyncio

# --- Fixtures ---

@pytest.fixture
def mock_writer(event_loop):
    # (Fixture code remains the same)
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.get_extra_info.return_value = ('127.0.0.1', 12345)
    writer.is_closing.return_value = False
    writer.close = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return writer

@pytest.fixture
def mock_reader():
    # (Fixture code remains the same)
    reader = AsyncMock(spec=asyncio.StreamReader)
    return reader

@pytest.fixture(autouse=True)
async def manage_server_state():
    """Fixture to reset server state before each test and handle lock."""
    # --- FIX: Use full path for patching ---
    with patch('Final_Project.relay_server_v2.connected_clients', {}):
        yield

# --- Tests for handle_client ---

# --- FIX: Use full path for patching broadcast ---
@patch('Final_Project.relay_server_v2.broadcast', new_callable=AsyncMock)
async def test_handle_client_connect_username_message_quit(
    mock_broadcast, mock_reader, mock_writer
):
    """Tests a standard client flow: connect, username, message, quit."""
    # Arrange
    username = b"Alice\n"
    message = b"Hello World!\n"
    quit_cmd = b"quit\n"
    eof = b""
    mock_reader.readline.side_effect = [username, message, quit_cmd, eof]

    # Act
    await handle_client(mock_reader, mock_writer)

    # Assert
    expected_writes = [
        call(b"Welcome! Please enter your username:\n"),
        call(b"You are now connected. Type 'quit' to exit.\n")
    ]
    mock_writer.write.assert_has_calls(expected_writes, any_order=False)
    assert mock_writer.drain.call_count >= len(expected_writes)

    broadcast_calls = mock_broadcast.await_args_list
    assert len(broadcast_calls) == 3
    assert broadcast_calls[0] == call("[Server] 'Alice' has joined the chat!", mock_writer)
    assert broadcast_calls[1] == call("[Alice]: Hello World!", mock_writer)
    assert broadcast_calls[2] == call("[Server] 'Alice' has left the chat.", None)

    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()


# --- FIX: Use full path for patching broadcast ---
@patch('Final_Project.relay_server_v2.broadcast', new_callable=AsyncMock)
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
    mock_writer.write.assert_called_once_with(b"Welcome! Please enter your username:\n")
    mock_writer.drain.assert_awaited_once()
    mock_broadcast.assert_not_awaited()
    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()


# --- FIX: Use full path for patching broadcast ---
@patch('Final_Project.relay_server_v2.broadcast', new_callable=AsyncMock)
async def test_handle_client_duplicate_username(
    mock_broadcast, mock_reader, mock_writer, manage_server_state # manage_server_state uses patch internally
):
    """Tests handling of a duplicate username."""
    # Arrange
    # Pre-populate state using the patched 'connected_clients'
    existing_writer = AsyncMock(spec=asyncio.StreamWriter)
    # --- FIX: Use full path to get module reference for state check ---
    # Access the patched dict via the module where manage_server_state patched it
    relay_server_module = sys.modules['Final_Project.relay_server_v2']
    relay_server_module.connected_clients[existing_writer] = {"username": "Alice", "peername": ('1.1.1.1', 111)}

    duplicate_username = b"Alice\n"
    eof = b""
    mock_reader.readline.side_effect = [duplicate_username, eof]

    # Act
    await handle_client(mock_reader, mock_writer)

    # Assert
    expected_writes = [
        call(b"Welcome! Please enter your username:\n"),
        call(b"Username 'Alice' already taken. Please reconnect with a different name.\n")
    ]
    mock_writer.write.assert_has_calls(expected_writes, any_order=False)
    assert mock_writer.drain.call_count >= len(expected_writes)
    mock_broadcast.assert_not_awaited()
    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()

    # Check state - the new client should NOT have been added
    assert len(relay_server_module.connected_clients) == 1
    assert mock_writer not in relay_server_module.connected_clients


# --- Tests for broadcast ---

# --- FIX: Use full path for patching ---
@patch('Final_Project.relay_server_v2.connected_clients', new_callable=dict)
async def test_broadcast_sends_to_others(mock_clients_dict):
    """Tests that broadcast sends to other clients but not the sender."""
    # Arrange
    sender_writer = AsyncMock(spec=asyncio.StreamWriter)
    writer1 = AsyncMock(spec=asyncio.StreamWriter)
    writer2 = AsyncMock(spec=asyncio.StreamWriter)

    mock_clients_dict[sender_writer] = {"username": "Sender"}
    mock_clients_dict[writer1] = {"username": "Recv1"}
    mock_clients_dict[writer2] = {"username": "Recv2"}

    message = "Test broadcast"
    expected_bytes = message.encode() + b'\n'

    # Act
    # --- FIX: Use full path for module reference if needed, but broadcast is imported directly ---
    # Call the imported broadcast function directly
    await broadcast(message, sender_writer)

    # Assert
    sender_writer.write.assert_not_called()
    sender_writer.drain.assert_not_awaited()
    writer1.write.assert_called_once_with(expected_bytes)
    writer1.drain.assert_awaited_once()
    writer2.write.assert_called_once_with(expected_bytes)
    writer2.drain.assert_awaited_once()


# --- FIX: Use full path for patching ---
@patch('Final_Project.relay_server_v2.connected_clients', new_callable=dict)
async def test_broadcast_handles_send_error(mock_clients_dict):
    """Tests that broadcast handles errors when sending to a client."""
    # Arrange
    sender_writer = AsyncMock(spec=asyncio.StreamWriter)
    writer_ok = AsyncMock(spec=asyncio.StreamWriter)
    writer_bad = AsyncMock(spec=asyncio.StreamWriter)

    mock_clients_dict[sender_writer] = {"username": "Sender"}
    mock_clients_dict[writer_ok] = {"username": "RecvOK"}
    mock_clients_dict[writer_bad] = {"username": "RecvBad"}

    writer_bad.write.side_effect = ConnectionResetError("Connection broken")
    writer_bad.close = MagicMock()

    message = "Test broadcast error"
    expected_bytes = message.encode() + b'\n'

    # Act
    await broadcast(message, sender_writer)

    # Assert
    sender_writer.write.assert_not_called()
    writer_ok.write.assert_called_once_with(expected_bytes)
    writer_ok.drain.assert_awaited_once()
    writer_bad.write.assert_called_once_with(expected_bytes)
    writer_bad.drain.assert_not_awaited()
    writer_bad.close.assert_called_once()

    # Note: checking removal from dict might still be tricky depending on exact error handling
