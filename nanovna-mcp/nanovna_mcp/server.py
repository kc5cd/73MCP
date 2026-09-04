"""MCP server exposing the nanovna-api daemon's REST endpoints as tools.

Each tool is a thin wrapper around NanovnaDaemonClient -- this module holds
no NanoVNA-specific logic of its own, only MCP glue.

MCPServer treats any exception it doesn't recognize as a server-side crash:
only its own message reaches the client for the deliberate `ToolError` it
defines (see mcp.server.mcpserver.tools.base.Tool.run's docstring); anything
else is replaced with a generic "Error executing tool <name>" so internal
exception text never leaks to a caller by default. DaemonError messages
(e.g. "not connected to a NanoVNA") are exactly what a caller needs to
correct its next call, so _call() below re-raises them as ToolError to keep
that text instead of losing it to the generic crash path.
"""

from __future__ import annotations

import os
from typing import Any, Awaitable, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .client import DEFAULT_DAEMON_URL, DaemonError, NanovnaDaemonClient

mcp = MCPServer("nanovna-mcp")

_client: NanovnaDaemonClient | None = None

_T = TypeVar("_T")


def _get_client() -> NanovnaDaemonClient:
    global _client
    if _client is None:
        _client = NanovnaDaemonClient(os.environ.get("NANOVNA_DAEMON_URL", DEFAULT_DAEMON_URL))
    return _client


async def _call(awaitable: Awaitable[_T]) -> _T:
    try:
        return await awaitable
    except DaemonError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def list_devices() -> list[str]:
    """List connected serial ports matching a NanoVNA's USB VID/PID (not yet connected)."""
    return await _call(_get_client().list_devices())


@mcp.tool()
async def status() -> dict[str, Any]:
    """Current daemon connection state: whether it's connected, and to which port."""
    return await _call(_get_client().get_status())


@mcp.tool()
async def connect(port: str) -> dict[str, Any]:
    """Open the daemon's serial connection to a NanoVNA on the given port
    (e.g. "COM20"). Use list_devices first to find candidate ports.
    """
    return await _call(_get_client().connect(port))


@mcp.tool()
async def disconnect() -> dict[str, Any]:
    """Close the daemon's serial connection, if one is open."""
    return await _call(_get_client().disconnect())


@mcp.tool()
async def get_info() -> str:
    """Firmware/version string reported by the connected NanoVNA."""
    return await _call(_get_client().get_info())


@mcp.tool()
async def sweep(start_hz: int, stop_hz: int, points: int) -> dict[str, Any]:
    """Run a frequency sweep on the connected NanoVNA and return the results.

    Returns every measured point (frequency, S11, S21 if available, derived
    impedance, and SWR) plus a `summary` with the point of lowest SWR --
    usually what matters most for a quick "how's my antenna" check.
    Requires a prior successful `connect`.
    """
    points_data = await _call(_get_client().sweep(start_hz, stop_hz, points))
    best = min(points_data, key=lambda p: p["swr"]) if points_data else None
    return {"points": points_data, "summary": {"min_swr_point": best}}
