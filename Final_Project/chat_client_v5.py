import os
import customtkinter as ctk
import asyncio
import argparse
import sys
import threading
import time
import traceback # Import traceback at top
# Import the necessary exception type if you need specific handling
from openai import AsyncOpenAI, AuthenticationError, OpenAIError

# --- Configuration ---
DEFAULT_SERVER_HOST = '000.00.000.00' # Replace with your server's IP if needed
DEFAULT_SERVER_PORT = 0000
APP_NAME = "Comprendo.v5" # Updated name
CONNECT_TIMEOUT = 10  # Seconds

# --- Language List ---
LANGUAGES = [
    "English", "Spanish", "French", "German", "Italian", "Portuguese", "Dutch",
    "Russian", "Chinese (Simplified)", "Chinese (Traditional)", "Japanese",
    "Korean", "Arabic", "Hindi", "Bengali"
]

# --- GUI Class ---
class ChatClientGUI:
    def __init__(self, root, host, port): # Host/Port from args are now initial values
        self.root = root
        # Store initial values, but GUI will use StringVars primarily
        self.initial_host = host
        self.initial_port = port

        # Asyncio state
        self.reader = None
        self.writer = None
        self.receive_task = None
        self.connection_task = None
        self.async_loop = None
        self.is_connected = False
        self.is_connecting = False
        self.connect_lock = threading.Lock()
        self.username = ""
        self.connection_thread = None

        # Language State
        self.language_var = ctk.StringVar(value=LANGUAGES[0])
        self.desired_language = self.language_var.get()
        print(f"DEBUG: Initial desired_language: {self.desired_language}")

        # OpenAI API Key State
        self.api_key_var = ctk.StringVar(value=os.getenv("OPENAI_API_KEY", ""))
        self.openai_client = None
        self._update_openai_client() # Initial update based on env/default

        # Server Host/Port State
        self.host_var = ctk.StringVar(value=self.initial_host)
        self.port_var = ctk.StringVar(value=str(self.initial_port))

        # GUI setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root.title(APP_NAME)
        self.root.geometry("600x650")
        self.root.minsize(500, 450)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=0)

        self.create_widgets()
        self.update_ui_state()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # --- Top Frame ---
        self.top_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        self.top_frame.grid_columnconfigure(1, weight=2)
        self.top_frame.grid_columnconfigure(3, weight=1)

        # Row 0: Username
        self.username_label = ctk.CTkLabel(self.top_frame, text="Username:")
        self.username_label.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
        self.username_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Enter username")
        self.username_entry.grid(row=0, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        # Row 1: Host / Port / Connect Button
        self.host_label = ctk.CTkLabel(self.top_frame, text="Server Host:")
        self.host_label.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="w")
        self.host_entry = ctk.CTkEntry(self.top_frame, textvariable=self.host_var)
        self.host_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.port_label = ctk.CTkLabel(self.top_frame, text="Port:")
        self.port_label.grid(row=1, column=2, padx=(10, 5), pady=5, sticky="w")
        self.port_entry = ctk.CTkEntry(self.top_frame, textvariable=self.port_var, width=70)
        self.port_entry.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        self.connect_button = ctk.CTkButton(self.top_frame, text="Connect", width=100, command=self.connect_disconnect)
        self.connect_button.grid(row=1, column=4, padx=(10, 10), pady=5)

        # Row 2: Status
        self.status_label = ctk.CTkLabel(self.top_frame, text="Status: Disconnected", text_color="gray", anchor="w")
        self.status_label.grid(row=2, column=0, columnspan=5, padx=10, pady=(5, 5), sticky="ew")

        # Row 3: API Key
        self.api_key_label = ctk.CTkLabel(self.top_frame, text="OpenAI Key:")
        self.api_key_label.grid(row=3, column=0, padx=(10, 5), pady=5, sticky="w")
        self.api_key_entry = ctk.CTkEntry(
            self.top_frame, textvariable=self.api_key_var,
            placeholder_text="Enter OpenAI API Key (optional)", show="*"
        )
        self.api_key_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        self.api_key_entry.bind("<Return>", self.set_api_key_event)
        self.set_api_key_button = ctk.CTkButton(
            self.top_frame, text="Set Key", width=100, command=self.set_api_key
        )
        self.set_api_key_button.grid(row=3, column=4, padx=(5, 10), pady=5)

        # Row 4: Language
        self.language_label = ctk.CTkLabel(self.top_frame, text="Language:")
        self.language_label.grid(row=4, column=0, padx=(10, 5), pady=(5, 10), sticky="w")
        self.language_menu = ctk.CTkOptionMenu(
            self.top_frame, values=LANGUAGES, variable=self.language_var,
            command=self.language_selected, width=200
        )
        self.language_menu.grid(row=4, column=1, padx=5, pady=(5, 10), sticky="w")

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

    def language_selected(self, selected_language):
        self.desired_language = selected_language # Already gets the exact value
        print(f"DEBUG: Language selected: {self.desired_language}")

    def _update_openai_client(self):
        # --- MODIFIED: Strip whitespace from key ---
        key = self.api_key_var.get().strip() # Trim leading/trailing spaces
        if key and key != "INSERT YOUR KEY HERE":
            try:
                self.openai_client = AsyncOpenAI(api_key=key)
                print("DEBUG: OpenAI client updated with new key.")
                return True
            except Exception as e:
                print(f"ERROR: Failed to initialize OpenAI client: {e}")
                self.openai_client = None
                return False
        else:
            print("DEBUG: OpenAI API key is empty or placeholder, client set to None.")
            self.openai_client = None
            return False

    def set_api_key(self):
        print("DEBUG: set_api_key called")
        # --- MODIFIED: Allow setting key while connected ---
        # Removed check: if self.is_connected or self.is_connecting: ... return
        if self._update_openai_client():
            # Display status update briefly, then potentially revert if connected
            if self.is_connected:
                 # If connected, show temporary confirmation then revert to connected status
                 current_status = self.status_label.cget("text") # Get current status text
                 self.update_status("OpenAI API Key Set", "light blue")
                 self.root.after(2000, lambda: self.status_label.configure(text=current_status)) # Revert after 2s
            else:
                 # If disconnected, keep the API key status
                 self.update_status("OpenAI API Key Set", "light blue")
        else:
            self.update_status("OpenAI API Key Cleared or Invalid", "orange")
             # If disconnected, make sure status reflects missing key
            if not self.is_connected and not self.is_connecting:
                 self.update_status("Disconnected. OpenAI Key Missing.", "gray")


    def set_api_key_event(self, event=None):
        self.set_api_key()

    def update_ui_state(self):
        api_key_set = bool(self.openai_client)
        connected_or_connecting = self.is_connected or self.is_connecting

        self.connect_button.configure(
            text="Disconnect" if self.is_connected else "Connecting..." if self.is_connecting else "Connect",
            state="normal" if not self.is_connecting else "disabled"
        )
        # Only disable these when connecting (allow changes when disconnected or connected)
        self.username_entry.configure(state="disabled" if connected_or_connecting else "normal")
        self.host_entry.configure(state="disabled" if connected_or_connecting else "normal")
        self.port_entry.configure(state="disabled" if connected_or_connecting else "normal")

        # --- MODIFIED: Keep these enabled when connected ---
        self.language_menu.configure(state="disabled" if self.is_connecting else "normal") # Only disable while connecting
        self.api_key_entry.configure(state="disabled" if self.is_connecting else "normal") # Only disable while connecting
        self.set_api_key_button.configure(state="disabled" if self.is_connecting else "normal") # Only disable while connecting

        # Enable message input only when fully connected
        self.message_entry.configure(state="normal" if self.is_connected else "disabled")
        self.send_button.configure(state="normal" if self.is_connected else "disabled")

        # Update status label based on connection and API key state when disconnected
        # (Keep previous logic - status updates for connected state happen elsewhere)
        if not connected_or_connecting:
             if api_key_set:
                 self.update_status("Disconnected. OpenAI Key Ready.", "light blue")
             else:
                 self.update_status("Disconnected. OpenAI Key Missing.", "gray")

    def send_message_event(self, event=None):
        print("DEBUG: send_message_event called")
        # --- Uses strip already ---
        message = self.message_entry.get().strip()
        print(f"DEBUG: is_connected={self.is_connected} when sending")
        if message and self.is_connected and self.async_loop and self.async_loop.is_running():
            print(f"DEBUG: Scheduling message send: {message}")
            asyncio.run_coroutine_threadsafe(self._send_message_async(message), self.async_loop)
            self.message_entry.delete(0, ctk.END)
        elif not self.is_connected:
            self.display_message("Not connected to server.", "error")
        elif not self.async_loop or not self.async_loop.is_running():
             self.display_message("Connection loop not active.", "error")
             print("DEBUG: Cannot send, async loop not active.")
        else:
            print(f"DEBUG: Message not sent (empty or other state): '{message}'")

    def display_message(self, message: str, tag: str = None):
        self.root.after(0, self._insert_message, message, tag)

    def _insert_message(self, message: str, tag: str = None):
        self.chat_display.configure(state="normal")
        if tag: self.chat_display.insert(ctk.END, f"{message}\n", (tag,))
        else:
            if message.startswith("[Server]"): self.chat_display.insert(ctk.END, f"{message}\n", ("server",))
            elif message.startswith("---"): self.chat_display.insert(ctk.END, f"{message}\n", ("error",))
            elif message.startswith("Welcome!") or message.startswith("You are now connected"): self.chat_display.insert(ctk.END, f"{message}\n", ("info",))
            else: self.chat_display.insert(ctk.END, f"{message}\n", ("user",))
        self.chat_display.configure(state="disabled"); self.chat_display.see(ctk.END)

    def update_status(self, text: str, color: str = "gray"):
        self.root.after(0, self._update_status_label, text, color)

    def _update_status_label(self, text: str, color: str):
        self.status_label.configure(text=f"Status: {text}", text_color=color)

    def connect_disconnect(self):
        if not self.connect_lock.acquire(blocking=False):
            print("Ignoring rapid connect/disconnect click.")
            return
        should_release = True
        try:
            if self.is_connected:
                print("DEBUG: Disconnect initiated.")
                self.update_status("Disconnecting...", "orange")
                self.is_connected = False
                if self.async_loop and self.async_loop.is_running():
                    self.async_loop.call_soon_threadsafe(self._schedule_stop)
                else:
                    self.root.after(0, self.update_ui_state)
            elif not self.is_connecting:
                print("DEBUG: Connect initiated.")
                # --- Uses strip already ---
                self.username = self.username_entry.get().strip()
                host_to_use = self.host_var.get().strip()
                port_str = self.port_var.get().strip()

                if not self.username:
                    self.display_message("Please enter a username first.", "error")
                    self.update_status("Username required", "red")
                    return
                if not host_to_use:
                    self.display_message("Server Host cannot be empty.", "error")
                    self.update_status("Host required", "red")
                    return
                try:
                    port_to_use = int(port_str)
                    if not (0 < port_to_use < 65536):
                        raise ValueError("Port out of range (1-65535)")
                except ValueError as e:
                    self.display_message(f"Invalid Port: '{port_str}'. {e}", "error")
                    self.update_status("Invalid Port", "red")
                    return

                self.is_connecting = True
                should_release = False
                self.update_ui_state()
                self.update_status(f"Connecting to {host_to_use}:{port_to_use}...", "orange")
                self.connection_thread = threading.Thread(
                    target=self._run_async_client_manual_loop,
                    args=(host_to_use, port_to_use),
                    daemon=True
                )
                self.connection_thread.start()
        finally:
            if should_release and self.connect_lock.locked():
                self.connect_lock.release()

    def _run_async_client_manual_loop(self, host_to_connect, port_to_connect):
        print(f"DEBUG: Background thread started for {host_to_connect}:{port_to_connect}")
        try:
            self.async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.async_loop)
            self.async_loop.run_until_complete(self.client_connection_loop(host_to_connect, port_to_connect))
        except Exception as e:
            self.update_status(f"Async loop error: {e}", "red")
            print(f"Error in async loop: {e}")
            traceback.print_exc()
        finally:
            print("DEBUG: Async loop processing finished, closing loop...")
            if self.async_loop:
                 try:
                    if hasattr(self.async_loop, 'shutdown_asyncgens'):
                        self.async_loop.run_until_complete(self.async_loop.shutdown_asyncgens())
                 except Exception as e_sg:
                     print(f"Error during shutdown_asyncgens: {e_sg}")
                 if not self.async_loop.is_closed():
                     self.async_loop.close()
                     print("DEBUG: Async loop closed.")
                 else:
                     print("DEBUG: Async loop was already closed.")
            self.async_loop = None
            self.is_connecting = False
            if not self.is_connected:
                 self.update_status("Disconnected (Loop Ended)", "gray")
                 self.root.after(0, self.update_ui_state)
                 if self.connect_lock.locked():
                     self.connect_lock.release()
            print("DEBUG: Background thread finished")

    async def client_connection_loop(self, host_to_connect, port_to_connect):
        self.connection_task = asyncio.current_task()
        try:
            self.update_status(f"Opening connection to {host_to_connect}:{port_to_connect}...", "orange")
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(host_to_connect, port_to_connect),
                timeout=CONNECT_TIMEOUT
            )
            peer = self.writer.get_extra_info('peername', 'Unknown')
            self.update_status(f"Connected to {peer}", "light green")
            self.is_connected = True
            self.is_connecting = False
            if self.connect_lock.locked():
                self.connect_lock.release()
            self.root.after(0, self.update_ui_state) # Ensure UI reflects connected state (enables lang/key)
            print("DEBUG: Creating receive task...")
            self.receive_task = asyncio.create_task(self.handle_received_data_async())
            print("DEBUG: Receive task created. Waiting for it to complete...")
            await self.receive_task
            print("DEBUG: Receive task finished or was cancelled.")
        except ConnectionRefusedError:
            self.update_status("Connection refused. Server offline?", "red")
            self.display_message(f"--- Connection refused to {host_to_connect}:{port_to_connect}. ---", "error")
        except asyncio.TimeoutError:
            self.update_status("Connection timed out.", "red")
            self.display_message(f"--- Connection to {host_to_connect}:{port_to_connect} timed out. ---", "error")
        except asyncio.CancelledError:
            self.update_status("Disconnecting (Loop Cancelled)...", "orange")
            raise
        except Exception as e:
            self.update_status(f"Connection error: {e}", "red")
            self.display_message(f"--- Error connecting to {host_to_connect}:{port_to_connect}: {e} ---", "error")
            traceback.print_exc()
        finally:
            print("DEBUG: client_connection_loop entering finally block.")
            await self._perform_cleanup_resources()
            if self.connect_lock.locked():
                self.connect_lock.release()

    async def _perform_cleanup_resources(self):
        print("DEBUG: Performing resource cleanup (_perform_cleanup_resources)...")
        if self.receive_task and not self.receive_task.done():
            print("DEBUG: Cancelling receive task during cleanup.")
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                 print(f"Error awaiting cancelled receive_task: {e}")
        if self.writer and not self.writer.is_closing():
            print("DEBUG: Closing writer during cleanup.")
            self.writer.close()
            try:
                 await self.writer.wait_closed()
                 print("DEBUG: Writer closed successfully.")
            except Exception as e:
                 print(f"Error during writer wait_closed: {e}")
        self.writer = None
        self.reader = None
        self.receive_task = None
        print("DEBUG: Resource cleanup finished.")

    async def handle_received_data_async(self):
        first_message = True
        print("DEBUG: handle_received_data_async started.")
        try:
            while self.reader:
                print("DEBUG: Receiver awaiting readline...")
                data = await self.reader.readline()
                print(f"DEBUG: Receiver got data: {data!r}")
                if not data:
                    self.display_message("--- Server closed the connection. ---", "error")
                    break
                message = data.decode().strip()
                if not message:
                    continue

                if first_message and message.startswith("Welcome!"):
                    print(f"DEBUG: Server prompted for username. Scheduling send: {self.username}")
                    if self.async_loop and self.async_loop.is_running():
                        asyncio.run_coroutine_threadsafe(self._send_message_async(f"{self.username}"), self.async_loop)
                    else:
                        print("DEBUG: Loop not running, cannot send username.")
                    first_message = False
                    self.display_message("Username sent to server.", "info")
                    continue

                translated_message = await self.translate_message_if_needed(message)
                self.display_message(translated_message)
                first_message = False
        except asyncio.CancelledError:
            print("DEBUG: Receive task cancelled.")
        except ConnectionResetError:
            self.display_message("--- Connection to server lost (reset). ---", "error")
            print("DEBUG: ConnectionResetError in receiver.")
        except Exception as e:
            self.display_message(f"--- Error receiving data: {e} ---", "error")
            print(f"DEBUG: Receiver error: {e}")
            traceback.print_exc()
        finally:
            print("DEBUG: handle_received_data_async finished.")

    async def _send_message_async(self, message: str):
        if self.writer and not self.writer.is_closing():
            try:
                message_bytes = message.encode() + b'\n'
                print(f"DEBUG: [ASYNC SEND] Writing bytes: {message_bytes!r}")
                self.writer.write(message_bytes)
                print("DEBUG: [ASYNC SEND] Write successful, now draining...")
                await self.writer.drain()
                print("DEBUG: [ASYNC SEND] Drain successful.")
            except ConnectionResetError:
                self.display_message("--- Connection lost while sending. ---", "error")
                print("DEBUG: [ASYNC SEND] ConnectionResetError")
                if self.async_loop and self.async_loop.is_running():
                    self.async_loop.call_soon_threadsafe(self._schedule_stop)
            except Exception as e:
                 self.display_message(f"--- Error sending data: {e} ---", "error")
                 print(f"DEBUG: [ASYNC SEND] ERROR: {e}")
                 traceback.print_exc()
                 if self.async_loop and self.async_loop.is_running():
                      self.async_loop.call_soon_threadsafe(self._schedule_stop)
        else:
            print("DEBUG: [ASYNC SEND] Writer not available or closing.")

    async def translate_message_if_needed(self, message: str) -> str:
        if not self.openai_client:
            print("DEBUG: OpenAI client not configured, skipping translation.")
            return message
        if message.startswith("[Server]") or message.startswith(f"[{self.username}]"):
            print(f"DEBUG: Skipping translation for server/own message: {message[:30]}...")
            return message

        print(f"DEBUG: Attempting translation check for: {message[:50]}... (Target: {self.desired_language})")
        system_prompt = (f"You are a translator. Detect the language of the following user message. If the language is NOT {self.desired_language}, translate the message accurately into {self.desired_language}. If the message IS ALREADY in {self.desired_language}, return the original message unchanged. Respond ONLY with the final text (either the original or the translation), with no extra explanations or introductory phrases.")
        try:
            start_time = time.monotonic()
            resp = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
                temperature=0.2, max_tokens=int(len(message) * 1.5) + 50
            )
            end_time = time.monotonic()
            processed_text = resp.choices[0].message.content.strip()
            if processed_text == message:
                print(f"DEBUG: Translation determined unnecessary by LLM ({end_time - start_time:.2f}s).")
            else:
                print(f"DEBUG: Translation performed ({end_time - start_time:.2f}s): {processed_text[:50]}...")
            return processed_text
        except AuthenticationError as e:
            error_msg = "--- Translation failed: Invalid OpenAI API Key. ---"
            print(f"DEBUG: OpenAI Authentication Error: {e}")
            self.display_message(error_msg, "error")
            self.openai_client = None
            self._update_openai_client() # Attempt to re-init (will likely fail again until key fixed)
            self.update_ui_state() # Update UI
            return message
        except OpenAIError as e:
            error_msg = f"--- Translation error: {e} ---"
            print(f"DEBUG: OpenAI API Error: {e}")
            self.display_message(error_msg, "error")
            return message
        except Exception as e:
            error_msg = f"--- Unexpected translation error: {e} ---"
            print(f"DEBUG: Unexpected translation error: {e}")
            traceback.print_exc()
            self.display_message(error_msg, "error")
            return message

    def _schedule_stop(self):
        print("DEBUG: _schedule_stop called.")
        if self.async_loop and self.async_loop.is_running():
            print("DEBUG: Scheduling cancellation of connection_task.")
            if self.connection_task and not self.connection_task.done():
                self.async_loop.call_soon_threadsafe(self.connection_task.cancel)
            print("DEBUG: Scheduling loop stop.")
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
        self.is_connected = False
        self.is_connecting = False
        self.update_status("Disconnecting (Scheduled Stop)...", "orange")
        self.root.after(0, self.update_ui_state)
        if self.connect_lock.locked():
            self.connect_lock.release()

    def on_closing(self):
        print("Window close requested.")
        if self.connect_lock.locked():
            print("DEBUG: Releasing connect lock during closing.")
            self.connect_lock.release()
        if self.is_connected or self.is_connecting:
            print("DEBUG: Calling disconnect logic from on_closing.")
            if self.async_loop and self.async_loop.is_running():
                self._schedule_stop()
            else:
                self.is_connected = False
                self.is_connecting = False
                self.update_status("Disconnected", "gray")
                self.update_ui_state()
            self.root.after(500, self.root.destroy)
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Client")
    parser.add_argument('--host', default=DEFAULT_SERVER_HOST, help="Default server host address")
    parser.add_argument('--port', type=int, default=DEFAULT_SERVER_PORT, help="Default server port number")
    args = parser.parse_args()
    try:
        import openai
    except ImportError:
        print("ERROR: 'openai' package not found. Please install it using:\npip install openai")
        # sys.exit(1)

    root = ctk.CTk()
    app = ChatClientGUI(root, args.host, args.port)
    app.run()

    print(f"{APP_NAME} terminated.")
