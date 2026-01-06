**Mentis AI**

A compact project that bridges an ESP32 audio client with OpenAI Realtime APIs. It provides firmware for the ESP32 (audio capture/playback), a Python server to receive UDP/TCP audio from devices and forward it to OpenAI, and small helper/MCP server utilities for tool integrations.

**Repository Layout**
- **arduino/**: ESP32 firmware (audio capture, UDP/TCP client).
- **docker_proj/**: Python server and helper modules that connect to OpenAI Realtime and handle TCP/UDP interactions.
- **MCP_servers/**: helper microservices that can be launched on demand by the main server.
 - **MCP_servers/**: placeholder microservices. MCP server functionality is experimental and NOT fully implemented — these are optional helpers that may be launched on demand if/when the code paths call them.
- **recordings_folder/**: audio samples and logs (runtime output).

**Quick Overview**
- `docker_proj/App.py`: main Python server — receives UDP audio, sends to OpenAI Realtime via WebSocket, routes responses to ESP32 or local playback.
- `docker_proj/helper.py`: utilities and AI function/tool handlers (also contains some example API calls).
- `arduino/working_AudioUDP/working_AudioUDP.ino`: ESP32 firmware that records audio and sends/receives audio packets.

This project is a proof-of-concept: it is not production-ready and may contain security vulnerabilities. Requirements and deployment notes:

- Hardware & firmware: an ESP32 device flashed with the sketch in `arduino/working_AudioUDP/working_AudioUDP.ino`. Configure the firmware with the server address the device should contact i.e. public IP of your EC2 instance.
- Server: a running host (for example an EC2 instance) that runs `docker_proj/App.py` and is reachable by the device.
- Optional: a mobile app for confirmations and approvals.

Deployment reminders:
- Do not commit API keys or credentials. Supply secrets at runtime (environment variables).
- Only set the device firmware to use a public server IP if you intend to expose the service publicly; otherwise prefer private networking and firewall rules.

For quick test set the public IP of your EC2 instance in the .ino file and load the api keys in the docker file python server.
