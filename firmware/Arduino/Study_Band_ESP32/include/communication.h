#ifndef COMMUNICATION_H
#define COMMUNICATION_H

#include <Arduino.h>

void setupCommunication();
String receiveMessage();
void sendMessage(String message);

#endif