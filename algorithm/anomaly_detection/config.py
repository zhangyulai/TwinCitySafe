from pathlib import Path
FEATURES = ("temperature", "vibration", "current", "rpm", "efficiency")
MODEL_PATH = Path(__file__).resolve().parent / "models" / "pump_isolation_forest.joblib"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
SEED = 42
ESTIMATORS = 200
CONTAMINATION = 0.03
# Synthetic sensor variation around simulator-generated operating trajectories.
SENSOR_STD = (0.45, 0.07, 0.35, 15.0, 0.45)
