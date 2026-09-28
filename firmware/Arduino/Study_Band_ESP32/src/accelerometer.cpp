#include <Arduino.h>
#include "accelerometer.h"

const int X_PIN = A2;
const int Y_PIN = A3;
const int Z_PIN = A4;

int ax = 0;
int ay = 0;
int az = 0;

void setupAccelSensor() {
    pinMode(X_PIN, INPUT);
    pinMode(Y_PIN, INPUT);
    pinMode(Z_PIN, INPUT);
}

void readAccelSensor() {
    ax = analogRead(X_PIN);
    ay = analogRead(Y_PIN);
    az = analogRead(Z_PIN);
}