import asyncio
import httpx
from app.main import app


def request(method: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, "/api/v1/health", **kwargs)
    return asyncio.run(send())


def test_health_contract():
    response = request("GET")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "TwinCitySafe", "version": "2.0"}


def test_local_frontend_cors():
    response = request("OPTIONS", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_origin_not_allowed():
    response = request("OPTIONS", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"})
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
