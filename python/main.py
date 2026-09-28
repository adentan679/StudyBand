from ECE16Lib.Communication import Communication
import ECE16Lib.DSP as filt
import numpy as np
import time
import json
import paho.mqtt.client as mqtt


# Debug settings
DEBUG_PRINT = True


# MQTT settings
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

STUDENT_ID = "Mchen"        # change if needed
DEVICE_ID = "studyband1"    # change if needed

STATUS_TOPIC = f"focus_tracker/{STUDENT_ID}/{DEVICE_ID}/status"
EVENT_TOPIC = f"focus_tracker/{STUDENT_ID}/{DEVICE_ID}/event"


# Utility helpers
def clamp_score(score: float) -> float:
    return max(0, min(100, score))


# MQTT helpers
mqtt_client = mqtt.Client(client_id=f"{STUDENT_ID}_{DEVICE_ID}_python", protocol=mqtt.MQTTv311)


def connect_mqtt():
    print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT} ...")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()


def disconnect_mqtt():
    try:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    except Exception:
        pass


def publish_final_status(score: int, pickups: int, elapsed_sec: int):
    payload = {
        "student_id": STUDENT_ID,
        "device": DEVICE_ID,
        "score": int(score),
        "pickups": int(pickups),
        "elapsed_sec": int(elapsed_sec),
    }
    mqtt_client.publish(STATUS_TOPIC, json.dumps(payload), qos=0, retain=True)
    print(f"[MQTT] final status -> {payload}")


def publish_final_event(score: int, pickups: int, elapsed_sec: int):
    payload = {
        "student_id": STUDENT_ID,
        "device": DEVICE_ID,
        "event": "session_complete",
        "score": int(score),
        "pickups": int(pickups),
        "elapsed_sec": int(elapsed_sec),
    }
    mqtt_client.publish(EVENT_TOPIC, json.dumps(payload), qos=0, retain=False)
    print(f"[MQTT] final event -> {payload}")


# Classification helper
def classify_session_state(
    sub_f: dict,
    L1_MIN: float,
    TILT_SUM_THRESH: float,
    PITCH_MIN: float,
    ROLL_MIN: float,
    ACTIVE_TILT_MIN: float,
):
    pitch_r = sub_f["pitch_range"]
    roll_r = sub_f["roll_range"]
    l1_peak = sub_f["l1_peak"]
    tilt_sum = pitch_r + roll_r

    pickup_detected = (
        l1_peak > L1_MIN
        and tilt_sum > TILT_SUM_THRESH
        and pitch_r > PITCH_MIN
        and roll_r > ROLL_MIN
    )

    if pickup_detected:
        return "phone_pickup", pitch_r, roll_r, l1_peak, tilt_sum

    if tilt_sum > ACTIVE_TILT_MIN:
        return "active_study", pitch_r, roll_r, l1_peak, tilt_sum

    return "still", pitch_r, roll_r, l1_peak, tilt_sum


# Session scoring helper
def update_session_score(
    score: float,
    state: str,
    now: float,
    last_phone_time: float,
    PHONE_PENALTY: int,
    ACTIVE_REWARD: int,
    STILL_REWARD: int,
    PHONE_COOLDOWN_SEC: int,
):
    phone_penalized = False

    if state == "phone_pickup":
        if (last_phone_time is None) or ((now - last_phone_time) >= PHONE_COOLDOWN_SEC):
            score -= PHONE_PENALTY
            last_phone_time = now
            phone_penalized = True

    elif state == "active_study":
        score += ACTIVE_REWARD

    else:
        score += STILL_REWARD

    score = clamp_score(score)
    return score, last_phone_time, phone_penalized


# Serial batch helpers
def wait_begin(comms: Communication) -> int:
    while True:
        msg = comms.receive_message()
        if msg is None:
            continue

        msg = msg.replace("\r", "").strip()

        if msg.startswith("BEGIN,"):
            try:
                return int(msg.split(",")[1])
            except Exception:
                pass


def read_batch(comms: Communication, n: int):
    t, ax, ay, az = [], [], [], []
    got = 0
    saw_end = False

    while got < n:
        msg = comms.receive_message()
        if msg is None:
            continue

        msg = msg.replace("\r", "").strip()
        if not msg:
            continue

        if msg == "END":
            saw_end = True
            break

        parts = msg.split(",")
        if len(parts) != 4:
            continue

        try:
            tt = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])
            z = int(parts[3])
        except Exception:
            continue

        t.append(tt)
        ax.append(x)
        ay.append(y)
        az.append(z)
        got += 1

    if not saw_end:
        while True:
            msg = comms.receive_message()
            if msg is None:
                continue
            msg = msg.replace("\r", "").strip()
            if msg == "END":
                break

    return np.array(t), np.array(ax), np.array(ay), np.array(az)


