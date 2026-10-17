from app.schemas.health import HealthResponse

def get_health() -> HealthResponse:
    """M0 service liveness, separate from equipment Health Index."""
    return HealthResponse()

from math import exp
from app.services.health_config import WEIGHTS, RANGES, HI_TAU_SECONDS

class HealthService:
    def __init__(self):
        self.values: dict[str, float] = {}

    @staticmethod
    def grade(value: float) -> str:
        return "优秀" if value >= 90 else "良好" if value >= 80 else "一般" if value >= 60 else "较差" if value >= 30 else "严重"

    def calculate(self, device, dt: float, operating: bool):
        if operating:
            deviations = {}
            for key, (normal, extreme) in RANGES.items():
                value = device.runtime_hours if key == "runtime" else getattr(device, key)
                deviations[key] = max(0, min(1, (value - normal) / (extreme - normal)))
            target = max(0, 100 - sum(WEIGHTS[key] * value * 100 for key, value in deviations.items()))
        else:
            target = self.values.get(device.id, device.health)
        previous = self.values.get(device.id, device.health)
        score = previous + (target - previous) * (1 - exp(-max(dt, 0) / HI_TAU_SECONDS))
        self.values[device.id] = score
        return score, target, self.grade(score)
