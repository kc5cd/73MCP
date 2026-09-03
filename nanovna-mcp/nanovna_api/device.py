"""Serial connection management for a NanoVNA: discovery and the
blocking line-based read/write primitives sweep.py builds on.

All I/O here is synchronous (pyserial has no native async API) -- api.py
is responsible for running it off the asyncio event loop thread via
asyncio.to_thread().
"""

from __future__ import annotations

import serial
from serial.tools import list_ports

from . import protocol

DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT_S = 2.0


class NotConnectedError(RuntimeError):
    pass


def discover_ports() -> list[str]:
    """List serial port device names matching the NanoVNA's VID/PID.

    Not yet connected to any of them -- just enumeration, mirroring the
    "found but not opened" step of this repo's own device search
    (analyzer/nanovna_analyzer.cpp).
    """
    matches = []
    for port in list_ports.comports():
        if port.vid == protocol.USB_VID and port.pid == protocol.USB_PID:
            matches.append(port.device)
    return matches


class NanovnaDevice:
    """Owns (at most) one open serial connection to a NanoVNA.

    One instance is shared by the whole daemon process (see api.py) --
    only one process may hold the port, so there is deliberately no
    connection pooling or multi-instance support here.
    """

    def __init__(self) -> None:
        self._serial: serial.Serial | None = None
        self._port: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def port(self) -> str | None:
        return self._port

    def connect(self, port: str) -> None:
        if self.is_connected:
            self.disconnect()
        self._serial = serial.Serial(port, DEFAULT_BAUDRATE, timeout=DEFAULT_TIMEOUT_S)
        self._port = port

    def disconnect(self) -> None:
        if self._serial is not None:
            self._serial.close()
        self._serial = None
        self._port = None

    def send_command(self, cmd: str) -> None:
        if not self.is_connected:
            raise NotConnectedError("not connected to a NanoVNA")
        self._serial.write(cmd.encode("ascii"))

    def read_line(self) -> str:
        """Block for a single line (blank on read timeout)."""
        if not self.is_connected:
            raise NotConnectedError("not connected to a NanoVNA")
        raw = self._serial.readline()
        return raw.decode("ascii", errors="replace").strip()

    def read_until_prompt(self) -> list[str]:
        """Read lines until one containing the prompt marker; return the
        lines seen before it (the prompt line itself is discarded).

        Mirrors this repo's own C++ parser: every command's reply ends
        this way, and no fixed line count is ever assumed. A read
        timeout (empty line from read_line()) also ends the loop
        defensively, so a device that stops responding mid-reply doesn't
        hang the caller forever.
        """
        lines: list[str] = []
        while True:
            line = self.read_line()
            if protocol.PROMPT_MARKER in line:
                return lines
            if line == "":
                return lines
            lines.append(line)
