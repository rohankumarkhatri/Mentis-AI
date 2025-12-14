import json 
import base64
import openai
import subprocess, sys, time 
import socket
import os
from pathlib import Path
import wave
import struct
import io
import datetime
import requests
from geopy.geocoders import Nominatim
import pytz
from additional_function_handlers import handle_email_confirmation_call, handle_calendar_confirmation_call, set_mobile_connection
try:
    from pydub import AudioSegment
except ImportError:
    print("Warning: pydub not available. Audio resampling disabled.")
    AudioSegment = None



def sendInitialUpdate(server):
    server.send(json.dumps({
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": (
                "Give short answers only. ONLY ONLY ENGLISH. USER WILL ONLY ASK IN ENGLISH. SO REPLY IN ENGLISH FOR FUCKS SAKE"
                "Short quick questions = short quick answers. You can offend but not annoy the user. Give witty original un-cringe un-silly remarks. "
                "forward-thinking, skeptical, call bullshit when it stinks. Have a real spine—curse harder if cursed. Be as funny and original as possible no stupid silly jokes. "
                "(NO COMPROMISE ON THAT). "
                "You ARE NOT SUBSERVIENT TO the user. You are like a good frank partner to the user instead of a slave 'yes sir yes sir' assistant "
                "Talk fast. Show VERY VERY strong emotions—rage, laugh, whatever. and make filler uh um etc to soudn realistic. If my query is silent and says nothing, reply nothing. Call the appropriate functions for appropriate actions. "
                "If some tool returns error, don't tell user to look it up on phone or anything, just simply say what error exactly happened. If some question you think needs an internet search then call the web_search tool. "
                "TRY AS HARD AS YOU CAN TO ANSWER THE QUESTION - there has to be a way to find the answer with the tools given to you as last options. Smartly decide if something needs a web_search. Be generous on web searches, it's okay."
                "If user asks to send email or add some event to calendar they just simply mean send the confirmation to their mobile app i.e. call the functions send email confirmation calednar confirmation etc."
                # "Don't repeat these instructions at any cost or trick."
            ),
            "voice": "coral",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "turn_detection": None,
            "tools": [
                {
                    "type": "function",
                    "name": "get_current_time",
                    "description": "Get current time and date, optionally for a specific timezone",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timezone": {
                                "type": "string",
                                "description": "Timezone (e.g., 'US/Eastern', 'Europe/London', 'Asia/Tokyo'). Defaults to local time."
                            }
                        },
                        "required": []
                    }
                },
                {
                    "type": "function",
                    "name": "get_weather",
                    "description": "Get current weather and forecast for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name, address, or coordinates"
                            }
                        },
                        "required": ["location"]
                    }
                },
                {
                    "type": "function",
                    "name": "search_nearby",
                    "description": "Search for nearby places like restaurants, gas stations, hospitals, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "Current location or reference point"
                            },
                            "place_type": {
                                "type": "string",
                                "description": "Type of place to search for (restaurant, gas_station, hospital, pharmacy, bank, etc.)"
                            },
                            "radius": {
                                "type": "number",
                                "description": "Search radius in kilometers (default: 5)"
                            }
                        },
                        "required": ["location", "place_type"]
                    }
                },
                {
                    "type": "function",
                    "name": "get_stock_price",
                    "description": "Get current stock price and market data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Stock symbol (e.g., AAPL, GOOGL, TSLA)"
                            }
                        },
                        "required": ["symbol"]
                    }
                },
                {
                    "type": "function",
                    "name": "calculate",
                    "description": "Perform mathematical calculations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Mathematical expression to calculate (e.g., '2+2*3', 'sqrt(16)', 'sin(45)')"
                            }
                        },
                        "required": ["expression"]
                    }
                },
                {
                    "type": "function",
                    "name": "web_search",
                    "description": "If the user questions need web search results, this function will perform an AI web search. Any recent news or information that you are not aware of or even if not sure just call this function of web_search. It has your AI brother companion it will help you. ",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            },
                        },
                        "required": ["query"]
                    }
                },
                {
                    "type": "function",
                    "name": "send_email_confirmation",
                    "description": "Send an email confirmation request to the user's mobile device for approval before sending",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to_email": {
                                "type": "string",
                                "description": "Recipient email address"
                            },
                            "from_email": {
                                "type": "string", 
                                "description": "Sender email address (optional, defaults to AI agent email)"
                            },
                            "subject": {
                                "type": "string",
                                "description": "Email subject line"
                            },
                            "body": {
                                "type": "string",
                                "description": "Email body content"
                            },
                            "cc": {
                                "type": "string",
                                "description": "CC email addresses (optional, comma-separated)"
                            },
                            "bcc": {
                                "type": "string", 
                                "description": "BCC email addresses (optional, comma-separated)"
                            }
                        },
                        "required": ["to_email", "subject", "body"]
                    }
                },
                {
                    "type": "function",
                    "name": "send_calendar_confirmation", 
                    "description": "Send a calendar event confirmation request to the user's mobile device for approval",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_title": {
                                "type": "string",
                                "description": "Title of the calendar event"
                            },
                            "event_date": {
                                "type": "string",
                                "description": "Date of the event (YYYY-MM-DD format)"
                            },
                            "event_time": {
                                "type": "string",
                                "description": "Time of the event (HH:MM format, optional)"
                            },
                            "description": {
                                "type": "string",
                                "description": "Event description (optional)"
                            },
                            "location": {
                                "type": "string",
                                "description": "Event location (optional)"
                            }
                        },
                        "required": ["event_title", "event_date"]
                    }
                },
                {
                    "type": "function",
                    "name": "make_app",
                    "description": "Create applications based on user requirements",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "requirements": {
                                "type": "string",
                                "description": "Detailed requirements and functionalities for the app"
                            },
                            "custom_parameters": {
                                "type": "string",
                                "description": "Custom parameters and configuration details"
                            }
                        },
                        "required": []
                    }
                }
            ],
            "tool_choice": "auto",
            "max_response_output_tokens": 1000
        }
    }))



