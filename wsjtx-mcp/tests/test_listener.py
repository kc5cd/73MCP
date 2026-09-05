"""Unit tests for wsjtx_udp.listener -- no real socket or event loop needed;
datagram_received() is called directly with hand-built bytes, same technique
as test_protocol.py.
"""

import struct
from datetime import date

import pytest

from wsjtx_udp.listener import ListenerError, WSJTXListener
from wsjtx_udp.protocol import MessageType

MAGIC = 0xADBCCBDA
_ADDR = ("127.0.0.1", 2237)


def _utf8(s: str) -> bytes:
    payload = s.encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def _header(msg_type: int, id_: str = "WSJT-X") -> bytes:
    return struct.pack(">III", MAGIC, 3, msg_type) + _utf8(id_)


def _status_bytes(id_: str = "WSJT-X", dial_hz: int = 14_074_000) -> bytes:
    return (
        _header(MessageType.STATUS, id_)
        + struct.pack(">Q", dial_hz)
        + _utf8("FT8") + _utf8("K1ABC") + _utf8("+03") + _utf8("FT8")
        + struct.pack(">???", True, False, True)
        + struct.pack(">ii", 1500, 1500)
        + _utf8("KC5CD") + _utf8("EM12") + _utf8("FN31")
        + struct.pack(">?", False) + _utf8("") + struct.pack(">?", False)
        + struct.pack(">B", 0)
    )


def _decode_bytes(id_: str = "WSJT-X", message: str = "CQ K1ABC FN31") -> bytes:
    return (
        _header(MessageType.DECODE, id_)
        + struct.pack(">?", True)
        + struct.pack(">I", 0)
        + struct.pack(">i", -10)
        + struct.pack(">d", 0.1)
        + struct.pack(">I", 1500)
        + _utf8("FT8") + _utf8(message)
        + struct.pack(">??", False, False)
    )


def _qso_bytes(id_: str = "WSJT-X", dx_call: str = "K1ABC") -> bytes:
    dt_bytes = struct.pack(">qIb", date.today().toordinal() + 1721425, 0, 1)
    return (
        _header(MessageType.QSO_LOGGED, id_)
        + dt_bytes
        + _utf8(dx_call) + _utf8("FN31")
        + struct.pack(">Q", 14_074_000)
        + _utf8("FT8") + _utf8("+03") + _utf8("-05")
        + _utf8("") + _utf8("") + _utf8("")
        + dt_bytes
        + _utf8("KC5CD") + _utf8("KC5CD") + _utf8("EM12")
        + _utf8("") + _utf8("")
    )


def _clear_bytes(id_: str = "WSJT-X", window: int | None = None) -> bytes:
    body = _header(MessageType.CLEAR, id_)
    if window is not None:
        body += struct.pack(">B", window)
    return body


def test_get_status_before_any_data_raises():
    listener = WSJTXListener()
    with pytest.raises(ListenerError, match="no WSJT-X instance"):
        listener.get_status()


def test_status_updates_get_status():
    listener = WSJTXListener()
    listener.datagram_received(_status_bytes(dial_hz=14_074_000), _ADDR)
    assert listener.get_status().dial_frequency_hz == 14_074_000

    listener.datagram_received(_status_bytes(dial_hz=7_074_000), _ADDR)
    assert listener.get_status().dial_frequency_hz == 7_074_000


def test_decodes_accumulate_most_recent_first():
    listener = WSJTXListener()
    listener.datagram_received(_decode_bytes(message="first"), _ADDR)
    listener.datagram_received(_decode_bytes(message="second"), _ADDR)
    decodes = listener.get_recent_decodes()
    assert [d.message for d in decodes] == ["second", "first"]


def test_decode_buffer_bounded_at_200():
    listener = WSJTXListener()
    for i in range(205):
        listener.datagram_received(_decode_bytes(message=str(i)), _ADDR)
    decodes = listener.get_recent_decodes(limit=1000)
    assert len(decodes) == 200
    assert decodes[0].message == "204"  # most recent first
    assert decodes[-1].message == "5"  # oldest 5 evicted


def test_get_recent_decodes_respects_limit():
    listener = WSJTXListener()
    for i in range(10):
        listener.datagram_received(_decode_bytes(message=str(i)), _ADDR)
    assert len(listener.get_recent_decodes(limit=3)) == 3


def test_clear_truncates_decode_buffer():
    listener = WSJTXListener()
    listener.datagram_received(_decode_bytes(), _ADDR)
    listener.datagram_received(_decode_bytes(), _ADDR)
    assert len(listener.get_recent_decodes()) == 2

    listener.datagram_received(_clear_bytes(window=0), _ADDR)
    assert listener.get_recent_decodes() == []


def test_qsos_accumulate():
    listener = WSJTXListener()
    listener.datagram_received(_qso_bytes(dx_call="K1ABC"), _ADDR)
    listener.datagram_received(_qso_bytes(dx_call="W1XYZ"), _ADDR)
    qsos = listener.get_recent_qsos()
    assert [q.dx_call for q in qsos] == ["W1XYZ", "K1ABC"]


def test_multiple_instances_require_instance_id():
    listener = WSJTXListener()
    listener.datagram_received(_status_bytes(id_="Station A", dial_hz=14_074_000), _ADDR)
    listener.datagram_received(_status_bytes(id_="Station B", dial_hz=7_074_000), _ADDR)

    with pytest.raises(ListenerError, match="multiple WSJT-X instances"):
        listener.get_status()

    assert listener.get_status(instance_id="Station A").dial_frequency_hz == 14_074_000
    assert listener.get_status(instance_id="Station B").dial_frequency_hz == 7_074_000


def test_unknown_instance_id_raises():
    listener = WSJTXListener()
    listener.datagram_received(_status_bytes(id_="Station A"), _ADDR)
    with pytest.raises(ListenerError, match="no data received"):
        listener.get_status(instance_id="Nonexistent")


def test_malformed_datagram_is_ignored():
    listener = WSJTXListener()
    listener.datagram_received(b"not a wsjtx datagram at all", _ADDR)
    with pytest.raises(ListenerError):
        listener.get_status()
