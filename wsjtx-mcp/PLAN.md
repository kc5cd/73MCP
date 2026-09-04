# WSJT-X MCP — Plan

## Context

WSJT-X publishes a live UDP protocol on the operating machine (multicast or
broadcast, default port `2237`, configurable in WSJT-X's own Settings →
Reporting) carrying station/decode/QSO events, and accepts a handful of
commands back over the same socket (e.g. requesting a specific reply/free
text, or a manual "Halt Tx"). This is the same mechanism JTAlert, GridTracker,
and N1MM+ integrate through — no separate daemon or process needs to own
anything exclusive, unlike `nanovna-mcp`'s serial port. That changes the
shape of this sub-project relative to `nanovna-mcp`: **no daemon layer is
needed here** — the MCP server can bind/read the UDP socket itself.

## Language/runtime decision (2026-09-03)

**Python**, matching `nanovna-mcp`. Reasoning:

- Consistency: same `mcp` Python SDK, same test tooling (`pytest`,
  `pytest-asyncio`), same packaging shape (`pyproject.toml`,
  `src`-less flat package) as the one other sub-project that's actually
  built. Nothing about WSJT-X's protocol favors a different language.
- `asyncio`'s `DatagramProtocol` is a good fit for a fire-and-forget UDP
  feed that needs to be read continuously in the background while MCP tool
  calls happen concurrently.
- **Lesson carried over from `nanovna-mcp`'s build** (see that branch's
  `.claude/state/context.md` if available, or `nanovna-mcp/pyproject.toml`'s
  git history): pin `mcp` to an exact version, not `mcp>=1.0` — a `>=1.0`
  range silently resolved to a 2.x release with a renamed API and different
  exception-forwarding behavior mid-build last time. Pin here from the start.

## Protocol reference

WSJT-X's UDP "NetworkMessage" protocol (implemented in WSJT-X's own
`Network/NetworkMessage.hpp`/`.cpp`, and documented informally in its
`NetworkMessage.hpp` header comments, which ship with the WSJT-X source).
Key shape, for scaffolding purposes:

- Each datagram starts with a fixed magic number (`0xADBCCBDA`), a schema
  version (currently 3), then a big-endian `quint32` message type ID,
  followed by type-specific fields, all encoded the way Qt's `QDataStream`
  serializes them (length-prefixed UTF-8/UTF-16 strings, fixed-width
  ints/doubles, no padding).
- Message types relevant to a first pass: `Heartbeat` (0), `Status` (1),
  `Decode` (2), `Clear` (3), `QSOLogged` (5), `Close` (6), `WSPRDecode` (10),
  `LoggedADIF` (12). Outbound (MCP → WSJT-X) messages of interest: `Reply`
  (4, tell WSJT-X to initiate a reply to a specific decode) and `Close` (6,
  ask it to exit) — later scope, not first pass.
- No third-party dependency for encoding/decoding: the message set actually
  needed is small, and existing community Python ports (e.g. `pywsjtx`) are
  unmaintained — implement the minimal encoder/decoder directly against
  WSJT-X's own header rather than taking on that dependency risk.

## Architecture

```
WSJT-X (already running, UDP enabled in Settings -> Reporting)
      |
      v  UDP datagrams (multicast/broadcast, port 2237 by default)
      |
+-----------------------+
|  wsjtx_udp             |   <-- asyncio DatagramProtocol; encodes/decodes
|  (Python, this repo)   |       NetworkMessage frames; no daemon needed,
+-----------------------+       runs in the same process as the MCP server
      |
      v
+-----------------------+
|  wsjtx_mcp              |   <-- MCP tools (stdio transport, same choice
|  (Python, this repo)   |       as nanovna-mcp and for the same reason:
+-----------------------+       launched as a subprocess by the MCP client,
                                  no network exposure of its own)
```

Likely first-pass tools (to be finalized in a plan-mode session before
building, same phased-approval pattern as `nanovna-mcp`):

- `get_status` — most recent `Status` message (dial frequency, mode, DX
  call/grid, Tx/Rx state).
- `get_recent_decodes` — buffered `Decode` messages since last cleared/since
  server start.
- `get_recent_qsos` — buffered `QSOLogged` messages (what's actually been
  logged this session).

Deferred to a later pass: sending commands back to WSJT-X (`Reply`, free
text, `Halt Tx`), WSPR-specific decode handling, ADIF log-file access as a
separate source of historical (not just live-session) QSOs.

## Verification

No daemon to stand up first, unlike `nanovna-mcp` — verification needs
WSJT-X itself running locally with UDP reporting enabled (Settings →
Reporting → "Enable" under UDP Server, default `127.0.0.1:2237`), then the
MCP server driven the same way `nanovna-mcp`'s was (a real stdio
`ClientSession`, or the MCP inspector CLI), confirming `get_status` and
`get_recent_decodes` reflect what WSJT-X is actually doing.

## Next step

This document records the language/runtime decision and rough shape only.
Actual implementation should go through the same plan-mode
scope/design/phasing process `nanovna-mcp` did before writing code.
