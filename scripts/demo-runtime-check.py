#!/usr/bin/env python3
"""Read-only startup readiness, including real same-origin WS handshake and initial data."""
import argparse
import asyncio
import json
import socket
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import get_settings


def urls():
    settings = get_settings()
    host = "127.0.0.1" if settings.backend_host in ("0.0.0.0", "::") else settings.backend_host
    return f"http://{host}:{settings.backend_port}", f"http://127.0.0.1:{settings.frontend_port}"


def get(url):
    with urlopen(url, timeout=3) as response:
        return response.read()


async def check_socket(frontend):
    from websockets.asyncio.client import connect
    async with connect(frontend.replace("http://", "ws://") + "/ws/realtime", open_timeout=4, close_timeout=1) as ws:
        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
        if message.get("type") != "REALTIME_STATE":
            raise ValueError("Unexpected realtime message")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ports", action="store_true")
    parser.add_argument("--check-ports", action="store_true")
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    settings = get_settings()
    backend, frontend = urls()
    if args.ports:
        print(settings.frontend_port)
        return 0
    if args.check_ports:
        for host, port, name in ((settings.backend_host, settings.backend_port, "Backend"), ("127.0.0.1", settings.frontend_port, "Frontend")):
            with socket.socket() as probe:
                # Match server bind semantics: TIME_WAIT from a stopped server is reusable.
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind((host, port))
                except OSError:
                    print(f"{name} port {port} is already in use. Stop the existing dev/demo process before starting.", file=sys.stderr)
                    return 1
        return 0
    deadline = time.monotonic() + args.timeout
    failed = "Backend"
    while time.monotonic() < deadline:
        try:
            failed = "Backend"
            get(backend + "/api/v1/health")
            failed = "Frontend"
            get(frontend + "/dashboard?demo=1")
            failed = "Readiness"
            readiness = json.loads(get(frontend + "/api/v1/system/readiness"))
            unavailable = [name for name in ("backend", "database", "websocket", "pipeline_graph") if not readiness[name]["available"]]
            if unavailable:
                failed = ", ".join(unavailable)
                raise ValueError("Core components unavailable")
            failed = "WebSocket"
            asyncio.run(check_socket(frontend))
            print("Database Ready")
            print("Models Ready" if readiness["anomaly_model"]["available"] and readiness["risk_model"]["available"] else "Models Degraded — physical simulation remains available")
            print("Backend Ready")
            print("Frontend Ready")
            print("WebSocket Ready (real handshake and initial message verified)")
            print(f"TwinCitySafe Demo Ready\nFrontend: {frontend}/dashboard?demo=1\nBackend: {backend}\nReadiness: {'READY' if readiness['ready'] else 'DEGRADED'}")
            return 0
        except (OSError, URLError, ValueError, TimeoutError, KeyError):
            time.sleep(.5)
        except Exception:
            time.sleep(.5)
    print(f"Startup failed: {failed} did not become ready. Check the named service logs.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
