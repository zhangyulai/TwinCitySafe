from math import expm1

TICK_INTERVAL = 1.0  # Wall-clock publication rate, independent of simulation speed.
MAX_SUBSTEP = 0.25  # Simulated seconds; keeps coupled models stable at 10x speed.
MAX_WALL_DELTA = 5.0  # Avoid a large catch-up jump after a stalled process.
BACKGROUND_ONLINE_DEVICES = 1265
MAX_WATER_LEVEL = 2.5


def relax(current: float, target: float, dt: float, tau: float) -> float:
    """Exact first-order response; the coefficient remains stable for any positive dt."""
    return current + (target - current) * -expm1(-dt / tau)

# M3 fault targets and time constants, shared by online simulation and dataset generation.
FAULT_TARGETS = {
    "bearing_degradation": (68.0, 5.2, 22.0, 1370.0, 76.0),
    "overheat": (76.0, 2.3, 21.0, 1410.0, 88.0),
    "low_efficiency": (49.0, 2.5, 24.0, 1220.0, 62.0),
}
FAULT_RAMP_SECONDS = 90.0

DEVICE_SETTLING_SECONDS = 60.0  # Normal pump start-up is outside the steady-running model domain.
