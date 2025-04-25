import os
import customtkinter as ctk
import asyncio
import argparse
import sys
import threading
import time
from openai import AsyncOpenAI

# --- Insert Key Below ---
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "INSERT YOUR KEY HERE"))

# --- Configuration ---
DEFAULT_SERVER_HOST = '000.00.000.00'
DEFAULT_SERVER_PORT = 8888
APP_NAME = "Async Chat V3"
CONNECT_TIMEOUT = 10  # Seconds

# --- Language List ---
LANGUAGES = [
    "English",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Dutch",
    "Russian",
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Japanese",
    "Korean",
    "Arabic",
    "Hindi",
    "Bengali"
]

# --- OpenAI Client Setup ---
class ChatClientGUI:
    def __init__(self, root, host, port):
        self.root = root
        self.host = host
        self.port = port

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

        # --- Language State ---
        self.language_var = ctk.StringVar(value=LANGUAGES[0])
        self.desired_language = self.language_var.get()
        print(f"DEBUG: Initial desired_language: {self.desired_language}")

        # GUI setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root.title(APP_NAME)
        self.root.geometry("600x550")
        self.root.minsize(400, 350)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=0)

        self.create_widgets()
        self.update_ui_state()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # Top frame (username, connect, language)
        self.top_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.username_label = ctk.CTkLabel(self.top_frame, text="Username:")
        self.username_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        self.username_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Enter your username")
        self.username_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.connect_button = ctk.CTkButton(
            self.top_frame, text="Connect", width=100,
            command=self.connect_disconnect
        )
        self.connect_button.grid(row=0, column=2, padx=(5, 10), pady=10, sticky="e")

        self.status_label = ctk.CTkLabel(
            self.top_frame, text="Status: Disconnected",
            text_color="gray", anchor="w"
        )
        self.status_label.grid(
            row=1, column=0, columnspan=3,
            padx=10, pady=(0, 5), sticky="ew"
        )

        # Language dropdown
        self.language_label = ctk.CTkLabel(self.top_frame, text="Language:")
        self.language_label.grid(row=2, column=0, padx=(10, 5), pady=(5, 10), sticky="w")
        self.language_menu = ctk.CTkOptionMenu(
            self.top_frame,
            values=LANGUAGES,
            variable=self.language_var,
            command=self.language_selected,
            width=200
        )
        self.language_menu.grid(row=2, column=1, columnspan=2, padx=5, pady=(5, 10), sticky="w")

        # Chat display
        self.chat_display = ctk.CTkTextbox(
            self.root, state="disabled", wrap="word",
            corner_radius=6, font=("Segoe UI", 13)
        )
        self.chat_display.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.chat_display.tag_config("server", foreground="#A0A0FF")
        self.chat_display.tag_config("user", foreground="#FFFFFF")
        self.chat_display.tag_config("error", foreground="#FF8080")
        self.chat_display.tag_config("info", foreground="#A0A0A0")

        # Bottom frame (message entry)
        self.bottom_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.bottom_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.bottom_frame.grid_columnconfigure(0, weight=1)

        self.message_entry = ctk.CTkEntry(self.bottom_frame, placeholder_text="Enter message...")
        self.message_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        self.message_entry.bind("<Return>", self.send_message_event)
        self.send_button = ctk.CTkButton(
            self.bottom_frame, text="Send", width=80,
            command=self.send_message_event
        )
        self.send_button.grid(row=0, column=1, padx=(5, 10), pady=10)

    def language_selected(self, selected_language):
        """Called when the user picks a new language."""
        self.desired_language = selected_language
        print(f"DEBUG: Language selected: {self.desired_language}")

    def update_ui_state(self):
        if self.is_connected:
            self.connect_button.configure(text="Disconnect", state="normal")
            self.username_entry.configure(state="disabled")
            self.language_menu.configure(state="disabled")
            self.message_entry.configure(state="normal")
            self.send_button.configure(state="normal")
        elif self.is_connecting:
            self.connect_button.configure(text="Connecting...", state="disabled")
            self.username_entry.configure(state="disabled")
            self.language_menu.configure(state="disabled")
            self.message_entry.configure(state="disabled")
            self.send_button.configure(state="disabled")
        else:
            self.connect_button.configure(text="Connect", state="normal")
            self.username_entry.configure(state="normal")
            self.language_menu.configure(state="normal")
            self.message_entry.configure(state="disabled")
            self.send_button.configure(state="disabled")

    def send_message_event(self, event=None):
        print("DEBUG: send_message_event called")
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
        if tag:
            self.chat_display.insert(ctk.END, f"{message}\n", (tag,))
        else:
            if message.startswith("[Server]"):
                self.chat_display.insert(ctk.END, f"{message}\n", ("server",))
            elif message.startswith("---"):
                self.chat_display.insert(ctk.END, f"{message}\n", ("error",))
            elif message.startswith("Welcome!") or message.startswith("You are now connected"):
                self.chat_display.insert(ctk.END, f"{message}\n", ("info",))
            else:
                self.chat_display.insert(ctk.END, f"{message}\n", ("user",))
        self.chat_display.configure(state="disabled")
        self.chat_display.see(ctk.END)

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
                self.username = self.username_entry.get().strip()
                if not self.username:
                    self.display_message("Please enter a username first.", "error")
                    self.update_status("Username required", "red")
                    return

                self.is_connecting = True
                should_release = False
                self.update_ui_state()
                self.update_status(f"Connecting to {self.host}:{self.port}...", "orange")
                self.connection_thread = threading.Thread(
                    target=self._run_async_client_manual_loop, daemon=True
                )
                self.connection_thread.start()
        finally:
            if should_release and self.connect_lock.locked():
                self.connect_lock.release()

    def _run_async_client_manual_loop(self):
        print("DEBUG: Background thread started")
        try:
            self.async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.async_loop)
            self.async_loop.run_until_complete(self.client_connection_loop())
        except Exception as e:
            self.update_status(f"Async loop error: {e}", "red")
            print(f"Error in async loop: {e}")
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

    async def client_connection_loop(self):
        self.connection_task = asyncio.current_task()
        try:
            self.update_status("Opening connection...", "orange")
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT
            )
            peer = self.writer.get_extra_info('peername', 'Unknown')
            self.update_status(f"Connected to {peer}", "light green")
            self.is_connected = True
            self.is_connecting = False
            if self.connect_lock.locked():
                self.connect_lock.release()
            self.root.after(0, self.update_ui_state)

            self.receive_task = asyncio.create_task(self.handle_received_data_async())
            await self.receive_task

        except ConnectionRefusedError:
            self.update_status("Connection refused. Server offline?", "red")
            self.display_message(
                f"--- Connection refused on port {self.port}. ---", "error"
            )
        except asyncio.TimeoutError:
            self.update_status("Connection timed out.", "red")
            self.display_message(
                f"--- Timed out after {CONNECT_TIMEOUT} seconds. ---", "error"
            )
        except asyncio.CancelledError:
            self.update_status("Disconnecting (Loop Cancelled)...", "orange")
            raise
        except Exception as e:
            self.update_status(f"Connection error: {e}", "red")
            self.display_message(f"--- Unexpected error: {e} ---", "error")
        finally:
            await self._perform_cleanup_resources()
            if self.connect_lock.locked():
                self.connect_lock.release()

    async def _perform_cleanup_resources(self):
        print("DEBUG: Performing resource cleanup...")
        if self.receive_task and not self.receive_task.done():
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"Error awaiting cancelled receive_task: {e}")
        if self.writer and not self.writer.is_closing():
            self.writer.close()
            try:
                await self.writer.wait_closed()
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
                data = await self.reader.readline()
                if not data:
                    self.display_message(
                        "--- Server closed the connection. ---", "error"
                    )
                    break

                message = data.decode().strip()

                # first handshake prompt
                if first_message and message.startswith("Welcome!"):
                    if self.async_loop and self.async_loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self._send_message_async(self.username), self.async_loop
                        )
                    first_message = False
                    self.display_message("Username sent to server.", "info")
                    continue

                # --- NEW: translate if needed ---
                translated = await self.translate_message_if_needed(message)
                self.display_message(translated)
                first_message = False

        except asyncio.CancelledError:
            print("DEBUG: Receive task cancelled.")
        except ConnectionResetError:
            self.display_message(
                "--- Connection to server lost (reset). ---", "error"
            )
        except Exception as e:
            self.display_message(f"--- Error receiving data: {e} ---", "error")
            print(f"DEBUG: Receiver error: {e}")
        finally:
            print("DEBUG: handle_received_data_async finished.")

    async def _send_message_async(self, message: str):
        if self.writer and not self.writer.is_closing():
            try:
                self.writer.write(message.encode() + b'\n')
                await self.writer.drain()
            except ConnectionResetError:
                self.display_message(
                    "--- Connection lost while sending. ---", "error"
                )
                if self.async_loop and self.async_loop.is_running():
                    self.async_loop.call_soon_threadsafe(self._schedule_stop)
            except Exception as e:
                self.display_message(f"--- Error sending data: {e} ---", "error")
                if self.async_loop and self.async_loop.is_running():
                    self.async_loop.call_soon_threadsafe(self._schedule_stop)

    def _schedule_stop(self):
        if self.async_loop and self.async_loop.is_running():
            if self.connection_task and not self.connection_task.done():
                self.async_loop.call_soon_threadsafe(self.connection_task.cancel)
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
        self.is_connected = False
        self.is_connecting = False
        self.update_status("Disconnecting...", "orange")
        self.root.after(0, self.update_ui_state)
        if self.connect_lock.locked():
            self.connect_lock.release()

    def on_closing(self):
        if self.connect_lock.locked():
            self.connect_lock.release()
        if self.is_connected or self.is_connecting:
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

    async def translate_message_if_needed(self, message: str) -> str:
        """
        Use ChatGPT to detect the incoming message’s language
        and translate it into self.desired_language if different.
        """
        system_prompt = (
            f"You are a translator. If this message is not in "
            f"{self.desired_language}, translate it to {self.desired_language}. "
            "Otherwise, return it unchanged. ONLY return the text."
        )
        try:
            resp = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": message}
                ]
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            # if translation fails, fall back to original text
            self.display_message(f"--- Translation error: {e} ---", "error")
            return message

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Client")
    parser.add_argument('--host', default=DEFAULT_SERVER_HOST,
                        help="Server host address")
    parser.add_argument('--port', type=int, default=DEFAULT_SERVER_PORT,
                        help="Server port number")
    args = parser.parse_args()

    root = ctk.CTk()
    app = ChatClientGUI(root, args.host, args.port)
    app.run()

    print(f"{APP_NAME} terminated.")
