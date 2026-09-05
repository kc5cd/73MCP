"""asyncio DatagramProtocol that consumes WSJT-X's live UDP feed and buffers
recent state per instance -- this is the whole "live feed" layer; no daemon
process, no network exposure of its own (see wsjtx-mcp/PLAN.md).
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

from .protocol import Clear, Decode, Heartbeat, Message, QSOLogged, Status, decode

logger = logging.getLogger(__name__)

_DECODE_BUFFER_SIZE = 200
_QSO_BUFFER_SIZE = 100


class ListenerError(RuntimeError):
    """No data yet, or an ambiguous/unknown instance_id -- carries a message
    meant to reach an MCP tool caller directly (see wsjtx_mcp/server.py).
    """


@dataclass
class _InstanceState:
    status: Status | None = None
    decodes: deque[Decode] = field(default_factory=lambda: deque(maxlen=_DECODE_BUFFER_SIZE))
    qsos: deque[QSOLogged] = field(default_factory=lambda: deque(maxlen=_QSO_BUFFER_SIZE))


class WSJTXListener:
    """Owns per-instance state. Usable standalone (feed it decoded bytes via
    datagram_received) or wired into asyncio via loop.create_datagram_endpoint,
    since it implements the DatagramProtocol callback shape without actually
    subclassing asyncio.DatagramProtocol -- keeps this importable/testable
    with zero event loop or real socket involved.
    """

    def __init__(self) -> None:
        self._instances: dict[str, _InstanceState] = {}

    # -- asyncio.DatagramProtocol callback shape --

    def connection_made(self, transport) -> None:
        pass

    def datagram_received(self, data: bytes, addr) -> None:
        message = decode(data)
        if message is None:
            logger.debug("ignoring undecodable datagram from %s (%d bytes)", addr, len(data))
            return
        self._handle(message)

    def error_received(self, exc: Exception) -> None:
        # Nothing is ever sent in this pass, so there's no prior send for an
        # OS-surfaced ICMP error to correspond to -- just don't crash the loop.
        logger.debug("UDP error_received: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        pass

    # -- state updates --

    def _state_for(self, instance_id: str) -> _InstanceState:
        return self._instances.setdefault(instance_id, _InstanceState())

    def _handle(self, message: Message) -> None:
        if isinstance(message, Status):
            self._state_for(message.id).status = message
        elif isinstance(message, Decode):
            self._state_for(message.id).decodes.append(message)
        elif isinstance(message, QSOLogged):
            self._state_for(message.id).qsos.append(message)
        elif isinstance(message, Clear):
            # Matches WSJT-X's own "Erase" semantics for the Band Activity
            # window -- see wsjtx_udp/protocol.py's Clear doc comment.
            self._state_for(message.id).decodes.clear()
        elif isinstance(message, Heartbeat):
            self._state_for(message.id)  # register the instance's presence

    # -- queries --

    def _resolve_instance(self, instance_id: str | None) -> str:
        if instance_id is not None:
            return instance_id
        if len(self._instances) == 1:
            return next(iter(self._instances))
        if not self._instances:
            raise ListenerError("no WSJT-X instance has been heard from yet")
        raise ListenerError(
            f"multiple WSJT-X instances heard ({sorted(self._instances)}); pass instance_id"
        )

    def _resolve_state(self, instance_id: str | None) -> tuple[str, _InstanceState]:
        resolved = self._resolve_instance(instance_id)
        state = self._instances.get(resolved)
        if state is None:
            raise ListenerError(f"no data received yet for instance {resolved!r}")
        return resolved, state

    def get_status(self, instance_id: str | None = None) -> Status:
        resolved, state = self._resolve_state(instance_id)
        if state.status is None:
            raise ListenerError(f"no Status message received yet for instance {resolved!r}")
        return state.status

    def get_recent_decodes(self, instance_id: str | None = None, limit: int = 50) -> list[Decode]:
        _, state = self._resolve_state(instance_id)
        return list(reversed(state.decodes))[:limit]

    def get_recent_qsos(self, instance_id: str | None = None, limit: int = 20) -> list[QSOLogged]:
        _, state = self._resolve_state(instance_id)
        return list(reversed(state.qsos))[:limit]
