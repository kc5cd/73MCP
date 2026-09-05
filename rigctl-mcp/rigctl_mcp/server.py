"""MCP server exposing an already-running rigctld's ERP interface as tools.

Each tool is a thin wrapper around RigctlClient -- this module holds no
Hamlib-specific logic of its own, only MCP glue. There's no daemon of our
own to start: rigctld already fills that role, so the client connects
directly to it (lazily, on first tool call).

MCPServer only forwards a ToolError's own message to the client; any other
exception becomes a generic "Error executing tool <name>" (same behavior
worked around in nanovna-mcp's and wsjtx-mcp's server.py). RigctlError
messages (e.g. "set_freq failed: RPRT -1") are exactly what a caller needs
to see, so _call() below re-raises them as ToolError.
"""

from __future__ import annotations

import os
from typing import Any, Awaitable, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from rigctl_client import DEFAULT_HOST, DEFAULT_PORT, RigctlClient, RigctlError

mcp = MCPServer("rigctl-mcp")

_client: RigctlClient | None = None

_T = TypeVar("_T")


def _get_client() -> RigctlClient:
    global _client
    if _client is None:
        host = os.environ.get("RIGCTLD_HOST", DEFAULT_HOST)
        port = int(os.environ.get("RIGCTLD_PORT", DEFAULT_PORT))
        _client = RigctlClient(host, port)
    return _client


async def _call(awaitable: Awaitable[_T]) -> _T:
    try:
        return await awaitable
    except RigctlError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def get_status() -> dict[str, Any]:
    """Current rig state: dial frequency (Hz), mode, passband (Hz), VFO, and
    PTT state (0=RX, 1=TX, 2=TX mic, 3=TX data)."""
    return await _call(_get_client().get_status())


@mcp.tool()
async def set_frequency(hz: int) -> dict[str, str]:
    """Set the rig's dial frequency in Hz on the current VFO."""
    await _call(_get_client().set_frequency(hz))
    return {"status": "ok"}


@mcp.tool()
async def set_mode(mode: str, passband_hz: int | None = None) -> dict[str, str]:
    """Set the rig's mode (e.g. USB, LSB, CW, FM) and optionally its
    passband width in Hz (0 or omitted picks the rig's default for the
    mode)."""
    await _call(_get_client().set_mode(mode, passband_hz))
    return {"status": "ok"}
