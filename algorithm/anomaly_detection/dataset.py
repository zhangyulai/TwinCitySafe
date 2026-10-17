"""Independent trajectories from the SAME online DeviceSimulator; no production data."""
import numpy as np
from app.schemas.realtime import DeviceState
from simulator.device_simulator import DeviceSimulator
from algorithm.anomaly_detection.config import SENSOR_STD
from algorithm.anomaly_detection.features import feature_row

def trajectory(seed: int, fault: str = "normal", seconds: int = 240):
    rng = np.random.default_rng(seed)
    simulator = DeviceSimulator()
    devices = [DeviceState(id=f"P0{i+1}", name="训练用模拟泵", status="running", temperature=42,
                vibration=1.8, current=18, rpm=1450, efficiency=96, health=94) for i in range(3)]
    offset = float(rng.uniform(0, 5000))
    for t in range(60):
        simulator.tick(devices, 26, offset + t, 1)
    if fault != "normal":
        for d in devices:
            simulator.set_fault(devices, d.id, fault)
    for t in range(seconds):
        simulator.tick(devices, 26, offset + 60 + t, 1)
        for device in devices:
            row = np.array(feature_row(device)) + rng.normal(0, SENSOR_STD)
            yield row, t + 1

def normal_dataset(count: int, seed: int):
    rows = []
    trajectory_index = 0
    while len(rows) < count:
        for row, _ in trajectory(seed + trajectory_index * 7919, seconds=180):
            rows.append(row)
            if len(rows) >= count:
                break
        trajectory_index += 1
    return np.asarray(rows)

def evaluation_dataset(seed: int):
    rows = list(normal_dataset(1800, seed))
    labels = [0] * len(rows)
    kinds = ["normal"] * len(rows)
    # Transition is reported separately, not silently labeled as healthy training data.
    for index, fault in enumerate(("bearing_degradation", "overheat", "low_efficiency")):
        for row, age in trajectory(seed + 100000 + index * 101, fault, seconds=240):
            if age >= 45:
                rows.append(row); labels.append(1); kinds.append(fault)
    return np.asarray(rows), np.asarray(labels), np.asarray(kinds)
