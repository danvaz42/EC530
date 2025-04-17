import customtkinter as ctk
import asyncio
import argparse
import sys
import threading
# queue is no longer needed for sending
import time

# --- Configuration ---
# Obscured Host/Port
DEFAULT_SERVER_HOST = '000.00.000.00' # Default to YOUR server's public IP!
DEFAULT_SERVER_PORT = 0000        # Default port YOUR server is using
APP_NAME = "Async Chat V2"
CONNECT_TIMEOUT = 10 # Seconds

# --- GUI Class ---
class ChatClientGUI:
    def __init__(self, root, host, port):
        self.root = root
        self.host = host
        self.port = port

        # Asyncio related state
        self.reader = None
        self.writer = None
        self.receive_task = None
        # Removed: self.send_task = None
        self.connection_task = None
        self.async_loop = None # Will hold the asyncio loop instance
        # Removed: self.send_queue = asyncio.Queue()
        self.is_connected = False
        self.is_connecting = False
        self.connect_lock = threading.Lock() # Prevent rapid connect/disconnect clicks
        self.username = ""
        self.connection_thread = None # Thread reference

        # Setup GUI theme and appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root.title(APP_NAME)
        self.root.geometry("600x500")
        self.root.minsize(400, 300)

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self.create_widgets()
        self.update_ui_state()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # --- Top Frame ---
        self.top_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.username_label = ctk.CTkLabel(self.top_frame, text="Username:")
        self.username_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.username_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Enter your username")
        self.username_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.connect_button = ctk.CTkButton(self.top_frame, text="Connect", width=100, command=self.connect_disconnect)
        self.connect_button.grid(row=0, column=2, padx=(5, 10), pady=10)

        self.status_label = ctk.CTkLabel(self.top_frame, text="Status: Disconnected", text_color="gray", anchor="w")
        self.status_label.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="ew")

        # --- Middle Frame (Chat Display) ---
        self.chat_display = ctk.CTkTextbox(self.root, state="disabled", wrap="word", corner_radius=6, font=("Segoe UI", 13))
        self.chat_display.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.chat_display.tag_config("server", foreground="#A0A0FF")
        self.chat_display.tag_config("user", foreground="#FFFFFF")
        self.chat_display.tag_config("error", foreground="#FF8080")
        self.chat_display.tag_config("info", foreground="#A0A0A0")

        # --- Bottom Frame (Input) ---
        self.bottom_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.bottom_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.bottom_frame.grid_columnconfigure(0, weight=1)

        self.message_entry = ctk.CTkEntry(self.bottom_frame, placeholder_text="Enter message...")
        self.message_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        self.message_entry.bind("<Return>", self.send_message_event)

        self.send_button = ctk.CTkButton(self.bottom_frame, text="Send", width=80, command=self.send_message_event)
        self.send_button.grid(row=0, column=1, padx=(5, 10), pady=10)

    # --- UI State Management ---
    def update_ui_state(self):
        # (Identical to previous version)
        if self.is_connected:
            self.connect_button.configure(text="Disconnect", state="normal")
            self.username_entry.configure(state="disabled")
            self.message_entry.configure(state="normal")
            self.send_button.configure(state="normal")
        elif self.is_connecting:
             self.connect_button.configure(text="Connecting...", state="disabled")
             self.username_entry.configure(state="disabled")
             self.message_entry.configure(state="disabled")
             self.send_button.configure(state="disabled")
        else: # Disconnected
            self.connect_button.configure(text="Connect", state="normal")
            self.username_entry.configure(state="normal")
            self.message_entry.configure(state="disabled")
            self.send_button.configure(state="disabled")

    # --- GUI Actions ---
    def send_message_event(self, event=None):
        """Handles sending message - schedules send operation."""
        print("DEBUG: send_message_event called")
        message = self.message_entry.get().strip()
        print(f"DEBUG: is_connected={self.is_connected} when sending")
        # Check if loop exists and is running before scheduling
        if message and self.is_connected and self.async_loop and self.async_loop.is_running():
            print(f"DEBUG: Scheduling message send: {message}")
            # Use run_coroutine_threadsafe to schedule the async send function
            # This is the key change for sending
            future = asyncio.run_coroutine_threadsafe(self._send_message_async(message), self.async_loop)
            # Optional: add callback to future for error handling from send
            # future.add_done_callback(self._send_done_callback)
            self.message_entry.delete(0, ctk.END)
        elif not self.is_connected:
            self.display_message("Not connected to server.", "error")
        elif not self.async_loop or not self.async_loop.is_running():
             self.display_message("Connection loop not active.", "error")
             print("DEBUG: Cannot send, async loop not active.")
        else:
             print(f"DEBUG: Message not sent (empty or other state): '{message}'")


    # Optional callback for send future
    # def _send_done_callback(self, future):
    #     try:
    #         future.result() # Raise exception if one occurred during send
    #     except Exception as e:
    #         print(f"Error occurred during scheduled send: {e}")
    #         self.display_message(f"--- Error sending message: {e} ---", "error")
    #         # Potentially trigger disconnect/cleanup here if send error is critical


    def display_message(self, message: str, tag: str = None):
        """Safely updates the chat display from any thread."""
        self.root.after(0, self._insert_message, message, tag)

    def _insert_message(self, message: str, tag: str = None):
        """Internal method to insert message, called by root.after."""
        # (Identical to previous version)
        self.chat_display.configure(state="normal")
        if tag:
            self.chat_display.insert(ctk.END, f"{message}\n", (tag,))
        else:
            if message.startswith("[Server]"): self.chat_display.insert(ctk.END, f"{message}\n", ("server",))
            elif message.startswith("---"): self.chat_display.insert(ctk.END, f"{message}\n", ("error",))
            elif message.startswith("Welcome!") or message.startswith("You are now connected"): self.chat_display.insert(ctk.END, f"{message}\n", ("info",))
            else: self.chat_display.insert(ctk.END, f"{message}\n", ("user",))
        self.chat_display.configure(state="disabled")
        self.chat_display.see(ctk.END)

    def update_status(self, text: str, color: str = "gray"):
        """Safely updates the status label from any thread."""
        self.root.after(0, self._update_status_label, text, color)

    def _update_status_label(self, text: str, color: str):
        """Internal method to update status label, called by root.after."""
        self.status_label.configure(text=f"Status: {text}", text_color=color)

    # --- Connection Logic (Modified for Manual Loop) ---
    def connect_disconnect(self):
        """Handles connect/disconnect button clicks."""
        if not self.connect_lock.acquire(blocking=False):
            print("Ignoring rapid connect/disconnect click.")
            return

        should_release_lock = True # Assume we need to release unless connection starts
        try:
            if self.is_connected:
                print("DEBUG: Disconnect initiated.")
                self.update_status("Disconnecting...", "orange")
                self.is_connected = False
                if self.async_loop and self.async_loop.is_running():
                    # Schedule cleanup to run on the loop, then stop it
                    print("DEBUG: Scheduling cleanup and stopping loop.")
                    self.async_loop.call_soon_threadsafe(self._schedule_stop)
                else:
                     # Fallback UI update if loop somehow already dead
                     self.root.after(0, self.update_ui_state)
                # Don't release lock here, let cleanup handle final state

            elif not self.is_connecting:
                print("DEBUG: Connect initiated.")
                self.username = self.username_entry.get().strip()
                if not self.username:
                    self.display_message("Please enter a username first.", "error")
                    self.update_status("Username required", "red")
                    return # Release lock in finally block

                self.is_connecting = True
                should_release_lock = False # Don't release lock, connection process owns it now
                self.update_ui_state()
                self.update_status(f"Connecting to {self.host}:{self.port}...", "orange")

                # Start the asyncio tasks in a separate thread using manual loop
                self.connection_thread = threading.Thread(target=self._run_async_client_manual_loop, daemon=True)
                self.connection_thread.start()

        finally:
            if should_release_lock and self.connect_lock.locked():
                self.connect_lock.release()

    def _run_async_client_manual_loop(self):
        """Runs the asyncio event loop manually."""
        print("DEBUG: Background thread started")
        try:
            # Create and set the event loop for this thread
            self.async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.async_loop)

            # Run the main connection coroutine until it completes
            self.async_loop.run_until_complete(self.client_connection_loop())

        except Exception as e:
            self.update_status(f"Async loop error: {e}", "red")
            print(f"Error in async loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("DEBUG: Async loop processing finished, closing loop...")
            # Gracefully stop and close the loop
            if self.async_loop:
                 # Run pending callbacks, shutdown executors
                 try:
                    # Give tasks a chance to finish cancelling if stop was called
                    # shutdown_asyncgens requires Python 3.6+
                    if hasattr(self.async_loop, 'shutdown_asyncgens'):
                         self.async_loop.run_until_complete(self.async_loop.shutdown_asyncgens())
                 except Exception as e_sg: print(f"Error during shutdown_asyncgens: {e_sg}")

                 if not self.async_loop.is_closed():
                      self.async_loop.close()
                      print("DEBUG: Async loop closed.")
                 else:
                      print("DEBUG: Async loop was already closed.")

            self.async_loop = None # Clear the loop reference
            self.is_connecting = False
            # Ensure final state update if loop exits unexpectedly
            if not self.is_connected:
                 self.update_status("Disconnected (Loop Ended)", "gray")
                 self.root.after(0, self.update_ui_state)
                 if self.connect_lock.locked(): # Release lock on final exit
                     self.connect_lock.release()
            print("DEBUG: Background thread finished")


    async def client_connection_loop(self):
        """The main async function managing connection and the receiver task."""
        self.connection_task = asyncio.current_task() # Reference to this task
        try:
            self.update_status(f"Opening connection...", "orange")
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=CONNECT_TIMEOUT
            )
            peer_name = self.writer.get_extra_info('peername', 'Unknown Server')
            self.update_status(f"Connected to {peer_name}", "light green")
            self.is_connected = True
            self.is_connecting = False
            # Release lock now that we are connected successfully
            if self.connect_lock.locked():
                 self.connect_lock.release()
            self.root.after(0, self.update_ui_state)

            # Start ONLY the reader task
            print("DEBUG: Creating receive task...")
            self.receive_task = asyncio.create_task(self.handle_received_data_async())
            print("DEBUG: Receive task created. Waiting for it to complete...")

            # Wait ONLY for the receive task to finish or be cancelled
            await self.receive_task
            print("DEBUG: Receive task finished or was cancelled.")

        except ConnectionRefusedError:
            self.update_status(f"Connection refused. Server offline?", "red")
            self.display_message(f"--- Connection refused. Server might be offline or firewall blocking port {self.port}. ---", "error")
        except asyncio.TimeoutError:
            self.update_status(f"Connection timed out.", "red")
            self.display_message(f"--- Connection attempt timed out after {CONNECT_TIMEOUT} seconds. ---", "error")
        except OSError as e:
            self.update_status(f"Network error: {e}", "red")
            self.display_message(f"--- Network error: {e} ---", "error")
        except asyncio.CancelledError:
             self.update_status("Disconnecting (Loop Cancelled)...", "orange")
             print("DEBUG: client_connection_loop cancelled.") # Expected on disconnect
             # Cleanup happens in finally
             raise # Re-raise to signal cancellation happened
        except Exception as e:
            self.update_status(f"Connection error: {e}", "red")
            self.display_message(f"--- Unexpected connection error: {e} ---", "error")
            import traceback
            traceback.print_exc()
        finally:
            print("DEBUG: client_connection_loop entering finally block.")
            # This block executes when the loop finishes naturally (receiver ends)
            # or when it's cancelled externally.
            # Perform resource cleanup here, but don't stop the loop itself (it's ending).
            await self._perform_cleanup_resources()
            # Release lock if somehow still held on error exit
            if self.connect_lock.locked():
                 self.connect_lock.release()


    async def _perform_cleanup_resources(self):
        """Closes connections and cancels tasks safely (modified for manual loop)."""
        print("DEBUG: Performing resource cleanup (_perform_cleanup_resources)...")
        # No longer setting flags here, state managed by connect/disconnect flow

        # Cancel receiver task if it exists and isn't done (might be if loop exited abnormally)
        if self.receive_task and not self.receive_task.done():
            print("DEBUG: Cancelling receive task during cleanup.")
            self.receive_task.cancel()
            try:
                await self.receive_task # Allow cancellation to be processed
            except asyncio.CancelledError:
                pass # Expected
            except Exception as e:
                 print(f"Error awaiting cancelled receive_task: {e}")


        # Close writer
        if self.writer and not self.writer.is_closing():
            print("DEBUG: Closing writer during cleanup...")
            # Send quit only if we were connected before cleanup started
            # This requires tracking previous state or passing it, maybe simplify:
            # Just close the writer cleanly. Server should handle abrupt close.
            self.writer.close()
            try:
                 await self.writer.wait_closed()
                 print("DEBUG: Writer closed successfully.")
            except Exception as e:
                 print(f"Error during writer wait_closed: {e}")

        # Reset state variables
        self.writer = None
        self.reader = None
        self.receive_task = None
        # self.connection_task = None # Don't clear this, loop might still be running finally block
        print("DEBUG: Resource cleanup finished.")


    async def handle_received_data_async(self):
        """Coroutine to handle receiving data from the server."""
        first_message = True
        print("DEBUG: handle_received_data_async started.") # <<< DEBUG >>>
        try: # Add top-level try for better error catching
            while self.reader:
                    print("DEBUG: Receiver awaiting readline...") # <<< DEBUG >>>
                    data = await self.reader.readline()
                    print(f"DEBUG: Receiver got data: {data!r}") # <<< DEBUG >>>
                    if not data:
                        self.display_message("--- Server closed the connection. ---", "error")
                        break # EOF

                    message = data.decode().strip()
                    if first_message and message.startswith("Welcome! Please enter your username:"):
                        print(f"DEBUG: Server prompted for username. Scheduling send: {self.username}")
                        # Use threadsafe call to send username
                        if self.async_loop and self.async_loop.is_running():
                             asyncio.run_coroutine_threadsafe(self._send_message_async(f"{self.username}"), self.async_loop)
                        else: print("DEBUG: Loop not running, cannot send username.")
                        first_message = False
                        self.display_message("Username sent to server.", "info")
                        continue

                    self.display_message(message)
                    first_message = False

        except asyncio.CancelledError:
            print("DEBUG: Receive task cancelled.") # Expected
        except ConnectionResetError:
            self.display_message("--- Connection to server lost (reset). ---", "error")
            print("DEBUG: ConnectionResetError in receiver.")
        except Exception as e:
            self.display_message(f"--- Error receiving data: {e} ---", "error")
            print(f"DEBUG: Receiver error: {e}")
            import traceback
            traceback.print_exc()
        finally:
             print("DEBUG: handle_received_data_async finished.")
             # If the receiver stops, the connection is effectively dead.
             # We should signal the main connection loop to stop if it hasn't already.
             # This happens naturally when client_connection_loop awaits this task.


    async def _send_message_async(self, message: str):
        """The actual async function that sends data, run via threadsafe."""
        if self.writer and not self.writer.is_closing():
            try:
                message_bytes = message.encode() + b'\n'
                print(f"DEBUG: [ASYNC SEND] Writing bytes: {message_bytes!r}")
                self.writer.write(message_bytes)
                print("DEBUG: [ASYNC SEND] Write successful, now draining...")
                await self.writer.drain()
                print("DEBUG: [ASYNC SEND] Drain successful.")

                # No longer automatically quitting here after sending 'quit'
                # Let server handle 'quit' command and close connection

            except ConnectionResetError:
                self.display_message("--- Connection lost while sending. ---", "error")
                print("DEBUG: [ASYNC SEND] ConnectionResetError")
                # Schedule cleanup/stop if send fails critically
                if self.async_loop and self.async_loop.is_running():
                     self.async_loop.call_soon_threadsafe(self._schedule_stop)
            except Exception as e:
                 self.display_message(f"--- Error sending data: {e} ---", "error")
                 print(f"DEBUG: [ASYNC SEND] ERROR: {e}")
                 import traceback
                 traceback.print_exc()
                 # Schedule cleanup/stop on other errors?
                 if self.async_loop and self.async_loop.is_running():
                      self.async_loop.call_soon_threadsafe(self._schedule_stop)
        else:
             print("DEBUG: [ASYNC SEND] Writer not available or closing.")


    def _schedule_stop(self):
        """Schedules the cancellation of the main loop task and stops the loop."""
        print("DEBUG: _schedule_stop called.")
        if self.async_loop and self.async_loop.is_running():
            print("DEBUG: Scheduling cancellation of connection_task.")
            # Cancel the main connection loop first
            if self.connection_task and not self.connection_task.done():
                self.async_loop.call_soon_threadsafe(self.connection_task.cancel)
            # Stop the loop itself, allows run_until_complete to return
            print("DEBUG: Scheduling loop stop.")
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
        # Update UI after scheduling stop
        self.is_connected = False
        self.is_connecting = False
        self.update_status("Disconnecting (Scheduled Stop)...", "orange")
        self.root.after(0, self.update_ui_state)
        if self.connect_lock.locked(): # Ensure lock released on scheduled stop
             self.connect_lock.release()

    # --- Window Closing ---
    def on_closing(self):
        """Handle the window close button."""
        print("Window close requested.")
        # Ensure lock released if held
        if self.connect_lock.locked():
             print("DEBUG: Releasing connect lock during closing.")
             self.connect_lock.release()

        if self.is_connected or self.is_connecting:
            print("DEBUG: Calling disconnect logic from on_closing.")
            # Use the schedule stop mechanism if loop is running
            if self.async_loop and self.async_loop.is_running():
                 self._schedule_stop()
            else: # Fallback if loop isn't running but state is weird
                 self.is_connected = False
                 self.is_connecting = False
                 self.update_status("Disconnected", "gray")
                 self.update_ui_state()
            # Give disconnect a moment to process before destroying window
            self.root.after(500, self.root.destroy)
        else:
            self.root.destroy()

    def run(self):
        """Starts the Tkinter main loop."""
        self.root.mainloop()


# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Client")
    parser.add_argument('--host', default=DEFAULT_SERVER_HOST,
                        help=f"Server host address (default: {DEFAULT_SERVER_HOST})")
    parser.add_argument('--port', type=int, default=DEFAULT_SERVER_PORT,
                        help=f"Server port number (default: {DEFAULT_SERVER_PORT})")

    args = parser.parse_args()

    root = ctk.CTk()
    app = ChatClientGUI(root, args.host, args.port)
    app.run()

    print(f"{APP_NAME} terminated.")
