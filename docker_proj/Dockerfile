# Use standard Python image (not slim)
FROM python:3.10

# Set working dir inside the container
WORKDIR /app

# Copy all files from host to container
COPY . .

# Install Python dependencies
RUN apt-get update && apt-get install -y portaudio19-dev ffmpeg
RUN pip install --no-cache-dir -r requirements.txt

ENV OPENAI_API_KEY= //api key here
ENV OPENWEATHER_API_KEY= //api key here
ENV ALPHA_VANTAGE_API_KEY= //api key here
ENV OPENROUTESERVICE_API_KEY= //api key
ENV PYTHONUNBUFFERED=1

# Command to run your app
CMD ["python", "App.py"]

# DOCKER RUN COMMAND
# docker run \
#  --network host \
#  --name cont1 \
#  -v ~/ALL_HERE/docker_proj/recording_logs:/app/recording_logs \
#  -v ~/ALL_HERE/docker_proj/MCP_servers:/app/MCP_servers \
#  mentis_server_image1
