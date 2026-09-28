#include <Arduino.h>
#include "sampling.h"
#include "accelerometer.h"

int sampleRate = 100;
unsigned long sampleDelay = 1000000UL / sampleRate;
unsigned long timeStart = 0;
unsigned long timeEnd = 0;
unsigned long sampleTime = 0;

bool sampleSensors() {
    timeEnd = micros();

    if (timeEnd - timeStart >= sampleDelay) {
        timeStart = timeEnd;
        sampleTime = millis();
        readAccelSensor();
        return true;
    }

    return false;
}