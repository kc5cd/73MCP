# AntScope MCP — Plan

## Context

Casey wants to control his NanoVNA remotely: a small webapp for
day-to-day remote use, plus an MCP server so an AI agent can drive the
analyzer directly. This came out of researching whether the AntScopeZ
desktop app exposes any API to build on: it doesn't. The only
network-facing code in AntScopeZ at all is an abandoned,
permanently-disabled UDP bridge in `OneFqWidget`
(`src/onefqwidget.cpp`, in the `AntScopeZ` repo) that a prior
investigation (`BUILDINFO.md` in that repo, 2026-08-20) already found
broken-by-design and not worth fixing in place.

Given that, the design bypasses AntScopeZ's own protocol handling and
talks to the NanoVNA's serial protocol directly — but the resulting API
daemon is still considered **general AntScopeZ-project functionality**
(not Windows-specific, not tied to the desktop app's UI), so **it lives
in the `AntScopeZ` repo itself**, on its own branch, not in this
`73MCP` repo. See "Where things actually live" below.

## Where things actually live

- **API daemon** (owns the NanoVNA serial connection, exposes it over
  REST + WebSocket): lives in the **`AntScopeZ` repo, `remote-api`
  branch** (branched off `master`, not `windows-port` — deliberately
  general-purpose, not Windows-specific), in a top-level `remote-api/`
  directory there. Built by the Claude Code session working in that
  repo. **This is not part of this (`73MCP`) repo.**
- **MCP server** (this sub-project, `antscope-mcp/` in `73MCP`) and
  **the webapp**: both to be built as HTTP/WebSocket clients of that
  API daemon — neither needs to know anything about the serial
  protocol, both just call the API described below. **Not yet
  started** — this is the actual deliverable of this sub-project,
  picked up by a separate agent/session working in this (`73MCP`) repo.
- The `nanovna-mcp/` folder elsewhere in this repo is unrelated to this
  effort — a separate placeholder Casey is filling in himself later.

## Architecture

```
NanoVNA (USB-serial, VID 0x0483 / PID 0x5740)
      |
      v
+----------------------+
|   nanovna_api daemon   |   <-- owns the serial port; single source of truth
|   (Python, FastAPI)     |       lives in the AntScopeZ repo, remote-api branch
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
[MCP server]     [webapp]     <-- built here, in 73MCP/antscope-mcp/
```

Only the daemon (in the `AntScopeZ` repo) ever opens the serial port.
Everything else — MCP server, webapp, any future client — talks to it
over the network (localhost or LAN), never to the serial port directly.
This is what lets the webapp and an AI agent use the analyzer at the
same time without fighting over the port.

## Deployment scope for v1

**Local network only.** No auth/TLS in this phase — add later if/when
Casey wants internet-reachable access. The daemon binds to a LAN-visible
address (not just `127.0.0.1`) so a phone/laptop on the same network can
reach it directly; the MCP server and webapp can run on the same
machine as the daemon or elsewhere on the LAN.

## Protocol reference (for context only — already implemented in the daemon)

The daemon (in `AntScopeZ`'s `remote-api` branch) implements the
classic ASCII `sweep`/`frequencies`/`data 0`/`data 1` NanoVNA command
sequence, grounded in and cross-checked against AntScopeZ's own C++
reference implementation (`analyzer/nanovna_analyzer.cpp`/`.h` in that
repo). Neither the MCP server nor the webapp need to know these
details — they only need the API contract below — but for background:
USB VID `0x0483` / PID `0x5740`; commands are `\r\n`-terminated ASCII
sent over the serial port; every reply is terminated by a line
containing `ch>`; impedance/SWR are derived from each S11 reflection
coefficient using the standard 50Ω-reference formula.

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

- `WS /sweep/stream` — client sends `{start_hz, stop_hz, points}` after
  connecting; server streams sweep points as JSON messages as they
  arrive during the in-progress sweep, then a final `{"done": true}`
  before closing. Same per-point JSON shape as `/sweep`'s response
  entries.

Response point shape (both REST and WebSocket):

```json
{
  "freq_hz": 468000000.0,
  "s11": {"re": 0.02, "im": 0.01},
  "s21": {"re": 0.9, "im": 0.0},
  "impedance": {"r": 48.1, "x": 1.2},
  "swr": 1.05
}
```

(`s21` is omitted for a point if S21 wasn't available from the device.)

## Deferred (explicitly out of scope for v1)

- OSL calibration.
- Saved measurement history/persistence.
- Auth/TLS for anything beyond local-network use.

## Verification

Once the MCP server and/or webapp are built here: point them at a
running instance of the daemon (see the `AntScopeZ` repo's
`remote-api` branch for how to run it — `remote-api/README.md` there),
and confirm `GET /devices` → `POST /connect` → `POST /sweep` (or the
WebSocket equivalent) round-trips correctly against real hardware.