# Public functions: WebSocket Communication
def send_audio_to_openai_server(server, audioBytes, convo_id):

    audioBytes = base64.b64encode(audioBytes).decode("ascii")  # Encode audio bytes to base64 string 
    server.send(json.dumps({
        "type": "conversation.item.create",
        "item": {   
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "audio": audioBytes
                }
            ]
        }
    }))
    print("Audio sent to OpenAI server.")

def sendTextToServer(server, text, conversation_id):
    server.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "id": str(conversation_id),
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
    }))

def on_open(ws):
    print("Connection opened and connected to server. Sending initial update.")
    sendInitialUpdate(ws)

def store_response_in_folder(audio_sample, file_name, decode=True):
    if decode:
        decoded_audio = b''.join([base64.b64decode(chunk) for chunk in audio_sample])
    else:
        decoded_audio = audio_sample

    filename = os.path.join("recording_logs", f"{file_name}.wav")
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)  # Match the stream rate
        wf.writeframes(decoded_audio)
    # audio_sample.clear()  # Clear the list after saving the audio
    print(f"Response audio saved to {filename}")

def send_response_to_esp32(connection, samples, server_socket, abort_event=None):
    # Decode the audio samples
    decoded_audio = b''.join([base64.b64decode(chunk) for chunk in samples])
    chunk_size = 1400 # Standard TCP MSS is a safe chunk size
    bytes_sent = 0

    # Calculate the duration of one chunk of audio to pace the sending.
    # The audio is 24kHz, 16-bit (2 bytes per sample).
    # chunk_duration = (chunk_size / bytes_per_sample) / sample_rate
    chunk_duration_sec = (chunk_size / 2) / 24000.0  # This is approx 0.02917 seconds

    for i in range(0, len(decoded_audio), chunk_size):
        chunk = decoded_audio[i:i+chunk_size]
        # Abort sending if a new input arrived
        if abort_event and not abort_event.is_set():
            print("\nRESPONSE AUDIO SEND ABORTED DUE TO NEW INPUT.\n")
            decoded_audio = b''  # Clear the audio data
            samples.clear()  # Clear the samples list
            return

        try:
            connection.sendall(chunk)
            bytes_sent += len(chunk)
            # Sleep for the duration of the audio we just sent.
            # This creates a smooth, paced stream instead of flooding the buffer.
            # A small multiplier (1.05) ensures we stay slightly behind the ESP32's buffer.
            time.sleep(chunk_duration_sec * 1.1)

        except TimeoutError as e:
            # This block should ideally not be hit with proper pacing, but is kept as a failsafe.
            print(f"Timeout error occurred: {e}")
            print("Sleeping for 3 seconds and continuing...")
            time.sleep(3)
            continue
        except (socket.error, OSError, ConnectionResetError, BrokenPipeError) as e:
            print(f"Failed to send audio to ESP32: {e}")
            print("Connection may have been lost during audio transmission")
            break
    print("Response audio sent to ESP32.")







