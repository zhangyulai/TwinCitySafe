from app.schemas.operation import DeviceAnalysis
from app.services.health_service import HealthService
from app.services.anomaly_service import AnomalyDetectionService
from app.services.maintenance_service import MaintenanceAdviceService
from app.services.alarm_service import AlarmService

class OperationService:
    def __init__(self, simulator, anomaly=None):
        self.simulator = simulator
        self.anomaly = anomaly or AnomalyDetectionService()
        self.health = HealthService()
        self.alarms = AlarmService()
        self.runtime = {"P01": 480.0, "P02": 600.0, "P03": 4138.0}
        self.last_time = -1.0

    def process(self, state, dt):
        if state.simulation_time < self.last_time:
            self.health.values.clear()
            self.anomaly.scores.clear()
            self.alarms.reset(state.timestamp)
        self.last_time = state.simulation_time
        for device in state.devices:
            if device.runtime_hours == 0:
                device.runtime_hours = self.runtime.get(device.id, 0)
            self.runtime[device.id] = device.runtime_hours
            commanded = self.simulator.commanded.setdefault(device.id, device.status)
            operating = commanded in ("running", "warning")
            settling = self.simulator.settling.get(device.id, 0) > 0
            health, target, grade = self.health.calculate(device, dt, operating and not settling)
            score, raw, level, evaluated = self.anomaly.predict(device, dt, operating, settling)
            contributions = self.anomaly.contributions(device, operating and not settling)
            explanation, advice = MaintenanceAdviceService.build(health, level, contributions, device.fault)
            alarm_id = self.alarms.update(device, score, level, state.timestamp)
            device.health = health
            device.status = "warning" if commanded == "running" and alarm_id else commanded
            device.analysis = DeviceAnalysis(health_score=health, health_target=target, health_grade=grade,
                model_available=self.anomaly.available, model_version=self.anomaly.artifact["version"] if self.anomaly.available else None,
                evaluated=evaluated, anomaly_score=score, raw_score=raw, is_anomaly=score is not None and score >= 0.6,
                level=level, contributions=contributions, explanation=explanation, advice=advice, active_alarm_id=alarm_id)
