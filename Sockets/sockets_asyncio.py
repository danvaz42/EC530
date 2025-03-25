import asyncio
import nest_asyncio
import socket

# for nested event loops in notebook environments.
nest_asyncio.apply()

# Global list to keep track of active sockets.
active_sockets = []

def register_socket(sock):
    """Register a socket to be cleaned up later."""
    active_sockets.append(sock)

def cleanup_sockets():
    """Clean up all registered sockets."""
    print("Cleaning up sockets...", flush=True)
    for sock in active_sockets:
        try:
            try:
                addr = sock.getsockname()
            except Exception:
                addr = "unknown"
            sock.close()
            print(f"Closed socket at {addr}", flush=True)
        except Exception as e:
            print(f"Error closing socket: {e}", flush=True)
    active_sockets.clear()

# SERVER

async def handle_client(client_sock, addr, loop):
    print(f"Server: Connected to {addr}", flush=True)
    
    # Register client socket.
    register_socket(client_sock)
    
    # Lock to prevent concurrent writes on the same socket.
    send_lock = asyncio.Lock()

    async def read_loop():
        while True:
            try:
                data = await loop.sock_recv(client_sock, 1024)
                if not data:
                    print("Server: No data received, closing connection.", flush=True)
                    break  # Connection closed.
                message = data.decode()
                print(f"Server received: {message}", flush=True)
                # If the message is not an acknowledgement, send one back.
                if not message.startswith("ACK:"):
                    ack_message = f"ACK: Received '{message}'"
                    try:
                        async with send_lock:
                            await loop.sock_sendall(client_sock, ack_message.encode())
                        print(f"Server sent acknowledgement: {ack_message}", flush=True)
                    except Exception as e:
                        print(f"Server error sending acknowledgement: {e}", flush=True)
            except Exception as e:
                print(f"Server read error: {e}", flush=True)
                break

    async def write_loop():
        try:
            message = "hello from server"
            async with send_lock:
                await loop.sock_sendall(client_sock, message.encode())
            print(f"Server sent: {message}", flush=True)
        except Exception as e:
            print(f"Server write error (message 1): {e}", flush=True)

        await asyncio.sleep(2)

        try:
            message = "server: How are you?"
            async with send_lock:
                await loop.sock_sendall(client_sock, message.encode())
            print(f"Server sent: {message}", flush=True)
        except Exception as e:
            print(f"Server write error (message 2): {e}", flush=True)

    # Run both tasks concurrently.
    await asyncio.gather(read_loop(), write_loop())
    client_sock.close()
    print("Server: Connection closed.", flush=True)

async def run_server(host="127.0.0.1", port=50007):
    loop = asyncio.get_running_loop()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    register_socket(server_sock)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind((host, port))
    except OSError as e:
        print(f"Error binding server socket: {e}", flush=True)
        return
    server_sock.listen()
    server_sock.setblocking(False)
    print(f"Server: Listening on {(host, port)}", flush=True)

    while True:
        try:
            client_sock, addr = await loop.sock_accept(server_sock)
            # Handle each client connection in its own task.
            asyncio.create_task(handle_client(client_sock, addr, loop))
        except Exception as e:
            print(f"Server accept error: {e}", flush=True)
            break

# CLIENT

async def run_client(server_host="127.0.0.1", server_port=50007,
                     client_host="127.0.0.1", client_port=50008):
    loop = asyncio.get_running_loop()
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    register_socket(client_sock)
    client_sock.setblocking(False)
    try:
        # Bind the client socket to a fixed local endpoint.
        client_sock.bind((client_host, client_port))
    except OSError as e:
        print(f"Error binding client socket: {e}", flush=True)
        return
    try:
        await loop.sock_connect(client_sock, (server_host, server_port))
    except Exception as e:
        print(f"Client connection error: {e}", flush=True)
        return
    print("Client: Connected to server", flush=True)
    print(f"Client: Local address {client_sock.getsockname()}", flush=True)
    
    send_lock = asyncio.Lock()

    async def read_loop():
        while True:
            try:
                data = await loop.sock_recv(client_sock, 1024)
                if not data:
                    print("Client: No data received, closing connection.", flush=True)
                    break  # Connection closed.
                message = data.decode()
                print(f"Client received: {message}", flush=True)
                # Send acknowledgement if the message is not an acknowledgement.
                if not message.startswith("ACK:"):
                    ack_message = f"ACK: Received '{message}'"
                    try:
                        async with send_lock:
                            await loop.sock_sendall(client_sock, ack_message.encode())
                        print(f"Client sent acknowledgement: {ack_message}", flush=True)
                    except Exception as e:
                        print(f"Client error sending acknowledgement: {e}", flush=True)
            except Exception as e:
                print(f"Client read error: {e}", flush=True)
                break

    async def write_loop():
        try:
            message = "hello from client"
            async with send_lock:
                await loop.sock_sendall(client_sock, message.encode())
            print(f"Client sent: {message}", flush=True)
        except Exception as e:
            print(f"Client write error (message 1): {e}", flush=True)

        await asyncio.sleep(3)

        try:
            message = "client: I'm fine, thanks!"
            async with send_lock:
                await loop.sock_sendall(client_sock, message.encode())
            print(f"Client sent: {message}", flush=True)
        except Exception as e:
            print(f"Client write error (message 2): {e}", flush=True)

    await asyncio.gather(read_loop(), write_loop())
    client_sock.close()
    print("Client: Connection closed.", flush=True)

async def main(duration=10):
    """Start server and client tasks, run for a given duration (in seconds), then clean up."""
    server_task = asyncio.create_task(run_server())
    # Wait briefly to ensure the server is ready.
    await asyncio.sleep(1)
    client_task = asyncio.create_task(run_client())
    
    # Let the tasks run for the specified duration.
    await asyncio.sleep(duration)
    
    # Cancel both tasks.
    client_task.cancel()
    server_task.cancel()
    try:
        await client_task
    except asyncio.CancelledError:
        print("Client task cancelled.", flush=True)
    try:
        await server_task
    except asyncio.CancelledError:
        print("Server task cancelled.", flush=True)
    
    # Clean up all sockets.
    cleanup_sockets()

if __name__ == "__main__":
    # Run the main function with default duration.
    asyncio.run(main())
