# Central M3 demonstration thresholds; not manufacturer-certified limits.
WEIGHTS = {"temperature": 0.20, "vibration": 0.30, "current": 0.15, "efficiency": 0.25, "runtime": 0.10}
RANGES = {"temperature": (50, 80), "vibration": (2.8, 6.5), "current": (21.6, 30), "efficiency": (96, 60), "runtime": (0, 10000)}
LABELS = {"temperature": "温度", "vibration": "振动", "current": "电流", "efficiency": "效率", "rpm": "转速"}
HI_TAU_SECONDS = 20
SCORE_TAU_SECONDS = 12
WARNING_SCORE = 0.60
RESOLVE_SCORE = 0.35

ATTENTION_SCORE = 0.35
CRITICAL_SCORE = 0.80
DEVIATION_BASELINES = {"vibration": (2.1, 3.1), "temperature": (44, 24), "efficiency": (94, -20), "current": (19, 5), "rpm": (1400, -300)}
