from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import asyncio
import json
import os
import threading
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from pathlib import Path

load_dotenv()

# =========================================================
# Config
# =========================================================
STUDENT_ID = os.getenv("STUDENT_ID", "UNKNOWN")
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_CLIENT_ID = f"{STUDENT_ID}_focus_dashboard"

# Subscribe to ALL focus trackers, not just one
STATUS_SUB = "focus_tracker/+/+/status"
EVENT_SUB = "focus_tracker/+/+/event"

app = FastAPI(title="Focus Tracker Dashboard")


BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

connected_clients: list[WebSocket] = []

# =========================================================
# In-memory shared state
# Keyed by "student_id/device"
# =========================================================
devices = {}
event_log = []
MAX_EVENTS = 40
state_lock = threading.Lock()


# =========================================================
# Helpers
# =========================================================
def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default


def parse_topic(topic: str):
    """
    Expected:
      focus_tracker/<student_id>/<device>/status
      focus_tracker/<student_id>/<device>/event
    """
    parts = topic.split("/")
    if len(parts) != 4:
        return None, None, None
    prefix, student_id, device, kind = parts
    if prefix != "focus_tracker":
        return None, None, None
    return student_id, device, kind


def device_key(student_id: str, device: str):
    return f"{student_id}/{device}"


def get_or_create_device(student_id: str, device: str):
    key = device_key(student_id, device)
    if key not in devices:
        devices[key] = {
            "student_id": student_id,
            "device": device,
            "mode": "IDLE",
            "score": 0,
            "pickups": 0,
            "elapsed_sec": 0,
            "break_remaining_sec": 0,
            "last_update": now_string(),
            "last_event": "-",
        }
    return devices[key]


async def broadcast_state():
    if not connected_clients:
        return

    with state_lock:
        leaderboard = sorted(
            devices.values(),
            key=lambda d: (-d["score"], d["pickups"], d["student_id"], d["device"])
        )
        payload = {
            "student_id": STUDENT_ID,
            "leaderboard": leaderboard,
            "events": event_log[:15]
        }

    dead = []
    for ws in connected_clients:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.append(ws)

    for ws in dead:
        if ws in connected_clients:
            connected_clients.remove(ws)


def schedule_broadcast():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(broadcast_state())
    loop.close()


# =========================================================
# MQTT handlers
# =========================================================
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Connected rc={rc}")
    client.subscribe(STATUS_SUB)
    client.subscribe(EVENT_SUB)
    # client.subscribe("focus_tracker/#")
    print(f"[MQTT] Subscribed to {STATUS_SUB}")
    print(f"[MQTT] Subscribed to {EVENT_SUB}")
    # print("[MQTT] Subscribed to focus_tracker/#")

def on_message(client, userdata, msg):
    topic = msg.topic
    raw = msg.payload.decode("utf-8", errors="ignore").strip()
    print(f"[MQTT] {topic} -> {raw}")

    student_id, topic_device, kind = parse_topic(topic)
    if not student_id or not topic_device:
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("[MQTT] Ignoring non-JSON payload")
        return

    payload_student = payload.get("student_id", student_id)
    payload_device = payload.get("device", topic_device)

    with state_lock:
        row = get_or_create_device(payload_student, payload_device)

        if kind == "status":
            row["mode"] = payload.get("mode", row["mode"])
            row["score"] = safe_int(payload.get("score", row["score"]))
            row["pickups"] = safe_int(payload.get("pickups", row["pickups"]))
            row["elapsed_sec"] = safe_int(payload.get("elapsed_sec", row["elapsed_sec"]))
            row["break_remaining_sec"] = safe_int(
                payload.get("break_remaining_sec", row["break_remaining_sec"])
            )
            row["last_update"] = now_string()

        elif kind == "event":
            event_name = payload.get("event", "unknown_event")
            row["mode"] = payload.get("mode", row["mode"])
            row["score"] = safe_int(payload.get("score", row["score"]))
            row["pickups"] = safe_int(payload.get("pickups", row["pickups"]))
            row["last_event"] = event_name
            row["last_update"] = now_string()

            event_log.insert(0, {
                "time": now_string(),
                "student_id": payload_student,
                "device": payload_device,
                "event": event_name,
                "mode": row["mode"],
                "score": row["score"],
                "pickups": row["pickups"],
            })

            if len(event_log) > MAX_EVENTS:
                del event_log[MAX_EVENTS:]

    threading.Thread(target=schedule_broadcast, daemon=True).start()


mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


def mqtt_worker():
    while True:
        try:
            print("[MQTT] Connecting...")
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            mqtt_client.loop_forever()
        except Exception as e:
            print(f"[MQTT] Error: {e}")
            print("[MQTT] Reconnecting in 3 seconds...")
            import time
            time.sleep(3)


# =========================================================
# Routes
# =========================================================
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "student_id": STUDENT_ID
    })


@app.get("/api/state")
async def api_state():
    with state_lock:
        leaderboard = sorted(
            devices.values(),
            key=lambda d: (-d["score"], d["pickups"], d["student_id"], d["device"])
        )
        return {
            "student_id": STUDENT_ID,
            "leaderboard": leaderboard,
            "events": event_log[:15]
        }


@app.post("/api/command/{student_id}/{device}/{cmd}")
async def send_command(student_id: str, device: str, cmd: str):
    cmd = cmd.upper().strip()
    if cmd not in {"START", "STOP", "RESET"}:
        return {"error": "Invalid command"}

    topic = f"focus_tracker/{student_id}/{device}/cmd"
    mqtt_client.publish(topic, cmd)
    return {"success": True, "topic": topic, "command": cmd}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        await websocket.send_text(json.dumps(await api_state()))
        while True:
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# =========================================================
# Main
# =========================================================
if __name__ == "__main__":
    threading.Thread(target=mqtt_worker, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)