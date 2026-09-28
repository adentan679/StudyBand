"""
log_data.py

Purpose:
Collect raw accelerometer batches from the ESP32 and save them as CSV files.
These datasets will later be used to design DSP algorithms such as
phone pickup detection.

Data flow:
ESP32 -> Python -> CSV

ESP32 protocol:
BEGIN,n
t,ax,ay,az
t,ax,ay,az
...
END


After receiving a batch, Python must send a response so the ESP32
exits its waiting state.
"""

from ECE16Lib.Communication import Communication
import numpy as np
import csv
import time
from pathlib import Path


# Serial configuration (must match ESP32)
PORT = "COM13"
BAUD = 115200


# Change this label before collecting each type of behavior
CURRENT_LABEL = "random_arm_move"  # e.g. phone_pickup, still, typing, writing, random_arm_move

# Good labels to collect later:
# phone_pickup
# still
# typing
# writing
# random_arm_move


# Directory where datasets will be saved
LOG_DIR = Path("logged_data")
LOG_DIR.mkdir(exist_ok=True)

def save_batch_csv(t, ax, ay, az, label):
    """
    Save one batch of accelerometer data to a CSV file.
    """

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = LOG_DIR / f"{timestamp}_{label}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)

        # CSV header
        writer.writerow(["t", "ax", "ay", "az"])

        # Write sensor samples
        for i in range(len(t)):
            writer.writerow([t[i], ax[i], ay[i], az[i]])

    print(f"\nSaved dataset -> {filename}")
    print(f"Samples saved: {len(t)}\n")


def wait_begin(comms):
    """
    Wait until the ESP32 signals the start of a data batch.
    ESP32 sends: BEGIN,n
    """

    while True:
        msg = comms.receive_message()

        if msg is None:
            continue

        msg = msg.replace("\r", "").strip()

        if msg.startswith("BEGIN,"):
            try:
                n = int(msg.split(",")[1])
                return n
            except:
                pass


def read_batch(comms, n):
    """
    Read n samples from the ESP32.
    Each line is formatted as:
    t,ax,ay,az
    """

    t, ax, ay, az = [], [], [], []
    count = 0

    while count < n:

        msg = comms.receive_message()

        if msg is None:
            continue

        msg = msg.replace("\r", "").strip()

        if not msg:
            continue

        # If END appears early
        if msg == "END":
            break

        parts = msg.split(",")

        if len(parts) != 4:
            continue

        try:
            tt = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])
            z = int(parts[3])
        except:
            continue

        t.append(tt)
        ax.append(x)
        ay.append(y)
        az.append(z)

        count += 1

    # Make sure the END marker is consumed before the next batch
    while True:
        msg = comms.receive_message()

        if msg is None:
            continue

        msg = msg.replace("\r", "").strip()

        if msg == "END":
            break

    return np.array(t), np.array(ax), np.array(ay), np.array(az)


if __name__ == "__main__":

    print("\nStarting ESP32 data logger")
    print(f"Current label: {CURRENT_LABEL}\n")

    # Connect to ESP32
    comms = Communication(PORT, BAUD)
    comms.clear()

    '''comms.send_message("Study")
    print("ESP32 armed in continuous collection mode.")
    print("Waiting for batches... Press Ctrl+C to stop.\n")
    '''
    try:
        while True:
            user_cmd = input(
                f"\nPress Enter to collect one '{CURRENT_LABEL}' clip, or type q to quit: "
            ).strip().lower()

            if user_cmd == "q":
                break

            comms.send_message("Study")
            time.sleep(0.2)   # give ESP32 time to receive command
            print("ESP32 armed. Perform the motion, then press the ESP32 button to send the batch.")
            print("Waiting for ESP32 batch...")

            n = wait_begin(comms)
            print(f"Receiving batch with {n} samples")

            t, ax, ay, az = read_batch(comms, n)
            save_batch_csv(t, ax, ay, az, label=CURRENT_LABEL)

            comms.send_message("stat" \
            "e,logging")
            comms.send_message("score,0")
            comms.send_message("alert,0")

            print("Batch complete. ESP32 is waiting for the next Study command.")

    except KeyboardInterrupt:
        print("\nStopping logger...")

    finally:
        comms.send_message("sleep")
        comms.close()