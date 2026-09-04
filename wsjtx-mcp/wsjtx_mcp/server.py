"""MCP server exposing WSJT-X's live UDP feed as tools.

Unlike nanovna-mcp, there's no daemon to talk to: this process binds the UDP
socket itself (via the `WSJTXListener` in `wsjtx_udp`) and starts listening
as part of the MCPServer's own lifespan, so the socket is open for exactly
as long as the MCP server is running.

MCPServer only forwards a ToolError's own message to the client; any other
exception becomes a generic "Error executing tool <name>" (same behavior
hit and worked around in nanovna-mcp's server.py). ListenerError messages
(e.g. "no WSJT-X instance has been heard from yet") are exactly what a
caller needs to try again correctly, so every tool below re-raises them as
ToolError.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from wsjtx_udp import ListenerError, QSOLogged, WSJTXListener

DEFAULT_UDP_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 2237

listener = WSJTXListener()


@asynccontextmanager
async def _lifespan(server: MCPServer) -> AsyncIterator[None]:
    host = os.environ.get("WSJTX_UDP_HOST", DEFAULT_UDP_HOST)
    port = int(os.environ.get("WSJTX_UDP_PORT", DEFAULT_UDP_PORT))
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(lambda: listener, local_addr=(host, port))
    try:
        yield
    finally:
        transport.close()


mcp = MCPServer("wsjtx-mcp", lifespan=_lifespan)


def _qso_to_dict(qso: QSOLogged) -> dict[str, Any]:
    d = asdict(qso)
    d["date_time_off"] = qso.date_time_off.isoformat()
    d["date_time_on"] = qso.date_time_on.isoformat()
    return d


@mcp.tool()
async def get_status(instance_id: str | None = None) -> dict[str, Any]:
    """Most recent Status from WSJT-X: dial frequency, mode, DX call/grid,
    Tx/Rx state. Pass instance_id only if more than one WSJT-X instance is
    running and has been heard from (the error message lists known ids).
    """
    try:
        return asdict(listener.get_status(instance_id))
    except ListenerError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def get_recent_decodes(instance_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Buffered decode lines (most recent first) from WSJT-X's Band Activity
    window since the server started or the buffer was last cleared.
    """
    try:
        decodes = listener.get_recent_decodes(instance_id, limit)
    except ListenerError as exc:
        raise ToolError(str(exc)) from exc
    return {"decodes": [asdict(d) for d in decodes]}


@mcp.tool()
async def get_recent_qsos(instance_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Buffered QSOs (most recent first) that WSJT-X has logged this session."""
    try:
        qsos = listener.get_recent_qsos(instance_id, limit)
    except ListenerError as exc:
        raise ToolError(str(exc)) from exc
    return {"qsos": [_qso_to_dict(q) for q in qsos]}
