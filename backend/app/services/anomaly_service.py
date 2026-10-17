import logging
import sys
from math import exp
from pathlib import Path
import joblib
import numpy as np
from app.core.config import PROJECT_ROOT
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from algorithm.anomaly_detection.config import MODEL_PATH, FEATURES
from algorithm.anomaly_detection.features import feature_row, normalize_scores
from app.services.health_config import SCORE_TAU_SECONDS, LABELS, ATTENTION_SCORE, WARNING_SCORE, CRITICAL_SCORE, DEVIATION_BASELINES
from app.schemas.operation import Contribution

logger = logging.getLogger("uvicorn.error")

class AnomalyDetectionService:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.artifact = None
        self.scores: dict[str, float] = {}
        try:
            artifact = joblib.load(model_path)
            if tuple(artifact["features"]) != FEATURES or artifact["calibration"]["cutoff"] <= artifact["calibration"]["median"]:
                raise ValueError("Invalid model metadata")
            self.artifact = artifact
        except Exception as error:
            logger.warning("Anomaly model unavailable (%s); run algorithm/anomaly_detection/train.py. No training at startup.", type(error).__name__)

    @property
    def available(self):
        return self.artifact is not None

    @staticmethod
    def level(score: float) -> str:
        return "critical" if score >= CRITICAL_SCORE else "warning" if score >= WARNING_SCORE else "attention" if score >= ATTENTION_SCORE else "normal"

    def predict(self, device, dt: float, operating: bool, settling: bool = False):
        if not self.available:
            return None, None, "unavailable", False
        if not operating:
            self.scores.pop(device.id, None)
            return None, None, "not_applicable", False
        if settling:
            self.scores.pop(device.id, None)
            return None, None, "warming_up", False
        raw = float(-self.artifact["pipeline"].score_samples(np.asarray([feature_row(device)]))[0])
        target = float(normalize_scores([raw], self.artifact["calibration"])[0])
        previous = self.scores.get(device.id, target)
        score = previous + (target - previous) * (1 - exp(-max(dt, 0) / SCORE_TAU_SECONDS))
        self.scores[device.id] = score
        return score, raw, self.level(score), True

    @staticmethod
    def contributions(device, operating: bool):
        if not operating:
            return []
        # Observable deviations, NOT IF feature importance, SHAP or proven causal attribution.
        deviations = {key: max(0, (getattr(device, key)-baseline)/scale)
                      for key, (baseline, scale) in DEVIATION_BASELINES.items()}
        total = sum(deviations.values())
        return sorted([Contribution(feature=key, label=LABELS[key], deviation=value,
                       contribution=value/total if total else 0) for key, value in deviations.items()],
                      key=lambda item: item.contribution, reverse=True)
