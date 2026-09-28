#include <Arduino.h>

#include "accelerometer.h"
#include "button.h"
#include "communication.h"
#include "display.h"
#include "sampling.h"

const int N = 300;  // buffer size

unsigned long t_buf[N];
int ax_buf[N];
int ay_buf[N];
int az_buf[N];
int idx = 0;

bool sending = false;
bool waitingForResult = false;
bool continuousMode = false;

void clearBuffer() {
    idx = 0;
    writeDisplay("idx=0", 2, true);
}

void logIfReady() {
    if (!sending) return;
    if (idx >= N) return;

    if (sampleSensors()) {
        t_buf[idx]  = sampleTime;
        ax_buf[idx] = ax;
        ay_buf[idx] = ay;
        az_buf[idx] = az;
        idx++;

        if (idx % 50 == 0) {
            writeDisplay(("idx=" + String(idx)).c_str(), 2, false);
        }
    }
}

void dumpBufferToPython() {
    sendMessage("BEGIN," + String(idx));
    delay(10);  // Allow time for message to be sent
    for (int i = 0; i < idx; i++) {
        String line = String(t_buf[i]) + ",";
        line += String(ax_buf[i]) + ",";
        line += String(ay_buf[i]) + ",";
        line += String(az_buf[i]);
        sendMessage(line);
        delay(5);  // Allow time 
    }

    sendMessage("END");
    delay(10);  // Allow time 
}

void setup() {
    setupAccelSensor();
    setupCommunication();
    setupDisplay();
    setupButton();

    sending = false;
    clearBuffer();
    waitingForResult = false;

    writeDisplay("Sleep", 0, true);
    writeDisplay("Wait Study", 1, false);
}

void loop() {
    String command = "";
    command = receiveMessage();

    if (command.length() > 0) {
        command.replace("\r", "");
        command.trim();
        writeDisplay(command.c_str(), 1, false);
        
        if (command == "sleep") {
            sending = false;
            waitingForResult = false;
            continuousMode = false;
            clearBuffer();
            writeDisplay("Sleep", 0, true);
        }

        else if (command == "session_done") {
            sending = false;
            waitingForResult = false;
            continuousMode = false;
            clearBuffer();

            writeDisplay("Session done", 0, true);
        }

        else if (command == "Study") {
            clearBuffer();
            sending = true;
            waitingForResult = false;
            continuousMode = true;

            writeDisplay("Studying", 0, true);
            writeDisplay("Ready", 1, false);
            writeDisplay("idx=0", 2, true);
            writeDisplay("", 3, true);
        }
        //the study band's state (e.g. "distracted", "focused", "phone pick up", "idle", 
        else if (command.startsWith("state,")) {
            waitingForResult = false;

            String state = command.substring(6);
            writeDisplay("Studying", 0, true);
            writeDisplay(state.c_str(), 3, true);

            if (continuousMode) {
                sending = true;
            }
        }
        else if (command.startsWith("score,")) {
            writeDisplay(command.c_str(), 1, false);
        }
        else if (command.startsWith("alert,")) {
            writeDisplay(command.c_str(), 2, false);
        }
        else {
            writeDisplay(command.c_str(), 1, false);
        }
    }
//Python must always send:
//state,<something>

    if (sending && !waitingForResult) {
        logIfReady();
    }
    if (sending && !waitingForResult && continuousMode && idx >= N) {
    writeDisplay("Sending...", 0, true);
    dumpBufferToPython();
    clearBuffer();
    waitingForResult = true;
    writeDisplay("Analyzing...", 0, true);
    
}
    if (!continuousMode && buttonPressed()) {
        if (waitingForResult) {
            writeDisplay("Wait result...", 0, true);
        }
        else if (idx == 0) {
            writeDisplay("No data", 0, true);
        }
        else {
            writeDisplay("Sending...", 0, true);
            dumpBufferToPython();
            clearBuffer();

            waitingForResult = true;
            sending = false;   // stop collecting after one batch

            writeDisplay("Analyzing...", 0, true);
        }
    }
}