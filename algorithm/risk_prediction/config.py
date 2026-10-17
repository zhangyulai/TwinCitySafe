from pathlib import Path
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
FEATURE_VERSION = "m6-v1"
GENERATOR_VERSION = "m7-simulator-v2-startup"
MODEL_VERSION = "risk-xgb-v1"
SEED = 42
HORIZONS = (10, 20, 30)
TARGETS = tuple(f"{kind}_{h}m" for kind in ("water", "risk") for h in HORIZONS)
STATUS = {"offline": 0, "standby": 1, "running": 2, "warning": 3}
STAGE = {"normal": 0, "watch": 1, "warning": 2, "high": 3, "extreme": 4}
FAULT = {"normal": 0, "bearing_degradation": 1, "overheat": 2, "low_efficiency": 3}
PARAMETERS = dict(n_estimators=600, max_depth=6, learning_rate=.05, subsample=.85,
                  colsample_bytree=.85, objective="reg:squarederror", tree_method="hist",
                  n_jobs=4, random_state=SEED, reg_lambda=2.0)
