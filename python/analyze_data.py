# analyze_data.py
# ------------------------------------------------------------
# PURPOSE:
# Compare phone_pickup vs still datasets so we can choose
# thresholds for live detection in main.py.
#
# INPUT:
# CSV files in logged_data/ with names like:
#   20260310_183250_phone_pickup.csv
#   20260310_184010_still.csv
#
# OUTPUT:
# 1. Per-file plots
# 2. Printed feature summaries
# 3. analysis_summary.csv
#
# FEATURES USED:
# - l1_peak       : overall motion magnitude peak
# - energy_peak   : sudden movement peak
# - pitch_range   : wrist forward/back rotation
# - roll_range    : wrist side rotation
# ------------------------------------------------------------

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import ECE16Lib.DSP as filt
DATA_DIR = Path("logged_data")

SMOOTH_WIN = 10
ACTIVE_WIN = 50

L1_MIN = 4700
TILT_SUM_THRESH = 0.24
PITCH_MIN = 0.10
ROLL_MIN = 0.10
SHIFT_MIN = 0.05

# Simple smoothing helper
def moving_average(x, window=15):
    if window <= 1:
        return x.copy()
    return np.convolve(x, np.ones(window) / window, mode="same")


# Compute all signals we care about from raw accelerometer data
def compute_signals(df):
    t = df["t"].to_numpy(dtype=float)
    ax = df["ax"].to_numpy(dtype=float)
    ay = df["ay"].to_numpy(dtype=float)
    az = df["az"].to_numpy(dtype=float)

    # overall motion magnitude
    l1 = np.abs(ax) + np.abs(ay) + np.abs(az)
    l1_smooth = moving_average(l1, window=15)

    # sudden motion / impulse strength
    energy = np.abs(np.gradient(l1_smooth))

    # wrist orientation
    pitch = np.arctan2(ax, np.sqrt(ay**2 + az**2))
    roll = np.arctan2(ay, np.sqrt(ax**2 + az**2))

    # smooth orientation
    pitch = moving_average(pitch, window=15)
    roll = moving_average(roll, window=15)

    return {
        "t": t,
        "ax": ax,
        "ay": ay,
        "az": az,
        "l1_smooth": l1_smooth,
        "energy": energy,
        "pitch": pitch,
        "roll": roll,
    }

def trim_edges(x, n_trim=20):
    if len(x) <= 2 * n_trim:
        return x
    return x[n_trim:-n_trim]

# Summarize a motion window into a few features
def summarize(features):
    l1 = features["l1_smooth"]
    energy_mid = trim_edges(features["energy"], n_trim=20)
    pitch = features["pitch"]
    roll = features["roll"]

    return {
        "l1_peak": float(np.max(l1)),
        "l1_mean": float(np.mean(l1)),
        "energy_peak": float(np.max(energy_mid)),
        "energy_mean": float(np.mean(energy_mid)),
        "pitch_range": float(np.max(pitch) - np.min(pitch)),
        "roll_range": float(np.max(roll) - np.min(roll)),

        "pitch_shift": float(pitch[-1] - pitch[0]),
        "roll_shift": float(roll[-1] - roll[0]),
        "abs_pitch_shift": float(abs(pitch[-1] - pitch[0])),
        "abs_roll_shift": float(abs(roll[-1] - roll[0])),
    }
    


# Extract label from filename
# Example:
#   20260310_183250_phone_pickup.csv -> phone_pickup
#   20260310_184010_still.csv        -> still
def get_label(filepath):
    stem = filepath.stem
    parts = stem.split("_")
    if len(parts) < 3:
        return "unknown"
    return "_".join(parts[2:])


# Plot one dataset
def plot_file(filepath, features, summary, label):
    t = features["t"]

    fig, axs = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
    fig.suptitle(f"{filepath.name} | label={label}", fontsize=12)

    # raw accelerometer
    axs[0].plot(t, features["ax"], label="ax")
    axs[0].plot(t, features["ay"], label="ay")
    axs[0].plot(t, features["az"], label="az")
    axs[0].set_ylabel("Accel")
    axs[0].legend()
    axs[0].grid(True)

    # motion magnitude
    axs[1].plot(t, features["l1_smooth"])
    axs[1].set_ylabel("L1")
    axs[1].grid(True)

    # orientation
    axs[2].plot(t, features["pitch"], label="pitch")
    axs[2].plot(t, features["roll"], label="roll")
    axs[2].set_ylabel("Angle")
    axs[2].legend()
    axs[2].grid(True)

    # sudden motion
    axs[3].plot(t, features["energy"])
    axs[3].set_ylabel("Energy")
    axs[3].set_xlabel("Time")
    axs[3].grid(True)

    # feature summary box
    text = (
        f"L1 peak: {summary['l1_peak']:.2f}\n"
        f"Energy peak: {summary['energy_peak']:.2f}\n"
        f"Pitch range: {summary['pitch_range']:.3f}\n"
        f"Roll range: {summary['roll_range']:.3f}"
    )

    axs[1].text(
        0.98, 0.95,
        text,
        transform=axs[1].transAxes,
        ha="right",
        va="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8)
    )

    plt.tight_layout()
    plt.show()
    plt.close(fig)   # IMPORTANT: close figure so next file displays correctly


