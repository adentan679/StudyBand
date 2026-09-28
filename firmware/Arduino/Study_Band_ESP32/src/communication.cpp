#include <Arduino.h>
#include "communication.h"

/*
 * Precompiler directive elegance: 0 == Serial, 1 == Bluetooth
 */
#define USE_BT 1

#if USE_BT
    #include "BluetoothSerial.h"
    BluetoothSerial BTSerial;
    #define Ser BTSerial
#else
    #define Ser Serial
#endif

void setupCommunication() {
#if USE_BT
    Ser.begin("Deadline");
#else
    Ser.begin(115200);
#endif
}

String receiveMessage() {
    String message = "";

    if (Ser.available() > 0) {
        while (true) {
            char c = Ser.read();
            if (c != char(-1)) {
                if (c == '\n') {
                    break;
                }
                message += c;
            }
        }
    }

    return message;
}

void sendMessage(String message) {
    Ser.println(message);
}