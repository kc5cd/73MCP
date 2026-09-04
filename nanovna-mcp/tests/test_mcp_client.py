"""Unit tests for nanovna_mcp.client -- no daemon or hardware required.

Each test swaps NanovnaDaemonClient's transport for an httpx.MockTransport,
so these exercise the client's request shapes and error translation without
any network I/O.
"""

import json

import httpx
import pytest

from nanovna_mcp.client import DaemonError, NanovnaDaemonClient


def _client(handler):
    return NanovnaDaemonClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_list_devices_returns_ports():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/devices"
        return httpx.Response(200, json={"devices": ["COM20"]})

    assert await _client(handler).list_devices() == ["COM20"]


@pytest.mark.asyncio
async def test_get_status():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/status"
        return httpx.Response(200, json={"connected": True, "port": "COM20"})

    assert await _client(handler).get_status() == {"connected": True, "port": "COM20"}


@pytest.mark.asyncio
async def test_connect_sends_port_in_body():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/connect"
        assert json.loads(request.content) == {"port": "COM20"}
        return httpx.Response(200, json={"connected": True, "port": "COM20"})

    assert await _client(handler).connect("COM20") == {"connected": True, "port": "COM20"}


@pytest.mark.asyncio
async def test_disconnect():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/disconnect"
        return httpx.Response(200, json={"connected": False})

    assert await _client(handler).disconnect() == {"connected": False}


@pytest.mark.asyncio
async def test_get_info():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/info"
        return httpx.Response(200, json={"info": "NanoVNA-H 1.0.1"})

    assert await _client(handler).get_info() == "NanoVNA-H 1.0.1"


@pytest.mark.asyncio
async def test_sweep_sends_params_and_returns_points():
    point = {
        "freq_hz": 468000000.0,
        "s11": {"re": 0.02, "im": 0.01},
        "impedance": {"r": 48.1, "x": 1.2},
        "swr": 1.05,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sweep"
        assert json.loads(request.content) == {"start_hz": 420000000, "stop_hz": 540000000, "points": 101}
        return httpx.Response(200, json={"points": [point]})

    assert await _client(handler).sweep(420000000, 540000000, 101) == [point]


@pytest.mark.asyncio
async def test_error_response_raises_daemonerror_with_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "not connected to a NanoVNA"})

    with pytest.raises(DaemonError, match="not connected to a NanoVNA"):
        await _client(handler).get_info()


@pytest.mark.asyncio
async def test_error_response_without_json_body_falls_back_to_status_and_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal server error")

    with pytest.raises(DaemonError, match="500"):
        await _client(handler).get_status()


@pytest.mark.asyncio
async def test_connection_error_raises_daemonerror():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(DaemonError, match="could not reach the daemon"):
        await _client(handler).list_devices()
