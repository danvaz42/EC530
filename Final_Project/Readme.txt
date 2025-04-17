Mission Statement:

This application is being designed to operate as a language-decentralized chatting program. It enables users to send and receive messages that will be automatically translated into any supported language of preference. This program is meant to break down language barriers, and give every user the ability to chat with anyone from anywhere.
_____________________________________________________________________________________________________________
Latest Version: (chat_client_v3, relay_server_v2) 4/17/25

Requirements:
- python3
- customtkinter (Python Package)

Changes:
- Added Client-Side GUI.
- Added new relay_server_debug.py file to help pinpoint errors
- Much more debugging in chat_client_v3.py
- New Requirement (for the GUI) > python package > customtkinter
	- install in terminal using "pip install customtkinter"

Fixes:
-Fixed an issue where the client could connect to server, but was unable to send messages

Note:
- Server information is currently obscured while in development.
____________________________________________________________________________________________________________
Current Functionality:

Allows chat between multiple clients/server in shell terminal.
_____________________________________________________________________________________________________________
Setup/Running

1) Install latest python version (https://www.python.org/downloads/)
2) Enter "pip install customtkinter" (no quotes) in a terminal
3) Download the latest version of chat_client.py
4) Navigate to the folder with the downloaded file > right click anywhere in the folder > select "open terminal here"
5) In the terminal session, run the command > python chat_client_(your version).py 
_____________________________________________________________________________________________________________

Future Updates:

- packaging/containerized for easy setup/distribution
- testing (unit, linting, etc) ==> (Unit testing added in v1)
- Mac support
- GUI (Added in v3 - subject to change)
- LLM calls (for translation)
- support multiple connections ==> (Added in v2)
_____________________________________________________________________________________________________________
Changelog:

(v2) 4/16/25
- Allows chat between multiple clients/server in shell terminal.

Changes:
- Updated from P2P to client/server, hosted by DigitalOcean.
- Multiple users can now connect to the provided server.

(v1) 4/15/2025 
- Allows chat between client/server in shell terminal. Only functional on same machine (uses localhost).
