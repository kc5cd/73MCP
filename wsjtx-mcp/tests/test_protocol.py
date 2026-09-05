"""Unit tests for wsjtx_udp.protocol -- no network required.

Each test hand-builds raw bytes matching WSJT-X's documented NetworkMessage
wire format and asserts decode() returns the expected dataclass, so a
regression in field order/types shows up immediately.
"""

import struct
from datetime import date, datetime, timezone

from wsjtx_udp.protocol import (
    Clear,
    Decode,
    Heartbeat,
    MessageType,
    QSOLogged,
    Status,
    decode,
)

MAGIC = 0xADBCCBDA


def _utf8(s: str) -> bytes:
    payload = s.encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def _header(msg_type: int, id_: str = "WSJT-X") -> bytes:
    return struct.pack(">III", MAGIC, 3, msg_type) + _utf8(id_)


def _qdatetime(dt: datetime) -> bytes:
    ordinal = dt.date().toordinal()
    julian_day = ordinal + 1721425
    ms = ((dt.hour * 60 + dt.minute) * 60 + dt.second) * 1000 + dt.microsecond // 1000
    spec = 1 if dt.tzinfo is not None else 0  # 1 = Qt::UTC, 0 = Qt::LocalTime
    return struct.pack(">qIb", julian_day, ms, spec)


def test_magic_number_mismatch_returns_none():
    assert decode(struct.pack(">III", 0xDEADBEEF, 3, 0) + _utf8("x")) is None


def test_unrecognized_type_returns_none():
    assert decode(_header(99)) is None


def test_truncated_payload_returns_none():
    assert decode(_header(MessageType.STATUS) + struct.pack(">I", 14313000)) is None


def test_heartbeat():
    body = _header(MessageType.HEARTBEAT) + struct.pack(">I", 3) + _utf8("2.6.0") + _utf8("abcdef1")
    msg = decode(body)
    assert msg == Heartbeat(id="WSJT-X", max_schema=3, version="2.6.0", revision="abcdef1")


def test_status():
    body = (
        _header(MessageType.STATUS)
        + struct.pack(">Q", 14_074_000)
        + _utf8("FT8")
        + _utf8("K1ABC")
        + _utf8("+03")
        + _utf8("FT8")
        + struct.pack(">???", True, False, True)
        + struct.pack(">ii", 1500, 1500)
        + _utf8("KC5CD")
        + _utf8("EM12")
        + _utf8("FN31")
        + struct.pack(">?", False)
        + _utf8("")
        + struct.pack(">?", False)
        + struct.pack(">B", 0)
    )
    msg = decode(body)
    assert msg == Status(
        id="WSJT-X",
        dial_frequency_hz=14_074_000,
        mode="FT8",
        dx_call="K1ABC",
        report="+03",
        tx_mode="FT8",
        tx_enabled=True,
        transmitting=False,
        decoding=True,
        rx_df=1500,
        tx_df=1500,
        de_call="KC5CD",
        de_grid="EM12",
        dx_grid="FN31",
        tx_watchdog=False,
        submode="",
        fast_mode=False,
        special_op_mode=0,
    )


def test_decode_message():
    body = (
        _header(MessageType.DECODE)
        + struct.pack(">?", True)
        + struct.pack(">I", 12 * 3_600_000 + 34 * 60_000 + 56_000)
        + struct.pack(">i", -12)
        + struct.pack(">d", 0.2)
        + struct.pack(">I", 1500)
        + _utf8("FT8")
        + _utf8("CQ K1ABC FN31")
        + struct.pack(">??", False, False)
    )
    msg = decode(body)
    assert msg == Decode(
        id="WSJT-X",
        new=True,
        time_ms=12 * 3_600_000 + 34 * 60_000 + 56_000,
        snr=-12,
        delta_time_s=0.2,
        delta_frequency_hz=1500,
        mode="FT8",
        message="CQ K1ABC FN31",
        low_confidence=False,
        off_air=False,
    )


def test_clear_with_window_byte():
    body = _header(MessageType.CLEAR) + struct.pack(">B", 1)
    assert decode(body) == Clear(id="WSJT-X", window=1)


def test_clear_without_window_byte_defaults_zero():
    body = _header(MessageType.CLEAR)
    assert decode(body) == Clear(id="WSJT-X", window=0)


def test_qso_logged():
    off = datetime(2026, 9, 3, 18, 4, 30, tzinfo=timezone.utc)
    on = datetime(2026, 9, 3, 18, 0, 0, tzinfo=timezone.utc)
    body = (
        _header(MessageType.QSO_LOGGED)
        + _qdatetime(off)
        + _utf8("K1ABC")
        + _utf8("FN31")
        + struct.pack(">Q", 14_074_000)
        + _utf8("FT8")
        + _utf8("+03")
        + _utf8("-05")
        + _utf8("")
        + _utf8("")
        + _utf8("")
        + _qdatetime(on)
        + _utf8("KC5CD")
        + _utf8("KC5CD")
        + _utf8("EM12")
        + _utf8("")
        + _utf8("")
    )
    msg = decode(body)
    assert msg == QSOLogged(
        id="WSJT-X",
        date_time_off=off,
        dx_call="K1ABC",
        dx_grid="FN31",
        tx_frequency_hz=14_074_000,
        mode="FT8",
        report_sent="+03",
        report_received="-05",
        tx_power="",
        comments="",
        name="",
        date_time_on=on,
        operator_call="KC5CD",
        my_call="KC5CD",
        my_grid="EM12",
        exchange_sent="",
        exchange_received="",
    )
    assert msg.date_time_off.date() == date(2026, 9, 3)