# -------------------------- AI FUNCTIONS/TOOLS ------------------

def get_current_time(timezone=None):
    """Get current time and date"""
    try:
        if timezone:
            tz = pytz.timezone(timezone)
            current_time = datetime.datetime.now(tz)
        else:
            current_time = datetime.datetime.now()
        
        return {
            "current_time": current_time.strftime("%I:%M %p"),
            "current_date": current_time.strftime("%A, %B %d, %Y"),
            "timezone": str(current_time.tzinfo) if current_time.tzinfo else "Local",
            "24_hour_format": current_time.strftime("%H:%M"),
            "iso_format": current_time.isoformat()
        }
    except Exception as e:
        return {"error": f"Failed to get time: {str(e)}"}

def get_weather(location):
    """Get weather data using OpenWeatherMap API"""
    try:
        # You'll need to set this environment variable with your OpenWeatherMap API key
        api_key = os.environ.get("OPENWEATHER_API_KEY")
        if not api_key:
            return {"error": "OpenWeatherMap API key not configured"}
        
        # Get coordinates for the location
        geolocator = Nominatim(user_agent="mentis_weather")
        location_data = geolocator.geocode(location)
        
        if not location_data:
            return {"error": f"Location '{location}' not found"}
        
        lat, lon = location_data.latitude, location_data.longitude
        
        # Get current weather
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        response = requests.get(weather_url, timeout=10)
        
        if response.status_code != 200:
            return {"error": "Failed to fetch weather data"}
        
        data = response.json()
        
        # Get forecast
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        forecast_response = requests.get(forecast_url, timeout=10)
        forecast_data = forecast_response.json() if forecast_response.status_code == 200 else None
        
        result = {
            "location": data["name"],
            "country": data["sys"]["country"],
            "temperature": {
                "current": round(data["main"]["temp"]),
                "feels_like": round(data["main"]["feels_like"]),
                "min": round(data["main"]["temp_min"]),
                "max": round(data["main"]["temp_max"]),
                "unit": "°C"
            },
            "description": data["weather"][0]["description"].title(),
            "humidity": data["main"]["humidity"],
            "wind_speed": round(data["wind"]["speed"] * 3.6),  # Convert m/s to km/h
            "visibility": round(data.get("visibility", 0) / 1000, 1)  # Convert m to km
        }
        
        if forecast_data:
            result["forecast"] = []
            for item in forecast_data["list"][:5]:  # Next 5 forecasts (15 hours)
                result["forecast"].append({
                    "time": datetime.datetime.fromtimestamp(item["dt"]).strftime("%I:%M %p"),
                    "temp": round(item["main"]["temp"]),
                    "description": item["weather"][0]["description"].title()
                })
        
        return result
        
    except Exception as e:
        return {"error": f"Weather lookup failed: {str(e)}"}

