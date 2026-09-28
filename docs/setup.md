# StudyBand Setup

This guide covers the course prototype: ESP32 firmware, Bluetooth serial, Python motion processing, and the FastAPI dashboard. The Python environment targets **Python 3.11 or 3.12**; the commands below use **3.12**.

Motion classification runs on the computer. The wearable does not connect directly to MQTT: Python publishes completed session results to the broker.

## 1. Requirements

For the complete system:

- The StudyBand ESP32 board, accelerometer, OLED, button, and existing project wiring.
- A USB data cable for firmware upload.
- A computer with Bluetooth Classic serial support, or a USB serial connection using the firmware option described below.
- Git, Python 3.12, VS Code, and the PlatformIO IDE extension.
- Internet access for dependency installation and the configured public MQTT broker.

The firmware selects PlatformIO's `featheresp32` board and uses `BluetoothSerial`. Confirm that the actual ESP32 board matches this configuration. Bluetooth Classic serial is different from BLE; not every ESP32 variant supports it.

The recordings can be analyzed without the wearable. The dashboard can also display its empty page without motion data, but populated session results require incoming MQTT messages.

## 2. Download the Repository

From a terminal:

```bash
git clone https://github.com/adentan679/StudyBand.git
cd StudyBand
```

If you already have a local copy, open that folder instead.

The relevant paths are:

| Path | Purpose |
|---|---|
| `firmware/Arduino/Study_Band_ESP32/` | PlatformIO firmware project |
| `python/main.py` | Session control, classification, scoring, and MQTT publishing |
| `python/log_data.py` | Labeled motion recording |
| `python/analyze_data.py` | Offline feature analysis |
| `python/ECE16Lib/` | Local serial and signal-processing modules |
| `python/explorer/server.py` | Dashboard backend and MQTT subscriber |
| `python/logged_data/` | Recorded motion CSVs |

## 3. Install Python Dependencies

Run these commands from the repository root:

```bash
cd python
python -m pip install uv
python -m uv sync --locked --python 3.12
```

`uv` creates a local `.venv` and installs the versions recorded in `uv.lock`. The commands in this guide use `uv run`, so manual environment activation is unnecessary. Keep subsequent Python commands in the **`StudyBand/python/` directory** so local imports and relative data paths work.

The dependency files have distinct roles:

| File | Purpose |
|---|---|
| `pyproject.toml` | Declares required packages and supported Python versions |
| `uv.lock` | Records resolved versions for reproducible installation |
| `requirements.txt` | Generated export of the lockfile for pip users |

Do not edit the generated dependency files independently. After intentionally changing `pyproject.toml`, regenerate them with:

```bash
python -m uv lock
python -m uv export --locked --format requirements.txt --no-emit-project --output-file requirements.txt
```

### Alternative: pip

If you prefer a manually activated environment, run from `StudyBand/python/`:

```bash
python -m venv .venv
```

Activate using the command for your terminal:

| Terminal | Activation command |
|---|---|
| Windows Git Bash | `source .venv/Scripts/activate` |
| Windows PowerShell | `.\.venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.venv\Scripts\activate.bat` |
| macOS/Linux | `source .venv/bin/activate` |

Then install the generated requirements:

```bash
python -m pip install -r requirements.txt
```

For this route, replace `python -m uv run --locked python` in the remaining commands with `python`. The existing `setup.py` is not needed when running from this source directory.

## 4. Prepare and Upload the Firmware

1. Open `firmware/Arduino/Study_Band_ESP32/` as the project folder in VS Code with PlatformIO.
2. Copy `.env.example` to `.env` in that same folder. The build script requires the file to exist. For the supplied Bluetooth firmware, keep the Wi-Fi fields empty; these settings are not used by the firmware.
3. Connect the ESP32 through a USB data cable.
4. Use PlatformIO **Build**, then **Upload**. PlatformIO reads `platformio.ini` and installs its listed libraries.
5. Close any serial monitor before opening the device from Python.

No Python MQTT package needs to be installed on the ESP32. Python dependencies and PlatformIO firmware libraries are managed separately.

### Bluetooth serial: current default

`src/communication.cpp` contains:

```cpp
#define USE_BT 1
```

The Bluetooth device advertises as **`Deadline`**. On Windows, pair it through Bluetooth settings and find its **outgoing Bluetooth serial COM port**. This may differ from the USB upload port.

List the serial ports visible to Python from `StudyBand/python/`:

```bash
python -m uv run --locked python -m serial.tools.list_ports -v
```

### USB serial option

To communicate through the USB cable, set `USE_BT` to `0`, rebuild, and upload. Select the USB serial port in Python and keep `BAUD = 115200`.

Use this route if the computer does not expose a usable Bluetooth Classic serial port. Upload always uses USB regardless of the selected data-communication mode.

## 5. Configure the Python Programs

Copy `python/.env.example` to `python/.env`. Its `STUDENT_ID` is a **dashboard server label**, read by `explorer/server.py`.

