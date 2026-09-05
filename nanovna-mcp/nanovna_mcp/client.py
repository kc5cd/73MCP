"""Async HTTP client for the nanovna-api daemon -- the only way nanovna_mcp
talks to a NanoVNA. Never imports nanovna_api.device/sweep directly: only the
daemon process may hold the serial port (see the repo's architecture doc).
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_DAEMON_URL = "http://localhost:8765"


class DaemonError(RuntimeError):
    """Raised for any daemon error response (400/409/422/...), carrying the
    daemon's own `detail` message so callers don't have to unwrap an
    httpx.HTTPStatusError to get something readable.
    """


class NanovnaDaemonClient:
    """Thin wrapper over the daemon's REST API (see nanovna-mcp/README.md's
    "Daemon API" section for the exact contract). One instance is meant to
    be shared for the life of the MCP server process.
    """

    def __init__(self, base_url: str = DEFAULT_DAEMON_URL, *, transport: httpx.BaseTransport | None = None) -> None:
        # `transport` is exposed so tests can swap in an httpx.MockTransport
        # instead of hitting a real daemon (see tests/test_mcp_client.py).
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = await self._client.request(method, path, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DaemonError(_extract_detail(exc.response)) from exc
        except httpx.RequestError as exc:
            raise DaemonError(f"could not reach the daemon at {self._client.base_url}: {exc}") from exc
        return resp.json()

    async def list_devices(self) -> list[str]:
        data = await self._request("GET", "/devices")
        return data["devices"]

    async def get_status(self) -> dict[str, Any]:
        return await self._request("GET", "/status")

    async def connect(self, port: str) -> dict[str, Any]:
        return await self._request("POST", "/connect", json={"port": port})

    async def disconnect(self) -> dict[str, Any]:
        return await self._request("POST", "/disconnect")

    async def get_info(self) -> str:
        data = await self._request("GET", "/info")
        return data["info"]

    async def sweep(self, start_hz: int, stop_hz: int, points: int) -> list[dict[str, Any]]:
        data = await self._request(
            "POST",
            "/sweep",
            json={"start_hz": start_hz, "stop_hz": stop_hz, "points": points},
        )
        return data["points"]


def _extract_detail(response: httpx.Response) -> str:
    """FastAPI's default error body is {"detail": "..."} for both raised
    HTTPExceptions (our 400/409s) and pydantic validation errors (422,
    where `detail` is a list of error objects instead of a string) -- stay
    permissive rather than assuming str.
    """
    try:
        body = response.json()
        detail = body.get("detail")
        if detail:
            return str(detail)
    except ValueError:
        pass
    return f"daemon returned {response.status_code}: {response.text}"
