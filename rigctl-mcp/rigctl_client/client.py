"""Persistent asyncio TCP client for rigctld's Extended Response Protocol.

No daemon of our own here: rigctld already fills that role, so this client
connects directly to an already-running rigctld instance (default
127.0.0.1:4532), lazily on first command, and keeps the connection open
across calls.
"""

from __future__ import annotations

import asyncio

from .protocol import RPRT_RE, ERPResponse, build_command, parse_response

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4532

# Some digital-mode transmit cycles run long (WSPR ~110s) -- the watchdog
# default has to clear the longest common one comfortably, not just guard
# against a quick voice/CW over-key.
DEFAULT_MAX_PTT_SECONDS = 130.0


class RigctlError(Exception):
    """rigctld returned a nonzero RPRT for a command."""

    def __init__(self, command: str, rprt: int):
        self.command = command
        self.rprt = rprt
        super().__init__(f"{command} failed: RPRT {rprt}")


class RigctlClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
            self._reader = None
            self._writer = None

    async def _ensure_connected(self) -> None:
        if self._writer is None:
            self._reader, self._writer = await asyncio.open_connection(self._host, self._port)

    async def _send(self, cmd: str, *args: str) -> ERPResponse:
        async with self._lock:
            await self._ensure_connected()
            assert self._reader is not None and self._writer is not None
            self._writer.write(build_command(cmd, *args))
            await self._writer.drain()

            lines: list[str] = []
            while True:
                raw = await self._reader.readline()
                if not raw:
                    raise ConnectionError("rigctld closed the connection")
                line = raw.decode("ascii").rstrip("\r\n")
                lines.append(line)
                if RPRT_RE.match(line):
                    break

        resp = parse_response(lines)
        if resp.rprt != 0:
            raise RigctlError(resp.command, resp.rprt)
        return resp

    async def get_status(self) -> dict[str, object]:
        freq = await self._send(r"\get_freq")
        mode = await self._send(r"\get_mode")
        vfo = await self._send(r"\get_vfo")
        ptt = await self._send(r"\get_ptt")
        return {
            "frequency_hz": int(freq.values["Frequency"]),
            "mode": mode.values["Mode"],
            "passband_hz": int(mode.values["Passband"]),
            "vfo": vfo.values["VFO"],
            "ptt": int(ptt.values["PTT"]),
        }

    async def set_frequency(self, hz: int) -> None:
        await self._send("F", str(hz))

    async def set_mode(self, mode: str, passband_hz: int | None = None) -> None:
        await self._send("M", mode, str(passband_hz if passband_hz is not None else 0))

    async def set_ptt(self, on: bool) -> None:
        """Key (on=True) or unkey (on=False) the transmitter. No safeguards
        at this layer -- confirmation and the auto-unkey watchdog are
        rigctl_mcp's job, not this protocol client's."""
        await self._send("T", "1" if on else "0")
