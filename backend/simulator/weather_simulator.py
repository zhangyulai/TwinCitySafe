from math import sin

from app.schemas.realtime import WeatherCondition, WeatherState
from simulator.config import relax


class WeatherSimulator:
    def __init__(self):
        self.rainfall_target = None

    def set_weather(self, state: WeatherState, condition: WeatherCondition) -> None:
        # A command changes the target regime immediately; numeric telemetry eases toward it.
        state.condition = condition
        self.rainfall_target = None

    def tick(self, state: WeatherState, time: float, dt: float) -> None:
        temperature, humidity, wind = {
            "clear": (26.0, 58.0, 2.4), "cloudy": (24.0, 68.0, 3.0), "rain": (22.0, 85.0, 4.2),
        }[state.condition]
        rainfall = 14 + 0.35 * sin(time / 47) if state.condition == "rain" else 0
        if self.rainfall_target is not None: rainfall = self.rainfall_target
        state.rainfall = relax(state.rainfall, rainfall, dt, 12)
        state.temperature = relax(state.temperature, temperature + 0.25 * sin(time / 90), dt, 38)
        state.humidity = relax(state.humidity, humidity + 0.5 * sin(time / 70), dt, 26)
        state.wind_speed = relax(state.wind_speed, wind + 0.12 * sin(time / 31), dt, 18)
