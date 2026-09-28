#include <Arduino.h>
#include "button.h"

const int BUTTON_PIN = 16;

void setupButton() {
    pinMode(BUTTON_PIN, INPUT_PULLUP);
}

bool buttonPressed() {
    static bool last = HIGH;
    static unsigned long lastChange = 0;

    bool cur = digitalRead(BUTTON_PIN);
    unsigned long now = millis();

    if (cur != last) {
        lastChange = now;
        last = cur;
    }

    if (cur == LOW && (now - lastChange) > 30) {
        while (digitalRead(BUTTON_PIN) == LOW) {
            delay(1);
        }
        return true;
    }

    return false;
}