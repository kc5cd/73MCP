"""Decode primitives for WSJT-X's `NetworkMessage` UDP protocol.

Field order/types per message type are taken from WSJT-X's own
`Network/NetworkMessage.hpp` doc comments (schema 2/3, i.e. Qt 5.2+ builds --
the only schemas in practical use). This module only decodes; nothing is
sent back to WSJT-X yet (see wsjtx-mcp/PLAN.md's "Not in this pass").
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import IntEnum
from typing import Callable, Union

MAGIC_NUMBER = 0xADBCCBDA

# Qt's QDate::toJulianDay() epoch vs. Python's date.toordinal() epoch
# (proleptic Gregorian day 1 = 0001-01-01): JD(1970-01-01) - ordinal(1970-01-01)
# = 2440588 - 719163 = 1721425.
_JULIAN_DAY_ORDINAL_OFFSET = 1721425


class MessageType(IntEnum):
    HEARTBEAT = 0
    STATUS = 1
    DECODE = 2
    CLEAR = 3
    QSO_LOGGED = 5


class ProtocolError(ValueError):
    """Internal: datagram too short or malformed. decode() catches this and
    returns None instead -- a stray/foreign packet on the port must not
    crash the listener.
    """


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def _take(self, size: int) -> bytes:
        end = self._pos + size
        if end > len(self._data):
            raise ProtocolError(
                f"expected {size} bytes at offset {self._pos}, "
                f"only {len(self._data) - self._pos} available"
            )
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    def remaining(self) -> int:
        return len(self._data) - self._pos

    def uint8(self) -> int:
        return struct.unpack(">B", self._take(1))[0]

    def int8(self) -> int:
        return struct.unpack(">b", self._take(1))[0]

    def uint32(self) -> int:
        return struct.unpack(">I", self._take(4))[0]

    def int32(self) -> int:
        return struct.unpack(">i", self._take(4))[0]

    def uint64(self) -> int:
        return struct.unpack(">Q", self._take(8))[0]

    def int64(self) -> int:
        return struct.unpack(">q", self._take(8))[0]

    def double(self) -> float:
        return struct.unpack(">d", self._take(8))[0]

    def boolean(self) -> bool:
        return self.uint8() != 0

    def utf8(self) -> str:
        # Qt's QDataStream length-prefixes a null string as 0xFFFFFFFF (no
        # payload bytes follow) -- WSJT-X uses this for unset string fields.
        length = self.uint32()
        if length == 0xFFFFFFFF:
            return ""
        return self._take(length).decode("utf-8")

    def qtime_ms(self) -> int:
        """Milliseconds since midnight -- QTime's own QDataStream wire format."""
        return self.uint32()

    def qdatetime(self) -> datetime:
        jd = self.int64()
        ms = self.uint32()
        spec = self.int8()
        d = date.fromordinal(jd - _JULIAN_DAY_ORDINAL_OFFSET)
        t = time(ms // 3_600_000, (ms // 60_000) % 60, (ms // 1_000) % 60, (ms % 1_000) * 1_000)
        if spec == 1:  # Qt::UTC
            tz = timezone.utc
        elif spec == 2:  # Qt::OffsetFromUTC
            tz = timezone(timedelta(seconds=self.int32()))
        elif spec == 0:  # Qt::LocalTime
            tz = None
        else:  # Qt::TimeZone (3) -- carries a QTimeZone id string, not implemented
            raise ProtocolError(f"unsupported QDateTime timeSpec {spec} (QTimeZone not implemented)")
        return datetime.combine(d, t, tzinfo=tz)


@dataclass(frozen=True)
class Heartbeat:
    id: str
    max_schema: int
    version: str
    revision: str


@dataclass(frozen=True)
class Status:
    id: str
    dial_frequency_hz: int
    mode: str
    dx_call: str
    report: str
    tx_mode: str
    tx_enabled: bool
    transmitting: bool
    decoding: bool
    rx_df: int
    tx_df: int
    de_call: str
    de_grid: str
    dx_grid: str
    tx_watchdog: bool
    submode: str
    fast_mode: bool
    special_op_mode: int


@dataclass(frozen=True)
class Decode:
    id: str
    new: bool
    time_ms: int
    snr: int
    delta_time_s: float
    delta_frequency_hz: int
    mode: str
    message: str
    low_confidence: bool
    off_air: bool


@dataclass(frozen=True)
class Clear:
    id: str
    window: int


@dataclass(frozen=True)
class QSOLogged:
    id: str
    date_time_off: datetime
    dx_call: str
    dx_grid: str
    tx_frequency_hz: int
    mode: str
    report_sent: str
    report_received: str
    tx_power: str
    comments: str
    name: str
    date_time_on: datetime
    operator_call: str
    my_call: str
    my_grid: str
    exchange_sent: str
    exchange_received: str


Message = Union[Heartbeat, Status, Decode, Clear, QSOLogged]


def _parse_heartbeat(r: _Reader, id_: str) -> Heartbeat:
    return Heartbeat(id=id_, max_schema=r.uint32(), version=r.utf8(), revision=r.utf8())


def _parse_status(r: _Reader, id_: str) -> Status:
    return Status(
        id=id_,
        dial_frequency_hz=r.uint64(),
        mode=r.utf8(),
        dx_call=r.utf8(),
        report=r.utf8(),
        tx_mode=r.utf8(),
        tx_enabled=r.boolean(),
        transmitting=r.boolean(),
        decoding=r.boolean(),
        rx_df=r.int32(),
        tx_df=r.int32(),
        de_call=r.utf8(),
        de_grid=r.utf8(),
        dx_grid=r.utf8(),
        tx_watchdog=r.boolean(),
        submode=r.utf8(),
        fast_mode=r.boolean(),
        special_op_mode=r.uint8(),
    )


def _parse_decode(r: _Reader, id_: str) -> Decode:
    return Decode(
        id=id_,
        new=r.boolean(),
        time_ms=r.qtime_ms(),
        snr=r.int32(),
        delta_time_s=r.double(),
        delta_frequency_hz=r.uint32(),
        mode=r.utf8(),
        message=r.utf8(),
        low_confidence=r.boolean(),
        off_air=r.boolean(),
    )


def _parse_clear(r: _Reader, id_: str) -> Clear:
    # "incoming only; default 0" per WSJT-X's own doc comment -- older
    # senders may end the datagram right after Id, with no window byte.
    window = r.uint8() if r.remaining() else 0
    return Clear(id=id_, window=window)


def _parse_qso_logged(r: _Reader, id_: str) -> QSOLogged:
    return QSOLogged(
        id=id_,
        date_time_off=r.qdatetime(),
        dx_call=r.utf8(),
        dx_grid=r.utf8(),
        tx_frequency_hz=r.uint64(),
        mode=r.utf8(),
        report_sent=r.utf8(),
        report_received=r.utf8(),
        tx_power=r.utf8(),
        comments=r.utf8(),
        name=r.utf8(),
        date_time_on=r.qdatetime(),
        operator_call=r.utf8(),
        my_call=r.utf8(),
        my_grid=r.utf8(),
        exchange_sent=r.utf8(),
        exchange_received=r.utf8(),
    )


_PARSERS: dict[int, Callable[[_Reader, str], Message]] = {
    MessageType.HEARTBEAT: _parse_heartbeat,
    MessageType.STATUS: _parse_status,
    MessageType.DECODE: _parse_decode,
    MessageType.CLEAR: _parse_clear,
    MessageType.QSO_LOGGED: _parse_qso_logged,
}


def decode(data: bytes) -> Message | None:
    """Decode one WSJT-X NetworkMessage UDP datagram.

    Returns None for a magic-number mismatch, an unrecognized message type,
    or a truncated/malformed payload -- a stray/foreign packet on the port
    must never crash the listener (see wsjtx_udp/listener.py).
    """
    try:
        r = _Reader(data)
        if r.uint32() != MAGIC_NUMBER:
            return None
        r.uint32()  # schema number -- field layout for the types we parse
        # hasn't changed across schema 2/3, so nothing branches on it.
        msg_type = r.uint32()
        id_ = r.utf8()
        parser = _PARSERS.get(msg_type)
        if parser is None:
            return None
        return parser(r, id_)
    except ProtocolError:
        return None
