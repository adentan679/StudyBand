# StudyBand Testing and Limitations

This document separates the course dataset and implementation from checks performed without the wearable. It does not claim hardware validation or an independently measured classification accuracy.

## Recorded Dataset

The repository contains 70 recordings in `python/logged_data/`:

| Activity label | Recordings |
|---|---:|
| `phone_pickup` | 15 |
| `still` | 13 |
| `typing` | 14 |
| `writing` | 13 |
| `random_arm_move` | 15 |
| **Total** | **70** |

Each file contains 300 samples with columns `t,ax,ay,az`. The target acquisition rate is 100 Hz. The filenames label the performed activity; the running classifier produces only `phone_pickup`, `active_study`, and `still`.

These recordings supported feature exploration and threshold tuning. No independent held-out test split is documented, so performance on this dataset should not be presented as general accuracy across users.

## Current Classification Method

The pipeline searches each recording using 50-sample windows with a 5-sample step. It selects the window with the highest `2 * pitch_range + 2 * roll_range + 0.0002 * l1_peak` value, then applies the rules in `main.py`:

- Phone pickup: peak smoothed L1 exceeds 4700, combined pitch/roll range exceeds 0.24, and each individual range exceeds 0.10.
- Active study: the pickup rule fails, but combined range exceeds 0.10.
- Still: combined range is at most 0.10.

These are empirically selected features of raw ADC readings. They are not calibrated physical wrist angles or a direct measure of attention.

## Reproducing Offline Analysis

Follow [setup.md](setup.md), then run from `python/`:

```bash
python -m uv run --locked python analyze_data.py
```

This regenerates `analysis_summary.csv`. It currently uses a different final prediction rule from `main.py`: it accepts pitch **or** roll above threshold and adds a start-to-end shift condition. Align these rules before using its detector counts to assess the running classifier.

The existing motion JPGs also use earlier plotting calculations. They show edge effects from smoothing and report values that differ from the current selected-window features. Treat them as exploratory plots until regenerated from the same pipeline used for classification, with the selected window and axis units identified.

## Checks to Perform on the Wearable

### Dependency-update checks

The setup update was checked on Linux with Python 3.12.14:

- Installed the locked dependencies into a new virtual environment and checked package compatibility.
- Imported the runtime, data-logging, and analysis modules successfully.
- Calculated finite selected-window features for all 70 recordings.
- Rendered the dashboard's initial HTML and read its empty API state without connecting to MQTT.
- Ran the offline analysis script on a temporary copy of the recordings and generated a 70-row summary.

These checks do not validate Windows Bluetooth, a firmware build/upload, live MQTT/WebSocket delivery, or operation on the physical wearable. Python 3.11 is included in the dependency resolution but was not executed during these checks.

### Physical-system checklist

| Check | Expected observation |
|---|---|
| Connection | The configured serial port opens and the ESP32 receives `Study` |
| Batch transfer | `BEGIN,300`, 300 sample rows, and `END` arrive without missing data |
| Display feedback | The OLED receives state and score messages |
| Scoring | Score starts at 100, active study adds 1 up to 100, and a pickup subtracts 15 outside the 8-second cooldown |
| Session result | Final score, pickup count, and elapsed time reach the dashboard |
| Multiple participants | Distinct participant/device pairs appear and sort by descending score, then fewer pickups |
| Session lifecycle | Completion, restart, exit, and a disconnected device are handled consistently |

These are checks to perform, not recorded passes. Record the date, firmware version, connection mode, observed result, and any failure when testing.

## Known Implementation Limitations

1. **Stop-message mismatch:** `main.py` sends `state,session_done`, while the firmware's explicit stop branch expects `session_done`. The current message does not enter that branch. Clean program exit sends `sleep` separately.
2. **Blocking batch waits:** missing serial data can keep the processing loop waiting beyond the configured session duration.
3. **Logging instructions:** `log_data.py` still describes button-driven transfer, but the current firmware sends full batches automatically in continuous mode.
4. **Dashboard delivery:** MQTT callbacks start broadcasts on newly created event loops rather than the server's existing loop. Reliable live updates need validation and may require a code change.
5. **Temporary results:** the dashboard keeps its state in memory. Retained broker messages may repopulate some rows, but there is no persistent session-history database.
6. **Motion ambiguity:** writing, typing, and unrelated arm movements may overlap in feature values. Classification and score do not directly establish concentration.

Future evaluation should use separate tuning and test recordings, include different users and wrist placements, and report phone-pickup false positives and missed pickups. Raw activity labels must be mapped explicitly before evaluating the three runtime states.