# Main program
if __name__ == "__main__":
    PORT = "COM13"
    BAUD = 115200

    fs = 100

    # Pickup detector thresholds
    TILT_SUM_THRESH = 0.24
    PITCH_MIN = 0.10
    ROLL_MIN = 0.10
    L1_MIN = 4700
    ACTIVE_WIN = 50
    SMOOTH_WIN = 10

    # Session settings
    SESSION_SEC = 30      # testing;
    # Session scoring weights
    PHONE_PENALTY = 15
    ACTIVE_REWARD = 1
    STILL_REWARD = 0
    
    PHONE_COOLDOWN_SEC = 8
    ACTIVE_TILT_MIN = 0.10

    # Session state variables
    session_started = False
    session_start_time = None
    session_end_time = None
    score = 100
    last_phone_time = None
    phone_pickups = 0

    # Connect to MQTT
    connect_mqtt()

    # Connect to ESP32
    comms = Communication(PORT, BAUD)
    time.sleep(2)
    print("Serial opened. Waiting for ESP32 reboot...")
    time.sleep(2.5)
    comms.clear()
    time.sleep(0.5)

    try:
        while True:
            if not session_started:
                user_cmd = input("\nPress Enter to start a study session, or type q to quit: ").strip().lower()
                if user_cmd == "q":
                    break

                session_started = True
                session_start_time = time.time()
                session_end_time = session_start_time + SESSION_SEC
                score = 100
                last_phone_time = None
                phone_pickups = 0

                comms.send_message("Study")
                time.sleep(0.2)

                print("Continuous study session started.")
                print("ESP32 is now streaming batches automatically.")
                print(f"\nStudy session started for {SESSION_SEC} seconds.")
                print(f"Starting score: {score}")

            now = time.time()
            time_left = int(session_end_time - now)

            if time_left <= 0:
                elapsed_sec = int(time.time() - session_start_time)

                print("\nStudy session complete.")
                print(f"Final score: {int(score)}")
                print(f"Phone pickups: {phone_pickups}")
                print(f"Elapsed time: {elapsed_sec} sec")

                # Publish to server/website ONLY at the end
                publish_final_status(score=int(score), pickups=phone_pickups, elapsed_sec=elapsed_sec)
                publish_final_event(score=int(score), pickups=phone_pickups, elapsed_sec=elapsed_sec)

                # Notify ESP32 that the session is done
                comms.send_message("state,session_done")
                comms.send_message(f"score,{int(score)}")
                comms.send_message("alert,0")

                session_started = False
                continue

            print(f"\nTime left: {time_left} sec | Current score: {int(score)}")
            print("Waiting for next automatic batch from ESP32...")

            n = wait_begin(comms)
            t, ax, ay, az = read_batch(comms, n)

            if len(ax) < fs:
                continue

            full_f, sub_f, start, end = filt.pickup_features_active_window(
                ax, ay, az,
                smooth_win=SMOOTH_WIN,
                active_win=ACTIVE_WIN
            )

            print(
                f"score window=[{start}:{end}] "
                f"l1={sub_f['l1_peak']:.1f} "
                f"pitch_range={sub_f['pitch_range']:.3f} "
                f"roll_range={sub_f['roll_range']:.3f}"
            )

            state, pitch_r, roll_r, l1_peak, tilt_sum = classify_session_state(
                sub_f,
                L1_MIN=L1_MIN,
                TILT_SUM_THRESH=TILT_SUM_THRESH,
                PITCH_MIN=PITCH_MIN,
                ROLL_MIN=ROLL_MIN,
                ACTIVE_TILT_MIN=ACTIVE_TILT_MIN
            )

            old_pickups = phone_pickups

            score, last_phone_time, phone_penalized = update_session_score(
                score=score,
                state=state,
                now=time.time(),
                last_phone_time=last_phone_time,
                PHONE_PENALTY=PHONE_PENALTY,
                ACTIVE_REWARD=ACTIVE_REWARD,
                STILL_REWARD=STILL_REWARD,
                PHONE_COOLDOWN_SEC=PHONE_COOLDOWN_SEC
            )

            if phone_penalized:
                phone_pickups += 1

            if state == "phone_pickup":
                alert = 1 if phone_penalized else 0
            else:
                alert = 0

            print(
                f"FULL  l1_peak={full_f['l1_peak']:.2f} "
                f"pitch_range={full_f['pitch_range']:.3f} "
                f"roll_range={full_f['roll_range']:.3f}"
            )

            print(
                f"SUB   l1_peak={sub_f['l1_peak']:.2f} "
                f"pitch_range={sub_f['pitch_range']:.3f} "
                f"roll_range={sub_f['roll_range']:.3f}"
            )

            print(
                f"SUB pitch start/end=({sub_f['pitch_start']:.3f},{sub_f['pitch_end']:.3f}) "
                f"min/max=({sub_f['pitch_min']:.3f},{sub_f['pitch_max']:.3f})"
            )

            print(
                f"SUB roll  start/end=({sub_f['roll_start']:.3f},{sub_f['roll_end']:.3f}) "
                f"min/max=({sub_f['roll_min']:.3f},{sub_f['roll_max']:.3f})"
            )

            print(
                f"pickup_check: "
                f"tilt_sum({tilt_sum:.3f}>{TILT_SUM_THRESH})={tilt_sum > TILT_SUM_THRESH}, "
                f"pitch_and_roll((pitch>{PITCH_MIN}) and (roll>{ROLL_MIN}))={(pitch_r > PITCH_MIN and roll_r > ROLL_MIN)}, "
                f"l1({l1_peak:.1f}>{L1_MIN})={l1_peak > L1_MIN}"
            )

            print(f"classified_state={state}")
            print(f"session_score={int(score)}")
            print(f"phone_penalized={phone_penalized}")
            print(f"phone_pickups={phone_pickups}")

            if DEBUG_PRINT:
                print(f"state={state} score={int(score)} alert={alert}")

            # Send current state back to ESP32 for OLED display
            comms.send_message(f"state,{state}")
            comms.send_message(f"score,{int(score)}")
            comms.send_message(f"alert,{alert}")

    except KeyboardInterrupt:
        pass

    finally:
        try:
            comms.send_message("sleep")
            comms.close()
        except Exception:
            pass

        disconnect_mqtt()
        