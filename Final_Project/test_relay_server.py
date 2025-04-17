# relay_server_v2.py (Corrected)

import asyncio
import argparse
import sys
from collections import defaultdict # Using defaultdict might simplify slightly

# --- Configuration ---
DEFAULT_HOST = '0.0.0.0'  # Listen on all available network interfaces
DEFAULT_PORT = 8888       # Port for chat communication (Adjust if needed)

# --- Global State ---
# Stores connected clients: {writer: {"peername": peername, "username": username}}
connected_clients = {}
# Lock to safely modify connected_clients from different client handlers
clients_lock = asyncio.Lock()

# --- Networking & Application Logic ---

async def broadcast(message: str, sender_writer: asyncio.StreamWriter | None): # Allow None for sender_writer
    """Sends a message to all connected clients except the sender."""
    global connected_clients
    async with clients_lock: # Acquire lock before accessing shared state
        # Prepare message once
        encoded_message = message.encode() + b'\n'
        # Create a list of writers to iterate over, preventing issues if dict changes mid-loop
        all_writers = list(connected_clients.keys())

        for writer in all_writers:
            # Send to writer if it's not the specified sender
            # If sender_writer is None (e.g., for server messages like 'leave'), send to everyone
            if writer is not sender_writer:
                peer_info = connected_clients.get(writer) # Get info for logging
                try:
                    writer.write(encoded_message)
                    await writer.drain()
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    # Handle case where sending fails (client likely disconnected abruptly)
                    if peer_info:
                        print(f"[Server] Error sending to {peer_info.get('username', 'Unknown')}: {e}. Removing.")
                    else:
                        print(f"[Server] Error sending to disconnected client: {e}. Removing.")
                    # Attempt removal here, though the client's handler should also do it
                    writer.close()
                    # Remove from dictionary (check if exists first)
                    if writer in connected_clients:
                         del connected_clients[writer]
                    # It's better practice to let the handle_client finally block do the main removal
                except Exception as e:
                    # Log other unexpected errors during broadcast
                    if peer_info:
                         print(f"[Server] Unexpected broadcast error to {peer_info.get('username', 'Unknown')}: {e}")
                    else:
                        print(f"[Server] Unexpected broadcast error: {e}")


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handles connection for a single client."""
    global connected_clients
    peername = writer.get_extra_info('peername', ('Unknown', 0))
    username = None
    client_writer = writer # Keep a reference for the finally block

    try:
        # 1. Get username
        print(f"[Server] New connection from {peername}")
        writer.write(b"Welcome! Please enter your username:\n")
        await writer.drain()

        username_data = await reader.readline()
        if not username_data:
            print(f"[Server] Client {peername} disconnected before sending username.")
            return # Exit if client disconnects immediately

        username = username_data.decode().strip()
        if not username:
            username = f"User_{peername[1]}" # Assign default if empty
            writer.write(f"No username provided, assigned: {username}\n".encode())
            await writer.drain()

        # 2. Add client to global list (with lock)
        async with clients_lock:
            if any(c.get("username") == username for c in connected_clients.values()):
                 writer.write(f"Username '{username}' already taken. Please reconnect with a different name.\n".encode())
                 await writer.drain()
                 print(f"[Server] Client {peername} disconnected due to duplicate username: {username}")
                 return

            connected_clients[client_writer] = {"peername": peername, "username": username}
            print(f"[Server] User '{username}' ({peername}) connected.")

        # 3. Announce join to others
        await broadcast(f"[Server] '{username}' has joined the chat!", client_writer)
        writer.write(b"You are now connected. Type 'quit' to exit.\n")
        await writer.drain()

        # 4. Receive and broadcast messages
        while True:
            data = await reader.readline()
            if not data:
                # Client disconnected gracefully (or connection lost)
                print(f"[Server] '{username}' ({peername}) disconnected (EOF).")
                break

            message = data.decode().strip()
            if message.lower() == 'quit':
                print(f"[Server] '{username}' requested to quit.")
                break # Exit loop, finally block will handle cleanup

            if not message: # Ignore empty lines
                continue

            print(f"[Server] Received from '{username}': {message}")
            # Prepend username and broadcast
            await broadcast(f"[{username}]: {message}", client_writer)

    except ConnectionResetError:
        print(f"[Server] Connection reset by '{username if username else peername}'.")
    except asyncio.CancelledError:
        print(f"[Server] Handler for '{username if username else peername}' cancelled.")
        raise # Re-raise cancellation
    except Exception as e:
        print(f"[Server] Error handling client '{username if username else peername}': {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging server issues
    finally:
        # 5. Cleanup: Remove client and announce departure
        departing_username = "Someone" # Default username if lookup fails
        async with clients_lock:
            if client_writer in connected_clients:
                # Ensure username is fetched correctly for departure message
                departing_username = connected_clients[client_writer].get("username", departing_username) # Use default if key somehow missing
                del connected_clients[client_writer]
                print(f"[Server] User '{departing_username}' ({peername}) removed from active list.")
        # Announce departure only if username was set (i.e., not the default 'Someone')
        # Do this *after* releasing the lock, but use the captured username
        if departing_username != "Someone":
             # *** THE CORRECTED LINE ***
             await broadcast(f"[Server] '{departing_username}' has left the chat.", None) # Pass None for departure broadcast

        # Clean up the writer resource for this client
        if client_writer and not client_writer.is_closing():
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except Exception as e:
                print(f"[Server] Error during final close for {peername}: {e}")
        print(f"[Server] Connection handler finished for {peername}.")


# --- Main Entry Point ---
async def main_server(host: str, port: int):
    """Starts the relay server."""
    server = None
    try:
        server = await asyncio.start_server(handle_client, host, port)
        # Use actual address server is listening on (helpful if host='0.0.0.0')
        actual_addr = server.sockets[0].getsockname()
        print(f"[Server] Relay server started on {actual_addr}")
        print("[Server] Waiting for client connections...")
        async with server:
            await server.serve_forever()
    except OSError as e:
        print(f"[Server] Error starting server on {host}:{port} - {e}")
        print("[Server] Is the port already in use?")
    except Exception as e:
        print(f"[Server] An unexpected error occurred: {e}")
    finally:
        print("[Server] Shutting down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async Chat Relay Server")
    parser.add_argument('--host', default=DEFAULT_HOST,
                        help=f"Host address to bind to (default: {DEFAULT_HOST})")
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f"Port number to listen on (default: {DEFAULT_PORT})")

    args = parser.parse_args()

    try:
        asyncio.run(main_server(args.host, args.port))
    except KeyboardInterrupt:
        print("\n[Server] Shutdown requested by user (Ctrl+C).")
    finally:
        print("[Server] Application terminated.")
