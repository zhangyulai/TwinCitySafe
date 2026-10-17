import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
import json
import joblib
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from algorithm.anomaly_detection.config import MODEL_PATH, REPORT_DIR
from algorithm.anomaly_detection.dataset import evaluation_dataset, trajectory
from algorithm.anomaly_detection.features import normalize_scores

def evaluate(artifact):
    data, truth, kinds = evaluation_dataset(20261002)
    raw = -artifact["pipeline"].score_samples(data)
    scores = normalize_scores(raw, artifact["calibration"])
    predicted = scores >= 0.6
    precision, recall, f1, _ = precision_recall_fscore_support(truth, predicted, average="binary", zero_division=0)
    per_fault = {}
    for kind in ("bearing_degradation", "overheat", "low_efficiency"):
        selected = kinds == kind
        per_fault[kind] = {"samples": int(selected.sum()), "recall": float(predicted[selected].mean())}
    result = {"model_version": artifact["version"], "sklearn_version": artifact["sklearn_version"],
        "training_samples": artifact["samples"], "training_seed": artifact["seed"], "evaluation_seed": 20261002,
        "evaluation_samples": len(truth), "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "confusion_matrix": confusion_matrix(truth, predicted).tolist(), "normal_false_positive_rate": float(predicted[kinds == "normal"].mean()),
        "per_fault": per_fault, "threshold": 0.6, "calibration": artifact["calibration"],
        "scope": "Synthetic held-out trajectories with independent seeds; fault labels start at 45 simulated seconds. Not production generalization.",
        "score_semantics": "Monotone normalized Isolation Forest score; not failure probability. UI additionally smooths over time."}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result

if __name__ == "__main__":
    print(json.dumps(evaluate(joblib.load(MODEL_PATH)), ensure_ascii=False, indent=2))
