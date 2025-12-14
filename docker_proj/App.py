import socket
import os
import websocket
import helper as utils
import threading
import json
import base64
import time
import wave
import pyaudio
import keyboard
import base64
import numpy as np

run_local = False

responseSamples = [] 
frames = []
response_in_process = threading.Event()
response_in_process.set() 
convo_id = 1000

recieve_udp_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recieve_udp_audio.bind(('0.0.0.0', 7777))  # Bind to all interfaces on port 7777 (not safe for public use)
recieve_udp_audio.settimeout(0.7) 
addr = None

TCP_IP = '0.0.0.0'
TCP_PORT = 8888
MOBILE_TCP_PORT = 9999  # Separate port for mobile app connections
conn = None
mobile_conn = None
server_socket = None
mobile_server_socket = None
shutdown_flag = threading.Event()

def setup_mobile_tcp_connection():
    global mobile_conn, mobile_server_socket
    while not shutdown_flag.is_set():
        try:
            if mobile_server_socket:
                mobile_server_socket.close()
            mobile_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mobile_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            mobile_server_socket.bind((TCP_IP, MOBILE_TCP_PORT))
            mobile_server_socket.listen(1)
            mobile_server_socket.settimeout(5)  # Shorter timeout to allow interruption
            
            print(f"Waiting for Mobile App connection on port {MOBILE_TCP_PORT}...")
            try:
                mobile_conn, mobile_addr = mobile_server_socket.accept()
                print(f"Mobile App connected from {mobile_addr}")
                mobile_conn.settimeout(5)
                # Set the mobile connection in the helper module
                utils.set_mobile_connection(mobile_conn)
                return mobile_conn
            except socket.timeout:
                if shutdown_flag.is_set():
                    break
                continue
        except Exception as e:
            if shutdown_flag.is_set():
                break
            print(f"Failed to establish Mobile TCP connection: {e}")
            print("Retrying in 3 seconds...")
            for _ in range(30):  # 3 seconds in 0.1 second intervals
                if shutdown_flag.is_set():
                    return None
                time.sleep(0.1)
    return None

def monitor_mobile_tcp_connection():
    """Monitor Mobile TCP connection in background and continuously listen for new connections"""
    global mobile_conn, mobile_server_socket
    
    # Start by setting up the server socket to continuously listen
    try:
        if mobile_server_socket:
            mobile_server_socket.close()
        mobile_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mobile_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mobile_server_socket.bind((TCP_IP, MOBILE_TCP_PORT))
        mobile_server_socket.listen(1)
        mobile_server_socket.settimeout(1.0)  # Short timeout to allow checking shutdown_flag
        print(f"Mobile TCP server listening continuously on port {MOBILE_TCP_PORT}")
    except Exception as e:
        print(f"Failed to setup mobile TCP server: {e}")
        return
    
    while not shutdown_flag.is_set():
        try:
            # Always listen for new connections
            try:
                new_conn, mobile_addr = mobile_server_socket.accept()
                print(f"New Mobile App connection from {mobile_addr}")
                
                # If we already have a connection, close the old one
                if mobile_conn:
                    try:
                        print("Closing previous mobile connection for new one")
                        mobile_conn.close()
                    except:
                        pass
                
                # Set up the new connection
                mobile_conn = new_conn
                mobile_conn.settimeout(5)
                utils.set_mobile_connection(mobile_conn)
                print("Mobile app connected successfully")
                
            except socket.timeout:
                # Timeout is expected when no new connections, continue monitoring existing connection
                pass
            except Exception as e:
                if not shutdown_flag.is_set():
                    print(f"Error accepting mobile connection: {e}")
                continue
            
            # Check if existing connection is still alive
            if mobile_conn:
                try:
                    # Try to peek at the socket to see if it's still connected
                    mobile_conn.settimeout(0.1)
                    data = mobile_conn.recv(1, socket.MSG_PEEK)
                    if len(data) == 0:
                        # Connection closed by peer
                        print("Mobile App connection closed by peer")
                        raise ConnectionResetError()
                except socket.timeout:
                    # Timeout is expected, connection is still alive
                    pass
                except (ConnectionResetError, socket.error, OSError, BrokenPipeError) as e:
                    print(f"Mobile App disconnected: {e}")
                    try:
                        mobile_conn.close()
                    except:
                        pass
                    mobile_conn = None
                    utils.set_mobile_connection(None)
            
        except Exception as e:
            if not shutdown_flag.is_set():
                print(f"Unexpected error in mobile connection monitor: {e}")
        
        time.sleep(0.5)  # Short sleep to prevent excessive CPU usage