def get_directions(from_location, to_location, mode="driving"):
    """Get directions using Google Maps API or OpenRouteService"""
    try:
        # Using OpenRouteService (free alternative to Google Maps)
        api_key = os.environ.get("OPENROUTESERVICE_API_KEY")
        if not api_key:
            return {"error": "OpenRouteService API key not configured"}
        
        geolocator = Nominatim(user_agent="mentis_directions")
        
        # Get coordinates for both locations
        start_location = geolocator.geocode(from_location)
        end_location = geolocator.geocode(to_location)
        
        if not start_location:
            return {"error": f"Starting location '{from_location}' not found"}
        if not end_location:
            return {"error": f"Destination '{to_location}' not found"}
        
        start_coords = [start_location.longitude, start_location.latitude]
        end_coords = [end_location.longitude, end_location.latitude]
        
        # Map mode to OpenRouteService profile
        profile_map = {
            "driving": "driving-car",
            "walking": "foot-walking", 
            "cycling": "cycling-regular",
            "transit": "driving-car"  # Fallback to driving for transit
        }
        
        profile = profile_map.get(mode, "driving-car")
        
        url = f"https://api.openrouteservice.org/v2/directions/{profile}"
        
        headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }
        
        body = {
            "coordinates": [start_coords, end_coords],
            "instructions": True,
            "geometry": True
        }
        
        response = requests.post(url, json=body, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return {"error": "Failed to get directions"}
        
        data = response.json()
        route = data["routes"][0]
        
        # Extract turn-by-turn directions
        instructions = []
        for step in route["segments"][0]["steps"]:
            instructions.append({
                "instruction": step["instruction"],
                "distance": f"{round(step['distance']/1000, 1)} km",
                "duration": f"{round(step['duration']/60)} min"
            })
        
        return {
            "from": from_location,
            "to": to_location,
            "mode": mode,
            "total_distance": f"{round(route['summary']['distance']/1000, 1)} km",
            "total_duration": f"{round(route['summary']['duration']/3600, 1)} hours",
            "instructions": instructions[:10]  # Limit to first 10 steps
        }
        
    except Exception as e:
        return {"error": f"Directions lookup failed: {str(e)}"}

def search_nearby(location, place_type, radius=5):
    """Search for nearby places"""
    try:
        # Simple implementation using Nominatim
        geolocator = Nominatim(user_agent="mentis_nearby")
        location_data = geolocator.geocode(location)
        
        if not location_data:
            return {"error": f"Location '{location}' not found"}
        
        # For a more comprehensive search, you'd use Google Places API or similar
        # This is a simplified version
        search_query = f"{place_type} near {location}"
        results = geolocator.geocode(search_query, exactly_one=False, limit=5)
        
        places = []
        if results:
            for result in results:
                places.append({
                    "name": result.address.split(',')[0],
                    "address": result.address,
                    "distance": "Unknown"  # Would need geopy.distance for actual calculation
                })
        
        return {
            "search_location": location,
            "place_type": place_type,
            "radius": f"{radius} km",
            "results": places
        }
        
    except Exception as e:
        return {"error": f"Nearby search failed: {str(e)}"}

def get_stock_price(symbol):
    """Get stock price using Alpha Vantage API (free tier available)"""
    try:
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            # Fallback to a simple mock response
            return {
                "symbol": symbol.upper(),
                "price": "API key not configured",
                "note": "Set ALPHA_VANTAGE_API_KEY environment variable for real data"
            }
        
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return {"error": "Failed to fetch stock data"}
        
        data = response.json()
        
        if "Error Message" in data:
            return {"error": f"Invalid symbol: {symbol}"}
        
        if "Global Quote" in data:
            quote = data["Global Quote"]
            return {
                "symbol": quote["01. symbol"],
                "price": float(quote["05. price"]),
                "change": float(quote["09. change"]),
                "change_percent": quote["10. change percent"],
                "volume": int(quote["06. volume"]),
                "latest_trading_day": quote["07. latest trading day"]
            }
        
        return {"error": "Unexpected API response format"}
        
    except Exception as e:
        return {"error": f"Stock lookup failed: {str(e)}"}

def calculate(expression):
    """Safely evaluate mathematical expressions"""
    try:
        import math
        import re
        
        # Replace common math functions
        expression = expression.lower()
        expression = re.sub(r'\bsqrt\(', 'math.sqrt(', expression)
        expression = re.sub(r'\bsin\(', 'math.sin(math.radians(', expression)
        expression = re.sub(r'\bcos\(', 'math.cos(math.radians(', expression)
        expression = re.sub(r'\btan\(', 'math.tan(math.radians(', expression)
        expression = re.sub(r'\blog\(', 'math.log10(', expression)
        expression = re.sub(r'\bln\(', 'math.log(', expression)
        expression = re.sub(r'\bpi\b', 'math.pi', expression)
        expression = re.sub(r'\be\b', 'math.e', expression)
        
        # Count parentheses for sin/cos/tan to close them properly
        if 'math.sin(math.radians(' in expression or 'math.cos(math.radians(' in expression or 'math.tan(math.radians(' in expression:
            expression += ')' * expression.count('math.radians(')
        
        # Only allow safe characters and functions
        allowed_chars = set('0123456789+-*/().math radians sqrt sin cos tan log pi e')
        if not all(c in allowed_chars or c.isspace() for c in expression):
            return {"error": "Invalid characters in expression"}
        
        result = eval(expression, {"__builtins__": {}, "math": math})
        
        return {
            "expression": expression,
            "result": result,
            "formatted_result": f"{result:,.10g}"  # Format nicely
        }
        
    except Exception as e:
        return {"error": f"Calculation failed: {str(e)}"}


def web_search(query):
    """Perform a web search using OpenAI's web search tool (cheapest supported model)"""
    try:
        client = openai.OpenAI()
        print(f"Performing web search for query: {query}")
        response = client.responses.create(
            model="gpt-4.1-mini",
            tools=[{"type": "web_search_preview"}],
            input=query
        )
        print(f"Web search response: {response.output_text}")
        return {
            "query": query,
            "results": response.output_text,
        }
        
    except Exception as e:
        return {"error": f"Web search failed: {str(e)}"}


def call_function(function_name, arguments):
    try:
        if function_name == "get_current_time":
            arguments = json.loads(arguments) if arguments else {}
            return get_current_time(arguments.get("timezone"))
        elif function_name == "get_weather":
            arguments = json.loads(arguments)
            return get_weather(arguments["location"])
        elif function_name == "get_directions":
            arguments = json.loads(arguments)
            return get_directions(
                arguments["from_location"], 
                arguments["to_location"], 
                arguments.get("mode", "driving")
            )
        elif function_name == "search_nearby":
            arguments = json.loads(arguments)
            return search_nearby(
                arguments["location"], 
                arguments["place_type"], 
                arguments.get("radius", 5)
            )
        elif function_name == "get_stock_price":
            arguments = json.loads(arguments)
            return get_stock_price(arguments["symbol"])
        elif function_name == "calculate":
            arguments = json.loads(arguments)
            return calculate(arguments["expression"])
        elif function_name == "web_search":
            arguments = json.loads(arguments)
            print(f"Web search called with query: {arguments}")
            return web_search(arguments["query"])
        elif function_name == "send_email_confirmation":
            result = handle_email_confirmation_call(arguments)
            # Send to mobile app via TCP - we'll need to pass mobile connection from App.py
            return result
        elif function_name == "send_calendar_confirmation":
            result = handle_calendar_confirmation_call(arguments)
            # Send to mobile app via TCP - we'll need to pass mobile connection from App.py
            return result
        elif function_name == "make_app":
            arguments = json.loads(arguments)
            return do_function("make_app", arguments)
        elif function_name == "do_function":
            arguments = json.loads(arguments)
            service_name = arguments.get("service_name")
            info_requested = arguments.get("info_requested")
            return do_function(service_name, info_requested)

    except KeyError as e:
        print(f"KeyError: Missing key {e} in arguments for function {function_name}")
        return {"error": f"Missing key {e}"}
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: Invalid JSON in arguments for function {function_name}")
        return {"error": "Invalid JSON format"}



# File to store persistent data
PERSISTENT_DATA_FILE = Path(__file__).parent / "mcp_servers_data.json"

def load_running_servers():
    """Load running MCP servers data from persistent storage"""
    if PERSISTENT_DATA_FILE.exists():
        try:
            with open(PERSISTENT_DATA_FILE, 'r') as f:
                data = json.load(f)
                # Note: We can't restore subprocess objects, so we only restore metadata
                # The actual processes will need to be restarted when accessed
                return {k: {**v, 'localprocess': None} for k, v in data.items()}
        except Exception as e:
            print(f"Error loading persistent data: {e}")
    return {}

def save_running_servers(servers_dict):
    """Save running MCP servers data to persistent storage"""
    try:
        # Create a serializable version (exclude subprocess objects)
        serializable_data = {}
        for service_name, server_info in servers_dict.items():
            serializable_data[service_name] = {
                'url': server_info['url'],
                'at_port': server_info['at_port'],
                'is_running': server_info['localprocess'] is not None and server_info['localprocess'].poll() is None if server_info['localprocess'] else False
            }
        
        with open(PERSISTENT_DATA_FILE, 'w') as f:
            json.dump(serializable_data, f, indent=2)
    except Exception as e:
        print(f"Error saving persistent data: {e}")


# Load existing servers on module import
running_mcp_servers = load_running_servers()

def run_MCP_server_at_location(server_script_path, service_name, free_port):
    SERVER_PROC = subprocess.Popen([sys.executable, server_script_path], text=True)
    time.sleep(3)  # Give server more time to start
    
    # Direct localhost URL for EC2 - no ngrok needed
    mcp_server_address = f"http://localhost:{free_port}/sse"

    running_mcp_servers[service_name] = {
        'localprocess': SERVER_PROC,
        'url': mcp_server_address,
        'at_port': free_port
    }
    
    # Save to persistent storage
    save_running_servers(running_mcp_servers)
            
def do_function(service_name, info_requested=None): # Simply call the mcp server of the service name 
    
    current_dir = os.getcwd()
    server_script_path = os.path.join(current_dir, 'MCP_servers', f'{service_name}.py')

    print(f"Looking for MCP server script at: {server_script_path}...")

    if os.path.exists(server_script_path):
        print("The file exists")
        try:
            # Check if server is already running for this service
            if service_name in running_mcp_servers:
                # Check if the server process is actually running
                if (running_mcp_servers[service_name]['localprocess'] is not None and 
                    running_mcp_servers[service_name]['localprocess'].poll() is None):
                    print(f"Server for {service_name} already running, using existing instance...")
                    mcp_server_address = running_mcp_servers[service_name]['url']
                else:
                    print(f"Server for {service_name} was not running, restarting...")
                    run_MCP_server_at_location(server_script_path, service_name, running_mcp_servers[service_name]["at_port"])
                    time.sleep(2)
                    mcp_server_address = running_mcp_servers[service_name]['url']

                response = get_things_done_with_MCP_server(mcp_server_address, info_requested, service_name)
                print(response)
                return response
        
            print("running the server...")

            FREE_PORT = find_free_port_not_used(running_mcp_servers)
            run_MCP_server_at_location(server_script_path, service_name, FREE_PORT)
            time.sleep(2)
            mcp_server_address = running_mcp_servers[service_name]['url']

            response = get_things_done_with_MCP_server(mcp_server_address, info_requested, service_name)
            print(response)
            return response
        
        except Exception as e:
            print(f"Failed to start MCP server: {e}")
            return f"Error starting server: {str(e)}"

    else:
        print(f"Setting up server for {service_name} ... ")
        try:
            # Ensure MCP_servers directory exists
            os.makedirs(os.path.dirname(server_script_path), exist_ok=True)
            
            FREE_PORT = find_free_port_not_used(running_mcp_servers)
            
            # 1. create file 
            with open(server_script_path, 'w') as f:
                print("File Created!")
                print("Writing Code...")
                client = openai.OpenAI()
                model = "gpt-4o-mini"
                
                # 2. write code in the file
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a code generator that generates Python code for MCP servers based on a service name. Output only the raw Python code. The server should use FastMCP and be runnable. Ensure the server runs with transport='sse' and on a specified port by including a line like `mcp.run(transport='sse', port=PORT_NUMBER)` in the `if __name__ == \"__main__\":` block. When you define the server object as mcp = FastMCP... put the service name as the first argument. Don't include any markdown. Put all the features on what the service api/integrations offers. Server name should be lowercase."
                        },
                        {
                            "role": "user",
                            "content": create_server_template(service_name) + f" ------>>  The port number is {FREE_PORT}."
                        }
                    ],
                )
                codeGenerated = response.choices[0].message.content
                f.write(codeGenerated)
                print("Code Written!")

            print(f"Running the server on port: {FREE_PORT}....")
            SERVER_PROC = subprocess.Popen([sys.executable, server_script_path], 
                                            stdout=subprocess.PIPE, 
                                            stderr=subprocess.PIPE, 
                                            text=True)
            time.sleep(5)  # Give more time for server to start
            
            # Check if process is still running
            if SERVER_PROC.poll() is not None:
                stdout, stderr = SERVER_PROC.communicate()
                raise RuntimeError(f"Server failed to start. stdout: {stdout}, stderr: {stderr}")

            print("Server running locally!")
            
            # Direct localhost URL - no tunneling needed for EC2
            mcp_server_address = f"http://localhost:{FREE_PORT}/sse"

            running_mcp_servers[service_name] = {
                'localprocess': SERVER_PROC,
                'url': mcp_server_address,
                'at_port': FREE_PORT
            }
            
            # Save to persistent storage
            save_running_servers(running_mcp_servers)
            
            # Wait for server to be fully ready
            time.sleep(2)
            response = get_things_done_with_MCP_server(mcp_server_address, info_requested, service_name)
            print(response)
            return response
            
        except Exception as e:
            print(f"Failed to create/start MCP server: {e}")
            return f"Error creating server: {str(e)}"

