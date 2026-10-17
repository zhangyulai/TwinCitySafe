"""Isolated per-client writers: a slow browser can never stall the engine or its peers."""
import asyncio
from contextlib import suppress
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect


@dataclass
class Client:
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    writer: asyncio.Task[None] | None = None


class ConnectionManager:
    def __init__(self, send_timeout: float = 2.0) -> None:
        self._clients: dict[WebSocket, Client] = {}
        self.send_timeout = send_timeout
        self._writers: set[asyncio.Task[None]] = set()

    @property
    def connection_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket, initial: str) -> None:
        await websocket.accept()
        client = Client()
        client.queue.put_nowait(initial)
        self._clients[websocket] = client
        client.writer = asyncio.create_task(self._write(websocket, client), name="park-websocket-writer")
        self._writers.add(client.writer)
        client.writer.add_done_callback(self._writers.discard)

    def broadcast(self, message: str) -> None:
        for client in tuple(self._clients.values()):
            if '"EMERGENCY_EVENT"' not in message and '"PIPELINE_LEAK_EVENT"' not in message:
                events=[]
                while not client.queue.empty():
                    old=client.queue.get_nowait()
                    if '"EMERGENCY_EVENT"' in old or '"PIPELINE_LEAK_EVENT"' in old:events.append(old)
                for old in events[-63:]:client.queue.put_nowait(old)
            if client.queue.full():client.queue.get_nowait()
            client.queue.put_nowait(message)

    async def _write(self, websocket: WebSocket, client: Client) -> None:
        try:
            while True:
                message = await client.queue.get()
                await asyncio.wait_for(websocket.send_text(message), timeout=self.send_timeout)
        except asyncio.CancelledError:
            raise
        except (WebSocketDisconnect, OSError, RuntimeError, TimeoutError):
            # Closed sockets, failed writes and slow connections are ordinary disconnects.
            pass
        finally:
            if self._clients.get(websocket) is client:
                self._clients.pop(websocket, None)
            await self._close(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        client = self._clients.pop(websocket, None)
        if client and client.writer:
            client.writer.cancel()
            with suppress(asyncio.CancelledError):
                await client.writer
        await self._close(websocket)

    @staticmethod
    async def _close(websocket: WebSocket) -> None:
        with suppress(WebSocketDisconnect, OSError, RuntimeError, TimeoutError):
            await asyncio.wait_for(websocket.close(code=1001), timeout=0.25)

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.disconnect(websocket) for websocket in tuple(self._clients)))
        if self._writers:
            await asyncio.gather(*tuple(self._writers), return_exceptions=True)