def setup_tcp_connection():
    global conn, server_socket
    while True:
        try:
            if server_socket:
                server_socket.close()
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((TCP_IP, TCP_PORT))
            server_socket.listen(1)
            server_socket.settimeout(20)
            
            print("Waiting for ESP32 connection...")
            conn, addrtcp = server_socket.accept()
            print(f"ESP32 connected from {addrtcp}")
            conn.settimeout(5)  # Set timeout for connection operations
            return conn
        except Exception as e:
            print(f"Failed to establish TCP connection: {e}")
            print("Retrying in 3 seconds...")
            time.sleep(3)

def ensure_tcp_connection():
    global conn
    # Return current connection if exists, else None
    if conn is None:
        return None

    # Test if connection is still alive by sending a small test
    try:
        conn.settimeout(0.1)
        conn.send(b'')  # test connection
        conn.settimeout(5)
        return conn
    except:
        print("TCP connection lost")
        try:
            conn.close()
        except:
            pass
        conn = None
        return None

def monitor_tcp_connection():
    """Monitor ESP32 TCP connection in background and continuously listen for new connections"""
    global conn, server_socket

    # Setup the server socket for continuous listening
    try:
        if server_socket:
            server_socket.close()
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((TCP_IP, TCP_PORT))
        server_socket.listen(1)
        server_socket.settimeout(1.0)  # Short timeout for checking shutdown_flag
        print(f"ESP32 TCP server listening continuously on port {TCP_PORT}")
    except Exception as e:
        print(f"Failed to setup ESP32 TCP server: {e}")
        return

    while not shutdown_flag.is_set():
        try:
            # Accept new connections
            try:
                new_conn, esp_addr = server_socket.accept()
                print(f"New ESP32 connection from {esp_addr}")

                # Close previous connection if present
                if conn:
                    try:
                        print("Closing previous ESP32 connection for new one")
                        conn.close()
                    except:
                        pass

                conn = new_conn
                conn.settimeout(5)
                print("ESP32 connected successfully")
            except socket.timeout:
                # No new connection, continue monitoring
                pass
            except Exception as e:
                if not shutdown_flag.is_set():
                    print(f"Error accepting ESP32 connection: {e}")
                continue

            # Check if existing connection is still alive
            if conn:
                try:
                    conn.settimeout(0.1)
                    data = conn.recv(1, socket.MSG_PEEK)
                    if len(data) == 0:
                        print("ESP32 connection closed by peer")
                        raise ConnectionResetError()
                except socket.timeout:
                    pass
                except (ConnectionResetError, socket.error, BrokenPipeError) as e:
                    print(f"ESP32 disconnected: {e}")
                    try:
                        conn.close()
                    except:
                        pass
                    conn = None
        except Exception as e:
            if not shutdown_flag.is_set():
                print(f"Unexpected error in ESP32 connection monitor: {e}")
        time.sleep(0.5)

# Initial connection setup
if not run_local:
    # Start ESP32 TCP connection monitoring thread (handles continuous accept and reconnect)
    tcp_monitor_thread = threading.Thread(target=monitor_tcp_connection)
    tcp_monitor_thread.daemon = True
    tcp_monitor_thread.start()

    # Start Mobile App connection monitoring (handles continuous accept and reconnect)
    mobile_monitor_thread = threading.Thread(target=monitor_mobile_tcp_connection)
    mobile_monitor_thread.daemon = True
    mobile_monitor_thread.start()