The current `main.py` and `log_data.py` do **not** load this `.env` file. Edit their source settings as follows:

| File | Setting | What to choose |
|---|---|---|
| `main.py` | `PORT` | Your Bluetooth or USB serial port; the course value is `COM13` |
| `main.py` | `BAUD` | Keep `115200` |
| `main.py` | `STUDENT_ID` | A display name or alias, such as `aden` |
| `main.py` | `DEVICE_ID` | A device label, such as `studyband_aden` |
| `main.py` | `SESSION_SEC` | Session length in seconds; the course test setting is `30` |
| `main.py` and `explorer/server.py` | `MQTT_BROKER`, `MQTT_PORT` | Use the same broker and port in both files |
| `log_data.py` | `PORT`, `BAUD` | Match the same device connection |
| `log_data.py` | `CURRENT_LABEL` | The activity being recorded |

Each simultaneous processing instance should have a unique participant/device pair. Use the same session duration when comparing participants.

The course configuration uses `broker.emqx.io` on port `1883`, with messages under `focus_tracker/<student_id>/<device>/...`. This is a shared public broker without application-level privacy or authentication. Use aliases and demonstration data. Configuring authenticated or encrypted MQTT requires additional code; it is not provided by the current `.env` files.

## 6. Launch the Dashboard and Study Session

Open **two terminals**, both in `StudyBand/python/`.

In terminal 1:

```bash
python -m uv run --locked python explorer/server.py
```

Open [http://localhost:8000](http://localhost:8000). Launch this script directly: the MQTT worker starts inside its `if __name__ == "__main__"` block. Running only `uvicorn explorer.server:app` does not start that worker in the current implementation.

In terminal 2:

```bash
python -m uv run --locked python main.py
```

Press **Enter** at the prompt to start a session. The computer receives motion batches, prints classification and scoring information, and sends display feedback to the wearable.

At the end of the session, Python publishes the final score, pickup count, and elapsed time. The leaderboard receives **completed results**, not every motion batch. Session completion can run past the configured duration while the program waits for a batch.

Type `q` at the next session prompt to exit cleanly, or use `Ctrl+C`. Close the dashboard server with `Ctrl+C` when finished.

## 7. Analyze Existing Recordings Without Hardware

From `StudyBand/python/`:

```bash
python -m uv run --locked python analyze_data.py
```

The script reads `logged_data/`, prints feature summaries, and writes **`analysis_summary.csv`**, replacing an existing file of that name. Its plot call is currently commented out, so it does not automatically display or regenerate the JPG plots.

See [Testing and Limitations](testing.md) before interpreting detector counts: the offline prediction rule currently differs from the running classifier.

## 8. Collect New Recordings

Stop `main.py` so only one process owns the serial port. Set `PORT` and `CURRENT_LABEL` in `log_data.py`, then run:

```bash
python -m uv run --locked python log_data.py
```

Use one of `phone_pickup`, `still`, `typing`, `writing`, or `random_arm_move`. Press Enter and perform the labeled activity during collection. CSVs are saved in `logged_data/` with columns `t,ax,ay,az`; `t` is the device timestamp in milliseconds and the axes contain raw ADC readings.

The current firmware automatically sends a full 300-sample batch after `Study`. The logger's printed instruction to press the device button is outdated for this firmware. For controlled recordings, collect one clip, exit with `q`, and restart for the next clip; the current logger and continuous firmware have not been fully reconciled for repeated interactive collection.

## Troubleshooting

| Symptom | Check |
|---|---|
| `ModuleNotFoundError` | Run from `StudyBand/python/` through the installed environment; run `uv sync --locked` again |
| Port missing or access denied | Check Bluetooth pairing/USB connection and close other serial programs |
| No `BEGIN` batch arrives | Confirm `USE_BT`, the selected port, and uploaded firmware; restart after a connection failure |
| Empty leaderboard | Wait for a session to finish; confirm both processes use the same reachable broker |
| Dashboard loads but receives nothing | Launch `python explorer/server.py` directly so its MQTT worker starts |
| WebSocket disconnects | Inspect server logs; the current cross-thread broadcast implementation needs further validation |
| Firmware build reports missing `.env` | Copy the firmware example into the PlatformIO project root as `.env` |
| Lockfile is out of date | Use the matching `pyproject.toml` and `uv.lock` from the same update |

## Prototype Boundaries

These instructions document the supplied implementation. The firmware stop-message mismatch, offline/live classifier differences, and live dashboard delivery limitations remain documented in [testing.md](testing.md). A successful dependency installation does not establish full hardware operation.

Keep `.env` files, virtual environments, caches, and build outputs out of version control. The supplied `.gitignore` prevents new untracked files from being added; it does not remove copies already tracked in Git.

## Dependency Reference

Package installation and lockfile commands follow the [official uv locking and syncing documentation](https://docs.astral.sh/uv/concepts/projects/sync/).
