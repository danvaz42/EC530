This project demonstrates a simple peer-to-peer networking example using Python's asyncio module. It implements both a server and a client that exchange messages asynchronously, complete with basic acknowledgement handling and socket management.

Features:

Asynchronous Communication: Uses Python's asyncio for concurrent read/write operations.

Bidirectional Message Exchange: Both server and client send and receive messages, with acknowledgements.

Socket Management: Registers and cleans up all active sockets after operations.

Notebook Compatibility: Uses nest_asyncio to support nested event loops (ideal for interactive environments like Jupyter Notebooks).

Requirements:

Python 3.7 or later

nest_asyncio (Install via "pip install nest_asyncio")

Getting Started:

Clone or Download:

Save the Python script containing the provided code to your local machine.

Run the Script:

Execute the script from your terminal by running: python your_script.py

The script will:

Start a server listening on 127.0.0.1 at port 50007.

Start a client bound to 127.0.0.1 at port 50008, which connects to the server.

Run the communication tasks for 10 seconds (default duration) before cancelling tasks and cleaning up sockets.

Code Overview:

Server:

run_server(): Creates and binds a server socket, listens for incoming connections, and spawns a new task (handle_client()) for each client.

handle_client(): Manages message exchange with a connected client using separate asynchronous read and write loops.

Client:

run_client(): Creates and binds a client socket, connects to the server, and handles message exchange using asynchronous loops.

Socket Management:

register_socket(sock): Adds sockets to a global list for cleanup.

cleanup_sockets(): Closes all registered sockets when operations are complete.

Main Function:

main(duration=10): Starts both server and client tasks, waits for a specified duration (default is 10 seconds), then stops tasks and cleans up sockets.

Customization:

Changing Hosts and Ports:

Modify the host and port parameters in run_server() and run_client() if you wish to deploy the application on different IP addresses or ports.

Duration:

Change the duration argument in the main() function if you need the application to run for longer periods.

Troubleshooting:

Socket Binding Errors:

If binding to a specific port fails, ensure that the port is not in use or blocked by your operating system’s firewall.

Notebook Environments:

The inclusion of nest_asyncio.apply() ensures that the code works within Jupyter Notebooks. If you are running in a different environment, this call does no harm.

License: This project is open-source and provided for educational purposes. Feel free to modify and extend the code as needed.