def response_from_server(_,response):
    response = json.loads(response)

    if(response.get("type") == "response.audio.delta" ):
        responseSamples.append(response.get("delta")) 
        
    else:
 
        if(response.get("type") == 'error'):
            print("OPEN AI Error: " + str(response))
        elif(response.get("type") == "conversation.item.created" and (response.get("item").get("role") == "user" or response.get("item").get("type") == "function_call_output") ): #if conversation item created by user or some function call output is recieved to the model, trigger inference by response.create
            _.send(json.dumps({
                "type": "response.create",
            }))
        elif(response.get("type") == "session.updated"):
            print("OPEN AI Session updated")

        elif(response.get("type") == "response.done"):

            for item in response.get("response").get("output"):
                if item.get("type") != "function_call":
                    continue
                function_answer = json.dumps(utils.call_function(item.get("name"), item.get("arguments")))
                _.send(json.dumps({ 
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": item.get("call_id"),
                        "output": function_answer,
                    }
                    }))


            # Ensure we have a valid TCP connection before sending
            if not run_local:
                active_conn = ensure_tcp_connection()
                if active_conn:
                    print("\nResponse done received from OpenAI server. Response samples length:", len(responseSamples), "sending to ESP32...\n")
                    # Abort ongoing response send if new audio arrives by passing response_in_process as abort event
                    utils.send_response_to_esp32(active_conn, responseSamples, server_socket, abort_event=response_in_process)    
                    utils.store_response_in_folder(responseSamples, 'response_audio', decode=True)
            elif run_local:
                # Play audio locally in terminal instead of sending to ESP32
                # Play audio locally
                if responseSamples:
                    try:
                        print("Playing audio locally...")
                        # Decode base64 audio samples
                        audio_data = b''
                        for sample in responseSamples:
                            audio_data += base64.b64decode(sample)
                        
                        # Convert bytes to numpy array (assuming 16-bit PCM)
                        audio_array = np.frombuffer(audio_data, dtype=np.int16)
                        
                        # Initialize PyAudio
                        p = pyaudio.PyAudio()
                        
                        # Open stream for playback
                        stream = p.open(format=pyaudio.paInt16,
                                      channels=1,
                                      rate=24000,  # OpenAI Realtime API uses 24kHz
                                      output=True)
                        
                        # Play audio
                        stream.write(audio_array.tobytes())
                        
                        # Cleanup
                        stream.stop_stream()
                        stream.close()
                        p.terminate()
                        
                    except Exception as e:
                        print(f"Error playing audio locally: {e}")
            else:
                print("Failed to establish TCP connection for response")  



OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if OPENAI_API_KEY is None:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview"
headers = [
	"Authorization: Bearer " + OPENAI_API_KEY,
	"OpenAI-Beta: realtime=v1"
]
ws = websocket.WebSocketApp(
    url,
    on_message= response_from_server,
    on_open= utils.on_open,
    header=headers
)

ws_thread = threading.Thread(target=ws.run_forever)
ws_thread.daemon = True
ws_thread.start()

def reconnect_websocket():
    global ws, ws_thread
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"Attempting to reconnect WebSocket (attempt {attempt + 1}/{max_retries})...")
            
            # Close existing connection if any
            if ws:
                try:
                    ws.close()
                except:
                    pass
            
            # Wait for thread to finish
            if ws_thread and ws_thread.is_alive():
                ws_thread.join(timeout=2)
            
            # Create new WebSocket connection
            ws = websocket.WebSocketApp(
                url,
                on_message=response_from_server,
                on_open=utils.on_open,
                header=headers
            )
            
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Give it a moment to connect
            time.sleep(1)
            
            # Check if connection is successful
            if ws.sock and ws.sock.connected:
                print("WebSocket reconnected successfully!")
                return True
            else:
                print(f"Reconnection attempt {attempt + 1} failed")
                
        except Exception as e:
            print(f"Reconnection attempt {attempt + 1} failed with error: {e}")
        
        if attempt < max_retries - 1:
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 10)  # Exponential backoff, max 10 seconds
    
    print("Failed to reconnect WebSocket after all attempts")
    return False

def cleanup_connections():
    global conn, server_socket, mobile_conn, mobile_server_socket, ws, ws_thread
    print("Setting shutdown flag...")
    shutdown_flag.set()
    
    # Close WebSocket connection
    if ws:
        try:
            ws.close()
        except:
            pass
    
    # Wait for WebSocket thread to finish
    if ws_thread and ws_thread.is_alive():
        ws_thread.join(timeout=2)
    
    if conn:
        try:
            conn.close()
        except:
            pass
        conn = None
    if server_socket:
        try:
            server_socket.close()
        except:
            pass
        server_socket = None
    
    if mobile_conn:
        try:
            mobile_conn.close()
        except:
            pass
        mobile_conn = None
    if mobile_server_socket:
        try:
            mobile_server_socket.close()
        except:
            pass
        mobile_server_socket = None
    print("Connections cleaned up.")

