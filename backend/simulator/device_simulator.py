from math import sin

from app.schemas.realtime import DeviceState, DeviceStatus
from simulator.config import relax, FAULT_TARGETS, FAULT_RAMP_SECONDS, DEVICE_SETTLING_SECONDS
from app.schemas.operation import FaultProfile


class DeviceSimulator:
    def __init__(self) -> None:
        self.commanded: dict[str, DeviceStatus] = {}
        self.fault_age: dict[str, float] = {}
        self.settling: dict[str, float] = {}

    def reset(self) -> None:
        self.commanded.clear()
        self.fault_age.clear()
        self.settling.clear()

    def set_fault(self, devices: list[DeviceState], device_id: str, fault: FaultProfile) -> None:
        device = next((item for item in devices if item.id == device_id), None)
        if device is None:
            raise KeyError(device_id)
        if device.fault != fault:
            self.fault_age[device_id] = 0
        device.fault = fault

    def set_state(self, devices: list[DeviceState], device_id: str, status: DeviceStatus) -> None:
        device = next((item for item in devices if item.id == device_id), None)
        if device is None:
            raise KeyError(device_id)
        previous = self.commanded.get(device_id, device.status)
        if status == "running" and previous != "running":
            self.settling[device_id] = DEVICE_SETTLING_SECONDS
            device.startup_progress = 0
        elif status != "running":
            self.settling.pop(device_id, None)
        self.commanded[device_id] = status
        device.status = status

    def tick(self, devices: list[DeviceState], ambient: float, time: float, dt: float) -> None:
        for index, device in enumerate(devices):
            self.settling[device.id] = max(0, self.settling.get(device.id, 0) - dt)
            device.startup_progress = 1 - self.settling[device.id] / DEVICE_SETTLING_SECONDS
            phase = time / 29 + index * 0.7
            command = self.commanded.setdefault(device.id, device.status)
            if command == "running":
                targets = (42 + 0.6 * sin(phase), 1.8 + 0.06 * sin(phase * 1.3),
                           18 + 0.18 * sin(phase * 0.8), 1450 + 9 * sin(phase),
                           96 + 0.25 * sin(phase * 0.6), 94 + 0.12 * sin(phase * 0.4))
            elif command == "warning":
                # A manually selected demonstration state, not anomaly detection.
                targets = (51 + 0.4 * sin(phase), 3.1 + 0.08 * sin(phase),
                           22 + 0.2 * sin(phase), 1280 + 8 * sin(phase), 78, 75)
            elif command == "standby":
                targets = (ambient + 2 + 0.15 * sin(phase), 0.2, 0, 0, 100, 95)
            else:
                targets = (ambient, 0, 0, 0, 0, device.health)
            if command in ("running", "warning"):
                device.runtime_hours += dt / 3600
                if device.fault != "normal":
                    age = self.fault_age.get(device.id, 0) + dt
                    self.fault_age[device.id] = age
                    fraction = min(1.0, age / FAULT_RAMP_SECONDS)
                    fault_targets = FAULT_TARGETS[device.fault]
                    targets = tuple(base + (bad - base) * fraction for base, bad in zip(targets[:5], fault_targets)) + (targets[5],)
            temperature, vibration, current, rpm, efficiency, health = targets
            device.temperature = relax(device.temperature, temperature, dt, 20)
            device.vibration = relax(device.vibration, vibration, dt, 8)
            device.current = relax(device.current, current, dt, 8)
            device.rpm = relax(device.rpm, rpm, dt, 8)
            device.efficiency = relax(device.efficiency, efficiency, dt, 14)
            if device.analysis is None:  # Once attached, the M3 health service owns this value.
                device.health = relax(device.health, health, dt, 30)

    @staticmethod
    def drainage_capacity(devices: list[DeviceState]) -> float:
        """Effective pump capacity: active status, current speed, and simulated efficiency."""
        return sum((device.rpm / 1450) * (device.efficiency / 96)
                   for device in devices if device.status in ("running", "warning"))
