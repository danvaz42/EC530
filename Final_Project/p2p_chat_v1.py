import asyncio
import sys
import argparse

# --- Configuration ---
DEFAULT_HOST = '127.0.0.1'  # Use localhost by default
DEFAULT_PORT = 8888       # Arbitrary port number

# --- Networking Core ---

async def handle_received_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Coroutine to continuously read data from the peer and print it."""
    peer_name = writer.get_extra_info('peername')
    print(f"Connection established with {peer_name}")
    try:
        while True:
            data = await reader.readline()  # Read until newline
            if not data:
                print(f"Connection with {peer_name} closed by peer.")
                break # Exit loop if connection is closed

            message = data.decode().strip()
            if not message: # Skip empty lines that might result from just pressing Enter
                continue

            print(f"\nReceived from {peer_name}: {message}")
            print("Enter message to send (or 'quit'): ", end='', flush=True) # Re-prompt user

            # --- Potential Future Hook ---
            # process_incoming_api_call(message)
            # update_gui_with_message(message)

    except asyncio.CancelledError:
        print(f"Receive task for {peer_name} cancelled.")
    except ConnectionResetError:
        print(f"Connection with {peer_name} was reset.")
    except Exception as e:
        print(f"An error occurred while receiving from {peer_name}: {e}")
    finally:
        print(f"Stopping receiver for {peer_name}.")
        if not writer.is_closing():
            # Ensure the writer is closed if the reader loop exits unexpectedly
            writer.close()
            # await writer.wait_closed() # This can sometimes hang if peer closed abruptly

async def handle_sending_data(writer: asyncio.StreamWriter):
    """Coroutine to get user input and send it to the peer."""
    peer_name = writer.get_extra_info('peername')
    loop = asyncio.get_running_loop()
    try:
        while True:
            # Run blocking input() in a separate thread
            message_to_send = await loop.run_in_executor(
                None, lambda: input("Enter message to send (or 'quit'): ")
            )

            if message_to_send.lower() == 'quit':
                print("Requesting to close connection...")
                break # Exit loop to close connection

            if not message_to_send: # Handle empty input if needed
                continue

            # --- Potential Future Hook ---
            # processed_message = call_external_api(message_to_send)
            # message_bytes = processed_message.encode() + b'\n'

            message_bytes = message_to_send.encode() + b'\n' # Add newline as delimiter

            writer.write(message_bytes)
            await writer.drain() # Ensure the buffer is flushed

    except asyncio.CancelledError:
        print(f"Send task for {peer_name} cancelled.")
    except (ConnectionResetError, BrokenPipeError, OSError):
        print(f"Connection with {peer_name} lost while trying to send.")
    except Exception as e:
        print(f"An error occurred while sending to {peer_name}: {e}")
    finally:
        print(f"Stopping sender for {peer_name}. Closing connection.")
        if not writer.is_closing():
            writer.close()
            await writer.wait_closed()

# --- Application Logic ---

async def connection_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handles a single connection (used by both server and client)."""
    peer_name = writer.get_extra_info('peername')
    print("-" * 20)

    # Create concurrent tasks for receiving and sending
    receive_task = asyncio.create_task(handle_received_data(reader, writer))
    send_task = asyncio.create_task(handle_sending_data(writer))

    # Wait for either task to complete (e.g., user types 'quit', connection drops)
    done, pending = await asyncio.wait(
        [receive_task, send_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    print(f"\nOne of the tasks for {peer_name} finished. Cleaning up...")

    # Cancel the remaining task(s) to ensure clean shutdown
    for task in pending:
        task.cancel()
        try:
            await task # Allow cancellation to propagate and handle exceptions
        except asyncio.CancelledError:
            pass # Expected

    # Ensure writer is closed if not already done by handle_sending_data
    if not writer.is_closing():
        print(f"Explicitly closing writer for {peer_name}.")
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionResetError:
             # It might already be closed abruptly by the peer
             print(f"Writer for {peer_name} already closed by peer (reset).")


    print(f"Connection with {peer_name} fully closed.")
    print("-" * 20)

# --- Main Entry Point ---

async def run_server(host: str, port: int):
    """Starts the server to listen for incoming connections."""
    server = None
    try:
        server = await asyncio.start_server(connection_handler, host, port)
        addr = server.sockets[0].getsockname()
        print(f'Server started. Listening on {addr}')
        print("Waiting for a connection...")
        async with server:
            await server.serve_forever()
    except OSError as e:
        print(f"Error starting server on {host}:{port} - {e}")
        print("Is the port already in use?")
    except Exception as e:
        print(f"An unexpected error occurred in the server: {e}")
    finally:
        if server and not server.is_serving():
             print("Server has stopped.")


async def run_client(host: str, port: int):
    """Connects to a server as a client."""
    reader, writer = None, None
    try:
        print(f"Attempting to connect to {host}:{port}...")
        reader, writer = await asyncio.open_connection(host, port)
        # Connection successful, pass streams to the handler
        await connection_handler(reader, writer)
    except ConnectionRefusedError:
        print(f"Connection refused. Is the server running on {host}:{port}?")
    except asyncio.TimeoutError:
         print(f"Connection attempt to {host}:{port} timed out.")
    except Exception as e:
        print(f"Failed to connect or run client: {e}")
    finally:
        # Redundant check, as connection_handler should close, but good practice
        if writer and not writer.is_closing():
            print("Ensuring client writer is closed.")
            writer.close()
            try:
                await writer.wait_closed()
            except Exception as e:
                print(f"Error during final client writer close: {e}")
        print("Client finished.")


def main():
    parser = argparse.ArgumentParser(description="Simple Async P2P Chat")
    parser.add_argument('mode', choices=['server', 'client'],
                        help="Run as 'server' (listen) or 'client' (connect)")
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help=f"Host address (default: {DEFAULT_HOST})")
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f"Port number (default: {DEFAULT_PORT})")

    args = parser.parse_args()

    host = args.host
    port = args.port

    try:
        if args.mode == 'server':
            print(f"Starting chat in SERVER mode on {host}:{port}")
            asyncio.run(run_server(host, port))
        elif args.mode == 'client':
            print(f"Starting chat in CLIENT mode, connecting to {host}:{port}")
            asyncio.run(run_client(host, port))
    except KeyboardInterrupt:
        print("\nShutdown requested by user (Ctrl+C). Exiting.")
    except Exception as e:
        print(f"\nAn unexpected error occurred in main: {e}")
    finally:
        print("Chat application terminated.")

if __name__ == "__main__":
    main()