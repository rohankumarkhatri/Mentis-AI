// ESP32 WiFi Audio Recorder/Speaker
// Records audio from the microphone sends over the UDP to EC2. Recieves audio over TCP and plays on the transducer

// MIC PIN: 36
// DAC SPEAKER PIN: 26
// We collect audioPackets and write them in the buffer and also read packets from the buffer

// [ F   F   F   F   T   T   T   T   T   F   F  ]    <--- ready to send 
// [ P1  P2 .......                   ...... PN ]    <--- Our buffer made of packets; the ready array tells us to should we read the buffer or write it (and we later decide: do that where to and from)
// [1400 1400 ......                            ]     <--- 77 such packets
//1400 bytes = 2 bytes per sample = 700-samples/1-block
#include <Arduino.h>
#include <WiFiUdp.h>
#include <WiFi.h>
 

// WiFi settings - Already configured with your information
const char* ssid = "Rohan Khatri";
const char* password = "ron123456";

const char* serverAddress = "X"; // EC2 public IP
const short int serverPort = 7777; //open port

const uint8_t buttonPin = 10;
#define NUM_PACKETS 78

// existing constants
const uint16_t sampleRate = 24000;
// const float segmentTime = 0.01587;
const short int samplesPerPacket = 700; //count of PCM values/samples whatever

int16_t* buffer; // flat storage: NUM_PACKETS × samplesPerPacket
volatile bool ready[NUM_PACKETS]; // true = filled, waiting to send
volatile uint8_t writeIdx = 0; // next row to fill
volatile uint8_t sendIdx = 0; // next row to send
volatile bool speakerMode = false;
volatile int8_t speakerStartId = -1;
volatile bool sendToDAC = false;
bool pressed = false;
int16_t dacValue;

WiFiUDP udp;
WiFiClient client;

// TCP connection management
bool tcpConnected = false;
unsigned long lastConnectionAttempt = 0;
const unsigned long connectionRetryInterval = 3000; // 3 seconds



bool connectToTCPServer() {
  if (client.connected()) {
    return true; // Already connected
  }
  
  Serial.println("Attempting to connect to TCP server...");
  client.stop(); // Ensure clean state
  
  if (client.connect(serverAddress, 8888)) {
    Serial.println("Connected to TCP server");
    client.write("hello_from_esp32");
    tcpConnected = true;
    return true;
  } else {
    Serial.println("TCP connection failed");
    tcpConnected = false;
    return false;
  }
}

bool ensureTCPConnection() {
  if (client.connected()) {
    return true;
  }
  
  // Connection lost, mark as disconnected
  if (tcpConnected) {
    Serial.println("TCP connection lost, attempting to reconnect...");
    tcpConnected = false;
  }
  
  // Only retry if enough time has passed
  unsigned long currentTime = millis();
  if (currentTime - lastConnectionAttempt >= connectionRetryInterval) {
    lastConnectionAttempt = currentTime;
    return connectToTCPServer();
  }
  
  return false;
}

void WriteBuffer(void*) {
  while (1) {
    if (!pressed && !speakerMode) {
        speakerMode = true;
        speakerStartId = writeIdx;
    }
    else if (!pressed && speakerMode){
      
      if(!ready[writeIdx]){

        // Ensure TCP connection before trying to read
        if (ensureTCPConnection() && client.available() > 1000) { //HERE HARD CODING 1400 BYTES ---> filling one single packet
          int readBytes = client.read((uint8_t*)&buffer[writeIdx * samplesPerPacket], 1400);
          // if (readBytes > 1000) {
            ready[writeIdx] = true;
            writeIdx = (writeIdx + 1) % NUM_PACKETS;
          // }
        } else if (client.connected() && client.available() != 0) {
          client.read();
        } else {
          vTaskDelay(1);
        }

      } else {
        vTaskDelay(1);
      }

    }
    else if (pressed && speakerMode){ //if button is pressed and we are in speaker mode -> reset everything to prepare start writting for mic
      sendIdx = 0;
      writeIdx = 0;
      speakerStartId = -1;
      memset((void*)ready, 0, sizeof(ready));
      speakerMode = false;
      sendToDAC = false;
    }
    else { // if button is pressed and not in speaker mode then things are reset -> fill empty slots
      if (!ready[writeIdx]) {
        noInterrupts();                      // ← kill all interrupts on this core
        for (int i = 0; i < samplesPerPacket; i++) {
          uint16_t raw = analogRead(35);
          buffer[writeIdx * samplesPerPacket + i] = map(raw, 0, 4095, -32768, 32767);
          delayMicroseconds(1000000UL / sampleRate);
        }
        interrupts();                        // ← re‑enable interrupts

        ready[writeIdx] = true; // mark filled
        writeIdx = (writeIdx + 1) % NUM_PACKETS;
      }
      else {
        vTaskDelay(1);
      }
    }

  }
}


