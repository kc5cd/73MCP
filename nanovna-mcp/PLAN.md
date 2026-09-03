# NanoVNA MCP + remote-access API — Plan

## Context

Casey wants to control his NanoVNA remotely: a small webapp for
day-to-day remote use, plus an MCP server so an AI agent can drive the
analyzer directly, both as part of the `73MCP` project. This came out of
researching whether AntScopeZ (the desktop app) exposes any API to build
on: it doesn't. The only network-facing code in AntScopeZ at all is an
abandoned, permanently-disabled UDP bridge in `OneFqWidget`
(`src/onefqwidget.cpp`) that a prior investigation (`BUILDINFO.md` in the
AntScopeZ repo, 2026-08-20) already found broken-by-design and not worth
fixing in place. Given that, and that Casey explicitly wants a
**NanoVNA** MCP (not an AntScopeZ-*app* MCP), the design bypasses
AntScopeZ entirely and talks to the NanoVNA's own serial protocol
directly. That protocol was already proven end-to-end against real
hardware in a prior AntScopeZ session (see the protocol reference
below), and AntScopeZ's own `analyzer/nanovna_analyzer.cpp`/`.h` (C++,
in the `AntScopeZ` repo) serve as a working reference implementation for
anyone implementing this to check behavior against — not copied from
directly (different language, different project).

This is a **new** sub-project (`nanovna-mcp/`), separate from the
existing `antscope-mcp` placeholder (which still targets the AntScopeZ
*app* itself, untouched, a possible separate future effort).

## Division of labor (as of 2026-09-03)

This project is split across two builders working from this one plan:

1. **The API daemon** (`nanovna_api/` in this directory) — built by the
   Claude Code session working in the `AntScopeZ` repo that wrote this
   plan. This is the single process that owns the NanoVNA's serial
   connection and exposes it over HTTP + WebSocket.
2. **The MCP server and the webapp** — built by a different agent/session,
   both as clients of the API daemon in (1) over HTTP/WebSocket (not an
   in-process import — keeps the two builders' work decoupled). Neither
   needs to know anything about the serial protocol; both just call the
   API described below.

## Architecture

```
NanoVNA (USB-serial, VID 0x0483 / PID 0x5740)
      |
      v
+----------------------+
|   nanovna_api daemon   |   <-- owns the serial port; single source of truth
|   (Python, FastAPI)     |       built in THIS plan, by the AntScopeZ-repo session
+----------------------+
   |                  |
   v                  v
[REST endpoints]   [WebSocket: live sweep stream]
   |                  |
   +--------+---------+
            |
   consumed by BOTH of, independently:
            |
     +------+-------+
     v              v
[MCP server]     [webapp]     <-- built separately, by a different agent
```

Only one process (the daemon) ever opens the serial port. Everything
else — MCP server, webapp, any future client — talks to the daemon over
the network (localhost or LAN), never to the serial port directly. This
is what lets the webapp and an AI agent use the analyzer at the same
time without fighting over the port.

## Deployment scope for v1

**Local network only.** No auth/TLS in this phase — add later if/when
Casey wants internet-reachable access. The daemon binds to a LAN-visible
address (not just `127.0.0.1`) so a phone/laptop on the same network can
reach it directly; MCP server and webapp can run on the same machine as
the daemon or elsewhere on the LAN.

## Protocol reference (grounded in AntScopeZ's C++ implementation)

- **USB identification**: VID `0x0483`, PID `0x5740`
  (`analyzer/nanovna_analyzer.h:21-22` in the `AntScopeZ` repo).
- **Commands** (plain ASCII over the serial port, `\r\n`-terminated):
  - `info\r\n` — device/firmware identification.
  - `sweep <start_hz> <stop_hz> <points>\r\n` — configure a sweep.
  - `frequencies\r\n` — list the frequency points for the last configured sweep.
  - `data 0\r\n` — S11 (reflection) data for the last sweep.
  - `data 1\r\n` — S21 (through) data for the last sweep, if supported.
  - `scan <start_hz> <stop_hz> <points> <mask>\r\n` — newer combined
    ASCII/binary fast-path (mask bits select S11/S21/binary mode); see
    `analyzer/nanovna_analyzer.cpp` in `AntScopeZ` around
    `probeBinaryScanSupport()` for the capability-probe pattern, and
    `parseBinaryScan()` for the binary reply framing (`uint16 mask`,
    `uint16 points` header, then packed `float` re/im pairs per point
    per selected channel).
  - Every reply command's first line **echoes the command itself back**
    before the real data — AntScopeZ's own parser had real bugs from not
    accounting for this (see the `fq <= 0` guards added in AntScopeZ
    commit `b66d9d3` and its issue #3 fix); don't repeat that mistake
    here.
- **Impedance from reflection coefficient** (50Ω reference): given
  `Γ = re + j·im`,
  `Z = 50 * (1 - re² - im²)/((1-re)² + im²) + j·50 * (2·im)/((1-re)² + im²)`
  — this is exactly `NanovnaAnalyzer::impedanceFromReflection()`
  (`analyzer/nanovna_analyzer.cpp` in `AntScopeZ`) ported to Python; SWR
  follows from `|Γ|` in the usual way.
- **Confirmed-working example** (captured live against real hardware,
  2026-08-30): `sweep 420000000 540000000 101` then `data 0` returned
  101 points; SWR computed from them was ≈3.0:1 @420MHz → ≈1.05:1
  @468MHz → ≈2.8:1 @540MHz, matching the connected antenna's known
  behavior. Good fixture for a protocol unit test, or a manual
  verification step against real hardware.

## Daemon API (v1) — for the MCP server and webapp to build against

REST (JSON):

- `GET /devices` — list connected NanoVNA-matching serial ports
  (VID/PID match), not yet connected.
- `POST /connect {port: str}` — open the serial connection.
- `POST /disconnect`
- `GET /info` — firmware/version string from `info`.
- `POST /sweep {start_hz: int, stop_hz: int, points: int}` — run a
  sweep, return per-point frequency + S11 (+ S21 if available) + derived
  SWR/impedance once the sweep completes.
- `GET /status` — current connection state + last sweep parameters.

WebSocket:

- `WS /sweep/stream` — subscribe to receive sweep points as they arrive
  during an in-progress sweep (rather than waiting for `/sweep` to
  return everything at once). Same per-point shape as `/sweep`'s
  response entries.

## Deferred (explicitly out of scope for v1)

- OSL calibration.
- Saved measurement history/persistence.
- Auth/TLS for anything beyond local-network use.
- `antscope-mcp` (the app-level placeholder) — untouched, separate future work.

## Verification

- Unit tests (no hardware required) for protocol parsing and the
  impedance/SWR math, using the confirmed-working example above as a
  fixture.
- Manual end-to-end check against real hardware: run the daemon, call
  `POST /connect` → `POST /sweep` (420000000, 540000000, 101) via curl
  or the webapp/MCP client, confirm the returned SWR curve matches the
  same ≈3.0/1.05/2.8 shape captured previously.
