"""Real ASGI WebSocket execution without deprecated httpx TestClient integration."""
import asyncio
import json
from time import monotonic

from fastapi import WebSocketDisconnect

from app.main import app
from app.schemas.realtime import ParkRealtimeState
from app.websocket.manager import ConnectionManager


class ASGIWebSocket:
    def __init__(self, origin: str | None = "http://localhost:5173"):
        self.incoming: asyncio.Queue[dict] = asyncio.Queue()
        self.outgoing: asyncio.Queue[dict] = asyncio.Queue()
        self.scope = {"type": "websocket", "asgi": {"version": "3.0", "spec_version": "2.4"},
                      "http_version": "1.1", "scheme": "ws", "path": "/ws/realtime", "raw_path": b"/ws/realtime",
                      "root_path": "", "query_string": b"", "headers": [] if origin is None else [(b"origin", origin.encode())],
                      "client": ("127.0.0.1", 40000), "server": ("127.0.0.1", 8000), "subprotocols": []}
        self.task: asyncio.Task | None = None

    async def open(self) -> dict:
        self.task = asyncio.create_task(app(self.scope, self.incoming.get, self.outgoing.put))
        await self.incoming.put({"type": "websocket.connect"})
        return await asyncio.wait_for(self.outgoing.get(), timeout=0.5)

    async def message(self) -> dict:
        event = await asyncio.wait_for(self.outgoing.get(), timeout=1.8)
        assert event["type"] == "websocket.send"
        message = json.loads(event["text"])
        assert message["type"] == "REALTIME_STATE"
        assert message["timestamp"] == message["data"]["timestamp"]
        ParkRealtimeState.model_validate(message["data"])
        return message["data"]

    async def close(self) -> None:
        await self.incoming.put({"type": "websocket.disconnect", "code": 1000})
        if self.task:
            await asyncio.wait_for(self.task, timeout=1)


def test_websocket_initial_snapshot_cadence_speed_pause_and_multi_client(monkeypatch):
    monkeypatch.setattr("app.main.check_database", lambda: None)

    async def exercise():
        async with app.router.lifespan_context(app):
            service = app.state.realtime
            first, second = ASGIWebSocket(), ASGIWebSocket(origin=None)
            before = monotonic()
            assert (await first.open())["type"] == "websocket.accept"
            initial = await first.message()
            assert monotonic() - before < 0.5
            assert (await second.open())["type"] == "websocket.accept"
            assert (await second.message())["sessionId"] == initial["sessionId"]
            assert service.connections.connection_count == 2
            service.engine.set_speed(10)
            update = await first.message()
            assert update["simulationTime"] > 8
            same_update = await second.message()
            assert same_update == update
            received_at = monotonic()
            next_update = await first.message()
            assert 0.8 < monotonic() - received_at < 1.5
            assert 8 < next_update["simulationTime"] - update["simulationTime"] < 15
            await second.message()
            service.engine.stop()
            await first.close()
            assert service.connections.connection_count == 1
            paused = await second.message()
            assert not paused["running"]
            assert paused["simulationTime"] == next_update["simulationTime"]
            again = await second.message()
            for field in ("simulationTime", "weather", "environment", "devices", "pipelines", "system"):
                assert again[field] == paused[field]
            assert again["revision"] > paused["revision"]
            await second.close()
            assert service.connections.connection_count == 0
        await asyncio.sleep(0)
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("park-")]

    asyncio.run(exercise())


def test_websocket_rejects_unknown_browser_origin(monkeypatch):
    monkeypatch.setattr("app.main.check_database", lambda: None)

    async def exercise():
        async with app.router.lifespan_context(app):
            rejected = ASGIWebSocket("https://untrusted.example")
            event = await rejected.open()
            assert event["type"] == "websocket.close" and event["code"] == 1008
            await rejected.close()
            assert app.state.realtime.connections.connection_count == 0

    asyncio.run(exercise())


class FakeSocket:
    def __init__(self, behavior: str = "fast"):
        self.behavior = behavior
        self.sent: list[str] = []
        self.closed = False

    async def accept(self):
        pass

    async def send_text(self, message: str):
        if self.behavior == "slow":
            await asyncio.sleep(10)
        if self.behavior == "broken":
            raise WebSocketDisconnect(code=1006)
        self.sent.append(message)

    async def close(self, code: int):
        self.closed = True


def test_slow_and_broken_clients_do_not_block_fast_client():
    async def exercise():
        manager = ConnectionManager(send_timeout=0.05)
        fast, slow, broken = FakeSocket(), FakeSocket("slow"), FakeSocket("broken")
        await manager.connect(fast, "initial")
        await manager.connect(slow, "initial")
        await manager.connect(broken, "initial")
        await asyncio.sleep(0.01)
        for index in range(50):
            manager.broadcast(str(index))
        await asyncio.sleep(0.08)
        assert fast.sent == ["initial", "49"]
        assert manager.connection_count == 1
        assert slow.closed and broken.closed
        await manager.shutdown()
        assert manager.connection_count == 0 and not manager._writers

    asyncio.run(exercise())
