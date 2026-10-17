"""Run with the project venv: python algorithm/anomaly_detection/train.py."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
import json
from datetime import datetime, UTC
import joblib
import numpy as np
import sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from algorithm.anomaly_detection.config import MODEL_PATH, FEATURES, SEED, ESTIMATORS, CONTAMINATION
from algorithm.anomaly_detection.dataset import normal_dataset

if __name__ == "__main__":
    data = normal_dataset(10000, SEED)
    pipeline = make_pipeline(StandardScaler(), IsolationForest(n_estimators=ESTIMATORS, contamination=CONTAMINATION, random_state=SEED, n_jobs=1))
    pipeline.fit(data)
    raw = -pipeline.score_samples(data)
    cutoff = -float(pipeline.named_steps["isolationforest"].offset_)
    artifact = {"pipeline": pipeline, "features": FEATURES, "calibration": {"median": float(np.median(raw)), "cutoff": cutoff},
                "version": "pump-if-m3-v1", "sklearn_version": sklearn.__version__, "seed": SEED,
                "trained_at": datetime.now(UTC).isoformat(), "samples": len(data), "source": "DeviceSimulator normal trajectories + synthetic sensor noise"}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH, compress=3)
    from algorithm.anomaly_detection.evaluate import evaluate
    metrics = evaluate(artifact)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("Model saved:", MODEL_PATH)
