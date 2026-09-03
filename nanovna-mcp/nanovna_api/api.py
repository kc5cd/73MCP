"""FastAPI app: the REST + WebSocket surface described in README.md's
"Daemon API" section. This is the only thing a future MCP server and
webapp are meant to talk to -- neither should import device.py/sweep.py
directly, since only this process may hold the serial port.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from . import sweep
from .device import NanovnaDevice, NotConnectedError, discover_ports

app = FastAPI(title="nanovna-api", version="0.1.0")

# One device, one lock: every request that touches the serial port waits
# its turn. A NanoVNA's classic ASCII protocol is fundamentally
# request/reply/single-session anyway (see sweep.py) -- there's no
# meaningful way to interleave two callers' commands even if we wanted to.
_device = NanovnaDevice()
_lock = asyncio.Lock()


class ConnectRequest(BaseModel):
    port: str


class SweepRequest(BaseModel):
    start_hz: int
    stop_hz: int
    points: int


@app.get("/devices")
async def list_devices() -> dict[str, Any]:
    ports = await asyncio.to_thread(discover_ports)
    return {"devices": ports}


@app.get("/status")
async def status() -> dict[str, Any]:
    return {"connected": _device.is_connected, "port": _device.port}


@app.post("/connect")
async def connect(req: ConnectRequest) -> dict[str, Any]:
    async with _lock:
        try:
            await asyncio.to_thread(_device.connect, req.port)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"connected": True, "port": _device.port}


@app.post("/disconnect")
async def disconnect() -> dict[str, Any]:
    async with _lock:
        await asyncio.to_thread(_device.disconnect)
    return {"connected": False}


@app.get("/info")
async def info() -> dict[str, Any]:
    async with _lock:
        try:
            text = await asyncio.to_thread(sweep.get_device_info, _device)
        except NotConnectedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"info": text}


@app.post("/sweep")
async def do_sweep(req: SweepRequest) -> dict[str, Any]:
    async with _lock:
        try:
            points = await asyncio.to_thread(
                lambda: [p.to_dict() for p in sweep.run_sweep(_device, req.start_hz, req.stop_hz, req.points)]
            )
        except NotConnectedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"points": points}


async def _stream_sweep_points(start_hz: int, stop_hz: int, points: int):
    """Bridge sweep.run_sweep()'s synchronous generator (running in a
    background thread, since pyserial is blocking) onto an async
    iterator the WebSocket handler can await over point-by-point.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def worker() -> None:
        try:
            for point in sweep.run_sweep(_device, start_hz, stop_hz, points):
                loop.call_soon_threadsafe(queue.put_nowait, point)
        except Exception as exc:  # noqa: BLE001 -- forwarded to the client, not swallowed
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        item = await queue.get()
        if item is sentinel:
            return
        if isinstance(item, Exception):
            raise item
        yield item


@app.websocket("/sweep/stream")
async def sweep_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        req = await websocket.receive_json()
        start_hz, stop_hz, points = int(req["start_hz"]), int(req["stop_hz"]), int(req["points"])
    except (KeyError, ValueError, TypeError) as exc:
        await websocket.send_json({"error": f"invalid sweep request: {exc}"})
        await websocket.close()
        return

    async with _lock:
        try:
            async for point in _stream_sweep_points(start_hz, stop_hz, points):
                await websocket.send_json(point.to_dict())
            await websocket.send_json({"done": True})
        except NotConnectedError as exc:
            await websocket.send_json({"error": str(exc)})
        except WebSocketDisconnect:
            return  # client already gone -- closing again below would raise
        finally:
            try:
                await websocket.close()
            except RuntimeError:
                pass  # already closed (e.g. the client-disconnect path above)
