import numpy as np
import scipy.signal as sig

"""
A module to provide common DSP filtering functionalities
"""

"""
Compute the L1-norm for 3 vectors: L1 = |ax| + |ay| + |az|
Note: Realistically, this function should be more general to any
number of input vectors, but we will only use it for 3.
"""

def l1_norm(ax, ay, az):
  ax = np.asarray(ax, dtype=float)
  ay = np.asarray(ay, dtype=float)
  az = np.asarray(az, dtype=float)
  return np.abs(ax) + np.abs(ay) + np.abs(az)

"""
Compute the moving average efficiently over a window 'win'
"""
def moving_average(x, win):
  ma = np.zeros(x.size)
  for i in np.arange(0,len(x)):
    if(i < win): # use mean until filter is "on"
      ma[i] = np.mean(x[:i+1])
    else:
      ma[i] = ma[i-1] + (x[i] - x[i-win])/win
  return ma

"""
Detrend the signal by removing the moving average
"""
def detrend(x, win=50):
  return x - moving_average(x, win)

"""
Compute the gradient of the signal
"""
def gradient(x):
  return np.gradient(x)

"""
Compute the power spectral density of the signal
"""
def psd(x, nfft, fs):
  return sig.welch(x, nfft=nfft, fs=fs)

"""
Create either high-pass or low-pass filters
"""
def create_filter(order, cutoff, btype, fs):
  b, a = sig.butter(order, cutoff, btype=btype, fs=fs)
  return b, a

"""
Filter the signal with the filter defined by the coefficients in b/a
"""
def filter(b, a, x):
  return sig.filtfilt(b, a, x)

"""
Count the number of peaks found between the lower and upper thresholds
"""
def count_peaks(x, thresh_low, thresh_high):
  peaks, _ = sig.find_peaks(x)

  count = 0
  locations = []
  for peak in peaks:
    if x[peak] >= thresh_low and x[peak] <= thresh_high:
      count += 1
      locations.append(peak)

  return count, locations

"""
Normalize the signal from 0 to 1
"""
def normalize(x):
  return (x - min(x)) / (max(x) - min(x))

def accel_tilt(ax, ay, az):
    ax = np.asarray(ax, dtype=float)
    ay = np.asarray(ay, dtype=float)
    az = np.asarray(az, dtype=float)

    pitch = np.arctan2(ax, np.sqrt(ay**2 + az**2))
    roll = np.arctan2(ay, np.sqrt(ax**2 + az**2))
    return pitch, roll

def window_mean(x, start, end):
    x = np.asarray(x, dtype=float)
    start = max(0, start)
    end = min(len(x), end)
    if end <= start:
        return 0.0
    return float(np.mean(x[start:end]))

def window_std(x, start, end):
    x = np.asarray(x, dtype=float)
    start = max(0, start)
    end = min(len(x), end)
    if end <= start:
        return 0.0
    return float(np.std(x[start:end]))

def best_pickup_window(ax, ay, az, win_size=50, step=5, smooth_win=10):
    """
    Search across the batch and return the sub-window that looks most like
    a phone pickup, based on both motion and tilt change.
    """
    ax = np.asarray(ax, dtype=float)
    ay = np.asarray(ay, dtype=float)
    az = np.asarray(az, dtype=float)

    n = len(ax)
    if n == 0:
        return 0, 0

    if n <= win_size:
        return 0, n

    best_start = 0
    best_end = win_size
    best_score = -1e9
    best_features = None

    for start in range(0, n - win_size + 1, step):
        end = start + win_size
        f = pickup_features(ax[start:end], ay[start:end], az[start:end], smooth_win=smooth_win)

        # combined score: reward tilt change strongly, but still require motion
        score = (
            2.0 * f["pitch_range"] +
            2.0 * f["roll_range"] +
            0.0002 * f["l1_peak"]
        )

        if score > best_score:
            best_score = score
            best_start = start
            best_end = end
            best_features = f

    return best_start, best_end, best_features

def pickup_features(ax, ay, az, smooth_win=15):
    ax = np.asarray(ax, dtype=float)
    ay = np.asarray(ay, dtype=float)
    az = np.asarray(az, dtype=float)

    l1 = l1_norm(ax, ay, az)
    l1_smooth = moving_average(l1, smooth_win)

    pitch, roll = accel_tilt(ax, ay, az)

    features = {
        "l1_smooth": l1_smooth,
        "pitch": pitch,
        "roll": roll,

        "l1_peak": float(np.max(l1_smooth)) if len(l1_smooth) else 0.0,
        "l1_mean": float(np.mean(l1_smooth)) if len(l1_smooth) else 0.0,

        "pitch_min": float(np.min(pitch)) if len(pitch) else 0.0,
        "pitch_max": float(np.max(pitch)) if len(pitch) else 0.0,
        "pitch_start": float(pitch[0]) if len(pitch) else 0.0,
        "pitch_end": float(pitch[-1]) if len(pitch) else 0.0,

        "roll_min": float(np.min(roll)) if len(roll) else 0.0,
        "roll_max": float(np.max(roll)) if len(roll) else 0.0,
        "roll_start": float(roll[0]) if len(roll) else 0.0,
        "roll_end": float(roll[-1]) if len(roll) else 0.0,
    }

    features["pitch_range"] = features["pitch_max"] - features["pitch_min"]
    features["roll_range"]  = features["roll_max"] - features["roll_min"]
    features["pitch_shift"] = features["pitch_end"] - features["pitch_start"]
    features["roll_shift"]  = features["roll_end"] - features["roll_start"]
    features["abs_pitch_shift"] = abs(features["pitch_shift"])
    features["abs_roll_shift"]  = abs(features["roll_shift"])

    return features


def pickup_features_active_window(ax, ay, az, smooth_win=10, active_win=50):
    full = pickup_features(ax, ay, az, smooth_win=smooth_win)

    start, end, sub = best_pickup_window(
        ax, ay, az,
        win_size=active_win,
        step=5,
        smooth_win=smooth_win
    )

    return full, sub, start, end