#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino.h>

void setupDisplay();
void writeDisplay(const char* message, int row, bool erase);
void writeDisplayCSV(String message, int commaCount);

#endif