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

import asyncio
import logging
import os
from typing import Any, Awaitable, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from rigctl_client import (
    DEFAULT_HOST,
    DEFAULT_MAX_PTT_SECONDS,
    DEFAULT_PORT,
    RigctlClient,
    RigctlError,
)

logger = logging.getLogger("rigctl_mcp.ptt")

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


# set_ptt keys a real transmitter, so it only exists at all if the server was
# explicitly started with --allow-ptt / RIGCTL_ALLOW_PTT -- an MCP client
# never even sees it as a callable tool otherwise. This has to be decided at
# import time (tool registration happens via the decorator below), which is
# why __main__.py sets the env var before importing this module, same
# ordering constraint as RIGCTLD_HOST/RIGCTLD_PORT.
_ALLOW_PTT = os.environ.get("RIGCTL_ALLOW_PTT", "").strip().lower() in ("1", "true", "yes")
_MAX_PTT_SECONDS = float(os.environ.get("RIGCTL_MAX_PTT_SECONDS", DEFAULT_MAX_PTT_SECONDS))

_ptt_watchdog: asyncio.Task[None] | None = None


async def _ptt_watchdog_fire() -> None:
    await asyncio.sleep(_MAX_PTT_SECONDS)
    logger.warning("PTT watchdog fired after %.0fs -- auto-unkeying", _MAX_PTT_SECONDS)
    try:
        await _get_client().set_ptt(False)
    except RigctlError:
        logger.exception("PTT watchdog's auto-unkey call itself failed")


if _ALLOW_PTT:

    @mcp.tool()
    async def set_ptt(on: bool, confirm: str | None = None) -> dict[str, Any]:
        """Key (on=True) or unkey (on=False) the transmitter. Keying ON
        requires confirm="transmit" exactly -- unkeying never needs it, since
        that direction is always safe. A server-side watchdog automatically
        unkeys after the configured max duration (see --max-ptt-seconds)
        even if set_ptt(False) never arrives, so a stuck-on key can't outlast
        it regardless of what the caller does."""
        global _ptt_watchdog
        if on and confirm != "transmit":
            raise ToolError('set_ptt(on=True) requires confirm="transmit"')

        logger.info("set_ptt(on=%s) requested", on)
        await _call(_get_client().set_ptt(on))

        if _ptt_watchdog is not None:
            _ptt_watchdog.cancel()
            _ptt_watchdog = None
        if on:
            _ptt_watchdog = asyncio.create_task(_ptt_watchdog_fire())

        return {"status": "ok", "ptt": on}
