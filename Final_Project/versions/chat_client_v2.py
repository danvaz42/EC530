import asyncio
import sys
import argparse

# --- Configuration ---
# Currently obscured (zeros), for safety reasons 
DEFAULT_SERVER_HOST = '000.00.000.00' # Default to YOUR server's public IP!
DEFAULT_SERVER_PORT = 000        # Default port YOUR server is using

# --- Networking Core ---

async def handle_received_data(reader: asyncio.StreamReader):
    """Coroutine to continuously read data from the server and print it."""
    try:
        while True:
            data = await reader.readline()
            if not data:
                print("\n--- Connection closed by server. ---")
                break # Exit loop if connection is closed

            message = data.decode().strip()
            # Simple print - server handles formatting with usernames
            print(f"\n{message}")
            print("Enter message: ", end='', flush=True) # Re-prompt user

    except asyncio.CancelledError:
        print("\nReceive task cancelled.") # Expected during shutdown
    except ConnectionResetError:
        print("\n--- Connection to server lost (reset). ---")
    except Exception as e:
        print(f"\nAn error occurred while receiving: {e}")
    finally:
        print("Stopping receiver.")


async def handle_sending_data(writer: asyncio.StreamWriter):
    """Coroutine to get user input and send it to the server."""
    loop = asyncio.get_running_loop()
    try:
        while True:
            # Run blocking input() in a separate thread
            message_to_send = await loop.run_in_executor(
                None, lambda: input("Enter message: ")
            )

            if not writer.is_closing():
                message_bytes = message_to_send.encode() + b'\n' # Add newline as delimiter
                writer.write(message_bytes)
                await writer.drain() # Ensure the buffer is flushed

                if message_to_send.lower() == 'quit':
                    print("Sent quit request. Closing connection...")
                    break # Exit loop after sending 'quit'
            else:
                 print("Cannot send, connection is closing.")
                 break

    except asyncio.CancelledError:
        print("\nSend task cancelled.") # Expected during shutdown
    except (ConnectionResetError, BrokenPipeError, OSError):
        print("\n--- Connection lost while trying to send. ---")
    except Exception as e:
        print(f"\nAn error occurred while sending: {e}")
    finally:
        print("Stopping sender.")
        # Don't close writer here, let the main cleanup handle it
        # to avoid race conditions if receiver closes first.


# --- Main Entry Point ---
async def main_client(host: str, port: int):
    """Connects to the server and starts chat tasks."""
    reader, writer = None, None
    receive_task, send_task = None, None
    main_task = asyncio.current_task() # Get reference to this task

    try:
        print(f"Attempting to connect to server at {host}:{port}...")
        # Add a timeout for the connection attempt
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10.0
            )
        peer_name = writer.get_extra_info('peername')
        print(f"--- Connected to server {peer_name} ---")

        # Start receiver first to catch welcome message/username prompt
        receive_task = asyncio.create_task(handle_received_data(reader))

        # Wait briefly for potential prompt before starting sender
        await asyncio.sleep(0.1)

        # Start sender
        send_task = asyncio.create_task(handle_sending_data(writer))

        # Wait for either task to complete (e.g., user types 'quit', server disconnects)
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        print("\n--- One of the communication tasks finished. Cleaning up... ---")

    except ConnectionRefusedError:
        print(f"--- Connection refused. Is the server running at {host}:{port}? ---")
    except asyncio.TimeoutError:
         print(f"--- Connection attempt to {host}:{port} timed out. ---")
    except OSError as e:
        print(f"--- Network error connecting to {host}:{port}: {e} ---")
    except Exception as e:
        print(f"\nFailed to connect or run client: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Initiating client shutdown...")
        # Cancel pending tasks if they exist and haven't finished
        if send_task and not send_task.done():
            send_task.cancel()
        if receive_task and not receive_task.done():
            receive_task.cancel()

        # Wait for tasks to acknowledge cancellation (or finish naturally)
        all_tasks = [t for t in [receive_task, send_task] if t]
        if all_tasks:
             await asyncio.gather(*all_tasks, return_exceptions=True) # Suppress exceptions on gather

        # Close the writer if it's still open
        if writer and not writer.is_closing():
            print("Closing connection to server...")
            writer.close()
            try:
                await writer.wait_closed()
            except Exception as e:
                print(f"Error during final writer close: {e}")
        print("Client finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async P2P Chat Client")
    parser.add_argument('--host', default=DEFAULT_SERVER_HOST,
                        help=f"Server host address (default: {DEFAULT_SERVER_HOST})")
    parser.add_argument('--port', type=int, default=DEFAULT_SERVER_PORT,
                        help=f"Server port number (default: {DEFAULT_SERVER_PORT})")

    args = parser.parse_args()

    try:
        asyncio.run(main_client(args.host, args.port))
    except KeyboardInterrupt:
        print("\nShutdown requested by user (Ctrl+C).")
    finally:
        print("Chat application terminated.")