void ReadBuffer(void*) {
  while (1) {

    if (ready[sendIdx]) { // only send slots that are filled
      if(sendToDAC) {
        noInterrupts();                      // ← kill all interrupts on this core
        for (int i = 0; i < samplesPerPacket; i++) {
          dacValue = (uint8_t) map(buffer[(sendIdx * samplesPerPacket) + i], -32768, 32767, 0, 255);
        // dacValue = min( max( (dacValue - 128)*2 + 128, 0 ), 255 );
          dacWrite(26, dacValue); 
          delayMicroseconds(1000000UL / (12000)); // precise playback timing
        }
        interrupts();                        // ← re‑enable interrupts
        if (sendIdx % 50 == 0){ vTaskDelay(1); }
        ready[sendIdx] = false;
        sendIdx = (sendIdx + 1) % NUM_PACKETS;
      }
      else{
        udp.beginPacket(serverAddress, serverPort);
        udp.write((uint8_t*)&buffer[sendIdx * samplesPerPacket], samplesPerPacket * sizeof(int16_t));
        udp.endPacket();
        ready[sendIdx] = false; // mark freed
        sendIdx = (sendIdx + 1) % NUM_PACKETS;
        if(sendIdx == speakerStartId){
          sendToDAC = true;
        }
      }
    } else {
      vTaskDelay(1);
    }


  }
}

void setup() {
  Serial.begin(115200);


  Serial.printf("Free heap: %u, Max alloc: %u\n", ESP.getFreeHeap(), ESP.getMaxAllocHeap());
  // Connect to WiFi
  Serial.println("Connecting to WiFi...");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.println("IP address: " + WiFi.localIP().toString());

  // allocate circular buffer
  buffer = (int16_t*) malloc(NUM_PACKETS * samplesPerPacket * sizeof(int16_t));
  if (!buffer) {
    Serial.println("Buffer alloc failed!");
    while (1);
  }
  memset((void*)ready, 0, sizeof(ready));

  // start UDP
  udp.begin(12345);

  // spawn tasks pinned to cores
  xTaskCreatePinnedToCore(WriteBuffer, "Fill", 4096 , NULL, 1, NULL, 1);
  xTaskCreatePinnedToCore(ReadBuffer, "Send", 4096 , NULL, 1, NULL, 0);

  pinMode(buttonPin, INPUT_PULLUP);

  // Initial TCP connection attempt
  connectToTCPServer();

  Serial.printf("Free heap: %u, Max alloc: %u\n", ESP.getFreeHeap(), ESP.getMaxAllocHeap());

}

void loop() {
  // Periodically check and maintain TCP connection
  static unsigned long lastConnectionCheck = 0;
  unsigned long currentTime = millis();
  
  if (currentTime - lastConnectionCheck >= 5000) { // Check every 5 seconds
    ensureTCPConnection();
    lastConnectionCheck = currentTime;
  }

  if(digitalRead(buttonPin) == LOW){
    delay(50);
    while (digitalRead(buttonPin) == LOW) { pressed = true; }
    pressed = false;
  }

}