import atexit
atexit.register(cleanup_connections)




if run_local:
    
    # Audio recording parameters
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    audio = pyaudio.PyAudio()
    
    print("Local mode: Press and hold SPACE to record audio, release to send")
    
    try:
        while True:
            if keyboard.is_pressed('space'):
                print("Recording... (release SPACE to stop)")
                frames = []
                
                stream = audio.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  input=True,
                                  frames_per_buffer=CHUNK)
                
                # Record while space is held
                while keyboard.is_pressed('space'):
                    data = stream.read(CHUNK)
                    frames.append(data)
                
                stream.stop_stream()
                stream.close()
                
                if frames:
                    response_in_process.clear()
                    responseSamples.clear()
                    
                    audio_data = b''.join(frames)
                    convo_id += 1
                    
                    # Check if WebSocket is connected, if not try to reconnect
                    if ws.sock and ws.sock.connected:
                        try:
                            utils.send_audio_to_openai_server(ws, audio_data, convo_id)
                        except Exception as e:
                            if "Connection is already closed" in str(e) or "WebSocketConnectionClosedException" in str(e):
                                print("WebSocket connection lost during send. Attempting to reconnect...")
                                if reconnect_websocket():
                                    print("Reconnection successful. Sending audio...")
                                    utils.send_audio_to_openai_server(ws, audio_data, convo_id)
                                else:
                                    print("Failed to reconnect. Audio will be lost.")
                            else:
                                print(f"Error sending audio: {e}")
                    else:
                        print("WebSocket connection is closed. Attempting to reconnect...")
                        if reconnect_websocket():
                            print("Reconnection successful. Sending audio...")
                            utils.send_audio_to_openai_server(ws, audio_data, convo_id)
                        else:
                            print("Failed to reconnect. Audio will be lost.")
                    
                    response_in_process.set()
                    
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        audio.terminate()
        
else:
    # Original UDP audio receiving code
    try: 
        while True:
            try:
                data, addr = recieve_udp_audio.recvfrom(1400) # 1400 bytes (2 bytes 700 samples) = 1 block. Total buffer size is 64 blocks.  

                if len(data) > 20:
                    response_in_process.clear()
                    responseSamples.clear()
                    frames.append(data)
            except socket.timeout:
                if frames:
                    print("Sending audio to server...")
                    response_in_process.set()
                    audio_data = b''.join(frames)  # No need for copy() here
                    convo_id += 1
                    
                    # Check if WebSocket is connected, if not try to reconnect
                    if ws.sock and ws.sock.connected:
                        try:
                            utils.send_audio_to_openai_server(ws, audio_data, convo_id)
                            # Reuse the already-joined audio_data instead of recreating it
                            utils.store_response_in_folder(audio_data, f"user_audio", decode=False)
                            frames.clear()  # More explicit than frames = []
                        except Exception as e:
                            if "Connection is already closed" in str(e) or "WebSocketConnectionClosedException" in str(e):
                                print("WebSocket connection lost during send. Attempting to reconnect...")
                                if reconnect_websocket():
                                    print("Reconnection successful. Sending audio...")
                                    utils.send_audio_to_openai_server(ws, audio_data, convo_id)
                                    utils.store_response_in_folder(audio_data, f"user_audio", decode=False)
                                    frames.clear()
                                else:
                                    print("Failed to reconnect. Audio will be lost.")
                                    frames.clear()
                            else:
                                print(f"Error sending audio: {e}")
                                frames.clear()
                    else: 
                        print("WebSocket connection is closed. Attempting to reconnect...")
                        if reconnect_websocket():
                            print("Reconnection successful. Sending audio...")
                            utils.send_audio_to_openai_server(ws, audio_data, convo_id)
                            utils.store_response_in_folder(audio_data, f"user_audio", decode=False)
                            frames.clear()
                        else:
                            print("Failed to reconnect. Audio will be lost.")
                            frames.clear()  # Clear frames to avoid infinite retry

                else:
                    print("No audio frames to send.")
                    continue  # Continue to next iteration if no frames
            except KeyboardInterrupt:
                print("\nShutting down gracefully...")
                break
            except Exception as e:
                print(f"Unexpected error in main loop: {e}")
                time.sleep(1)  # Brief pause before continuing
    finally:
        print("Cleaning up connections...")
        cleanup_connections()
        recieve_udp_audio.close()
