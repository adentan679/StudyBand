# Communication.py
# Put in: Python/Lab_7/Communication.py

import serial
from time import sleep


class Communication:
    __serial_name = ""
    __baud_rate = 115200
    __ser = None

    def __init__(self, serial_name=None, baud_rate=None):
        self.__serial_name = serial_name
        self.__baud_rate = baud_rate
        if serial_name is not None and baud_rate is not None:
            self.setup()

    def setup(self):
        # Open serial with a small timeout to avoid rare blocking
        self.__ser = serial.Serial(self.__serial_name, self.__baud_rate, timeout=0.1)

    def close(self):
        sleep(0.5)
        if self.__ser is not None and self.__ser.is_open:
            self.__ser.close()

    def send_message(self, message: str):
        if self.__ser is None:
            return
        if not message.endswith("\n"):
            message += "\n"
        self.__ser.write(message.encode("utf-8"))

    def receive_message(self, num_bytes=80):
        if self.__ser is None:
            return None
        if self.__ser.in_waiting > 0:
            # Strip CR/LF to avoid subtle string-compare bugs
            return self.__ser.readline(num_bytes).decode("utf-8", errors="ignore").strip()
        return None

    def clear(self):
        if self.__ser is not None:
            self.__ser.reset_input_buffer()