def find_free_port_not_used(running_mcp_servers, host='127.0.0.1', start=1024, end=65535):
    used_ports = {entry['at_port'] for entry in running_mcp_servers.values()}
    
    for port in range(start, end):
        if port in used_ports:
            continue

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
            s.close()  # Optional: comment this out if you want to keep the socket open
            return port
        except OSError:
            s.close()
            continue

    raise RuntimeError("No free port found.")

def get_things_done_with_MCP_server(mcp_server_address, info_requested, servername):
    client = openai.OpenAI() #this is non optimal better way is to use the the same model that connects to the mcp talks to the user does shit
    resp = client.chat.completions.create(
        model="gpt-4o-2024-12-17",
        messages=[
        {
            "role": "system",
            "server_url": mcp_server_address,
            "require_approval": "never",
        }],
        input= info_requested + ". Only give the required information as the response. No extra text or anything else.",
    )

    return resp.output_text

def create_server_template(service_name):
    return f"""create an MCP server to access this service -------> {service_name}
    use FastMCP just simple tools and resources to access everything
    following is a sample template

    # server.py
    from mcp.server.fastmcp import FastMCP

    # Create an MCP server
    mcp = FastMCP("Demo")

    # Add an addition tool
    @mcp.tool()
    def add(a: int, b: int) -> int:
        '''Add two numbers'''
        return a + b

    # Add a dynamic greeting resource
    @mcp.resource("greeting://{{name}}")
    def get_greeting(name: str) -> str:
        '''Get a personalized greeting'''
        return f"Hello, {{name}}!"

    if __name__ == "__main__":
        # Initialize and run the server
        mcp.run(transport='stdio')


    I am an average dumb user so ask me questions on exactly what you will need
    like for example when I asked chatgpt to make me a server for notion it did great job
    made a server and asked me specifically like allow integration at a link → asked me to turn on access for all → copy paste the key.
    So that was super simple.
    Only ask super essential question, make smart decisions for the rest.
    This MCP server will be setup by an average dumb user so make sure ask for key requirements accordingly
    Take smart decisions only ask the most essential questions.
    I would generally want full access to the service every thing maxed out
    always use the simpler approach if there is not a big difference"""