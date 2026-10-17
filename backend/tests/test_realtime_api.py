import asyncio

import httpx

from app.main import app
from app.schemas.realtime import ParkRealtimeState


def test_api_state_status_controls_and_validation(monkeypatch):
    monkeypatch.setattr("app.main.check_database", lambda: None)

    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/realtime/state")
                assert response.status_code == 200
                initial = ParkRealtimeState.model_validate(response.json())
                status = await client.get("/api/v1/simulation/status")
                assert status.json() == {"running": True, "speed": 1, "simulationTime": 0}
                stopped = await client.post("/api/v1/simulation/stop")
                assert not stopped.json()["running"]
                rain = await client.post("/api/v1/simulation/weather", json={"condition": "rain"})
                assert rain.json()["weather"]["condition"] == "rain"
                assert rain.json()["weather"]["rainfall"] == 0
                speed = await client.post("/api/v1/simulation/speed", json={"speed": 2.5})
                assert speed.json()["speed"] == 2.5
                device = await client.post("/api/v1/simulation/device/P03/state", json={"status": "warning"})
                assert device.json()["devices"][2]["status"] == "warning"
                assert device.json()["system"]["alerts"] == 1
                for path, body, code in [
                    ("weather", {"condition": "storm"}, 422),
                    ("weather", {"condition": "rain", "ignored": 1}, 422),
                    ("device/unknown/state", {"status": "running"}, 404),
                    ("device/P03/state", {"status": "broken"}, 422),
                    ("speed", {"speed": 0}, 422),
                    ("speed", {"speed": 11}, 422),
                    ("speed", {"speed": "2"}, 422),
                ]:
                    invalid = await client.post("/api/v1/simulation/" + path, json=body)
                    assert invalid.status_code == code
                reset = await client.post("/api/v1/simulation/reset")
                result = ParkRealtimeState.model_validate(reset.json())
                assert not result.running and result.speed == 1 and result.simulation_time == 0
                assert result.weather.condition == "clear" and result.devices[2].status == "running"
                assert result.session_id == initial.session_id and result.revision > initial.revision
                started = await client.post("/api/v1/simulation/start")
                assert started.json()["running"]
                twice = await client.post("/api/v1/simulation/start")
                assert twice.json() == started.json()
                assert app.state.realtime.engine._task is not None
        assert not hasattr(app.state, "realtime")

    asyncio.run(exercise())