def main():
    if not DATA_DIR.exists():
        print("logged_data folder not found.")
        return

    files = sorted(DATA_DIR.glob("*.csv"))
    if not files:
        print("No CSV files found in logged_data/")
        return

    # only keep the two classes we care about for threshold design
    keep_labels = {"phone_pickup", "still", "writing", "typing", "random_arm_move"}
    rows = []

    for filepath in files:
        label = get_label(filepath)
        if label not in keep_labels:
            continue

        try:
            df = pd.read_csv(filepath)

            required = {"t", "ax", "ay", "az"}
            if not required.issubset(df.columns):
                print(f"Skipping {filepath.name}: missing columns")
                continue

            if len(df) < 5:
                print(f"Skipping {filepath.name}: not enough samples")
                continue

            ax = df["ax"].to_numpy(dtype=float)
            ay = df["ay"].to_numpy(dtype=float)
            az = df["az"].to_numpy(dtype=float)

            full_f, sub_f, start, end = filt.pickup_features_active_window(
                ax, ay, az,
                smooth_win=SMOOTH_WIN,
                active_win=ACTIVE_WIN
            )

            row = {
                "file": filepath.name,
                "label": label,
                "n_samples": len(df),

                "full_l1_peak": full_f["l1_peak"],
                "full_pitch_range": full_f["pitch_range"],
                "full_roll_range": full_f["roll_range"],

                "sub_l1_peak": sub_f["l1_peak"],
                "sub_pitch_range": sub_f["pitch_range"],
                "sub_roll_range": sub_f["roll_range"],
                "sub_tilt_sum": sub_f["pitch_range"] + sub_f["roll_range"],

                "sub_pitch_shift": abs(sub_f["pitch_end"] - sub_f["pitch_start"]),
                "sub_roll_shift": abs(sub_f["roll_end"] - sub_f["roll_start"]),

                "active_start": start,
                "active_end": end,
            }
            rows.append(row)

            print(f"\nFile: {filepath.name}")
            print(f"  Label:           {label}")
            print(f"  Samples:         {len(df)}")
            print(f"  FULL l1 peak:    {full_f['l1_peak']:.2f}")
            print(f"  FULL pitch rng:  {full_f['pitch_range']:.3f}")
            print(f"  FULL roll rng:   {full_f['roll_range']:.3f}")
            print(f"  SUB  l1 peak:    {sub_f['l1_peak']:.2f}")
            print(f"  SUB  pitch rng:  {sub_f['pitch_range']:.3f}")
            print(f"  SUB  roll rng:   {sub_f['roll_range']:.3f}")
            print(f"  SUB  tilt sum:   {row['sub_tilt_sum']:.3f}")
            print(f"  SUB  p shift:    {row['sub_pitch_shift']:.3f}")
            print(f"  SUB  r shift:    {row['sub_roll_shift']:.3f}")
            print(f"  Active window:   [{start}:{end}]")

            #plot_file(filepath, features, summary, label)

            # pause so plots don't all stack weirdly
            #input("Press Enter for next file...")

        except Exception as e:
            print(f"Error reading {filepath.name}: {e}")

    if not rows:
        print("No valid labeled files found.")
        return

    summary_df = pd.DataFrame(rows)

    metric_cols = [
        "full_l1_peak",
        "full_pitch_range",
        "full_roll_range",
        "sub_l1_peak",
        "sub_pitch_range",
        "sub_roll_range",
        "sub_tilt_sum",
        "sub_pitch_shift",
        "sub_roll_shift",
    ]

    print("\n=== CLASS AVERAGES ===")
    print(summary_df.groupby("label")[metric_cols].mean())

    print("\n=== CLASS MEAN / STD / MIN / MAX ===")
    print(summary_df.groupby("label")[metric_cols].agg(["mean", "std", "min", "max"]))
    
    print("\n=== CURRENT DETECTOR THRESHOLDS ===")
    print(f"L1_MIN = {L1_MIN}")
    print(f"TILT_SUM_THRESH = {TILT_SUM_THRESH}")
    print(f"PITCH_MIN = {PITCH_MIN}")
    print(f"ROLL_MIN = {ROLL_MIN}")
    print(f"SHIFT_MIN = {SHIFT_MIN}")

    summary_df["pred_phone_pickup"] = (
        (summary_df["sub_l1_peak"] > L1_MIN) &
        (summary_df["sub_tilt_sum"] > TILT_SUM_THRESH) &
        (
            (summary_df["sub_pitch_range"] > PITCH_MIN) |
            (summary_df["sub_roll_range"] > ROLL_MIN)
        ) &
        (
            (summary_df["sub_pitch_shift"] > SHIFT_MIN) |
            (summary_df["sub_roll_shift"] > SHIFT_MIN)
        )
    )
    summary_df.to_csv("analysis_summary.csv", index=False)
    print("\nSaved feature table to analysis_summary.csv")
    
    print("\n=== DETECTOR COUNTS ===")
    print(pd.crosstab(summary_df["label"], summary_df["pred_phone_pickup"]))
   
    print("\n=== MISSED PICKUP FILES ===")
    missed = summary_df[
        (summary_df["label"] == "phone_pickup") &
        (summary_df["pred_phone_pickup"] == False)
    ]
    if missed.empty:
        print("None")
    else:
        print(
            missed[
                [
                    "file",
                    "sub_l1_peak",
                    "sub_pitch_range",
                    "sub_roll_range",
                    "sub_tilt_sum",
                    "sub_pitch_shift",
                    "sub_roll_shift",
                    "active_start",
                    "active_end",
                ]
            ]
        )

    print("\n=== FALSE POSITIVE FILES ===")
    fp = summary_df[
        (summary_df["label"] != "phone_pickup") &
        (summary_df["pred_phone_pickup"] == True)
    ]
    if fp.empty:
        print("None")
    else:
        print(
            fp[
                [
                    "file",
                    "label",
                    "sub_l1_peak",
                    "sub_pitch_range",
                    "sub_roll_range",
                    "sub_tilt_sum",
                    "sub_pitch_shift",
                    "sub_roll_shift",
                    "active_start",
                    "active_end",
                ]
            ]
        )

if __name__ == "__main__":
    main()