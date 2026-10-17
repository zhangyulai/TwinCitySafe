from copy import deepcopy
from uuid import uuid4
from app.services.health_config import WARNING_SCORE, RESOLVE_SCORE

class AlarmService:
    def __init__(self):
        self.active: dict[str, dict] = {}
        self.pending: dict[str, dict] = {}

    def update(self, device, score, level, timestamp):
        current = self.active.get(device.id)
        if score is not None and score >= WARNING_SCORE:
            if current is None:
                current = dict(id=str(uuid4()), device_id=device.id, alarm_type="ANOMALY_WARNING", level=level,
                    message=f"{device.id} 仿真运行参数异常，建议检查", status="active", max_score=score,
                    created_at=timestamp, updated_at=timestamp, resolved_at=None)
                self.active[device.id] = current
            current.update(level=level, max_score=max(current["max_score"], score), updated_at=timestamp)
            self.pending[current["id"]] = deepcopy(current)
        elif current and score is not None and score < RESOLVE_SCORE:
            current.update(status="resolved", updated_at=timestamp, resolved_at=timestamp)
            self.pending[current["id"]] = deepcopy(current)
            del self.active[device.id]
        # An unavailable/idle model cannot prove recovery: retain existing active alarm.
        return self.active.get(device.id, {}).get("id")

    def reset(self, timestamp):
        for current in self.active.values():
            current.update(status="resolved", updated_at=timestamp, resolved_at=timestamp, message=current["message"] + "（仿真已重置）")
            self.pending[current["id"]] = deepcopy(current)
        self.active.clear()

    def acknowledge(self, written):
        for item in written:
            current = self.pending.get(item["id"])
            if current and current["updated_at"] == item["updated_at"]:
                self.pending.pop(item["id"], None)
