import numpy as np
from algorithm.anomaly_detection.config import FEATURES

def feature_row(device) -> list[float]:
    return [float(getattr(device, name)) for name in FEATURES]

def normalize_scores(raw, calibration):
    # Monotone transform of -score_samples; the trained IF cutoff maps to 0.60.
    # This is a display severity scale, not a calibrated failure probability.
    median, cutoff = calibration["median"], calibration["cutoff"]
    distance = max(cutoff - median, 0.015)
    raw = np.asarray(raw)
    lower = 0.12 + (raw - median) * 0.48 / distance
    upper = 0.60 + (raw - cutoff) * 0.40 / 0.25
    return np.clip(np.where(raw <= cutoff, lower, upper), 0.02, 0.99)
