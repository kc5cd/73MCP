# nanovna-mcp

A local network API daemon for NanoVNA antenna analyzers, living on the `nanovna-mcp` branch
of the `73MCP` repo. **Moved here from AntScopeZ's `remote-api` branch on 2026-09-03** — see
`## History` below for why.

## Why this exists

Casey wants to control his NanoVNA remotely: a small webapp, plus an MCP server so an AI
agent can drive the analyzer directly. AntScopeZ itself has no usable API to build either of
those on — the only network-facing code in the app at all is an abandoned, permanently
disabled UDP bridge in `OneFqWidget` (`src/onefqwidget.cpp` in the AntScopeZ repo) already
found broken-by-design for this purpose (`BUILDINFO.md`, 2026-08-20 entry, AntScopeZ repo).

So this daemon bypasses AntScopeZ's own protocol handling and talks to the NanoVNA's serial
protocol directly — proven working end-to-end against real hardware in a prior session
(`sweep 420000000 540000000 101` then `data 0`, straight over the COM port, no app involved).
AntScopeZ's `analyzer/nanovna_analyzer.cpp`/`.h` is the reference implementation this was
ported from (useful to cross-check the protocol reference below against, but this project
has no dependency on that repo at runtime).

## History

Originally built on AntScopeZ's `remote-api` branch (2026-09-02/03) under the reasoning that
it was "general project functionality, not Windows-specific" rather than part of the desktop
Qt app. Superseded 2026-09-03: AntScopeZ's repo should stay scoped to the AntScopeZ desktop
app itself, not host NanoVNA-specific API tooling — this project belongs in `73MCP` alongside
the other MCP sub-projects instead, which is also a more natural home for it now that it's
named `nanovna-mcp`. Moved by AntScopeZ's session, source-identical (all 10 tracked files
copied as-is), with a knowledge-transfer message sent to this repo's session afterward.

**Decoupling confirmed (2026-09-03)**: `nanovna-mcp` should always have been separate from
`antscope-mcp` and never coupled with it — Casey confirmed this directly after the move.
`antscope-mcp` instead targets a distinct, still-undefined AntScopeZ application API to be
designed/built separately; it has no dependency on this daemon.

## Where the pieces live

- **This daemon** (`nanovna-mcp/`, this branch): owns the serial port, exposes REST+WebSocket.
- **MCP server** (`nanovna_mcp/`): built 2026-09-03 — stdio transport, 6 tools
  (`list_devices`, `status`, `connect`, `disconnect`, `get_info`, `sweep`) over the daemon's
  REST API. See `## MCP server` below.
- **Webapp**: built 2026-09-04, extended through 2026-09-05 — a single self-contained page
  served by the daemon itself at `/` (`nanovna_api/static/index.html`), no build step, no CDN
  dependencies (works offline on the LAN). See `## Webapp` below.

**`nanovna-mcp` is a standalone project, fully decoupled from `73MCP`'s `antscope-mcp`
sub-project** (confirmed by Casey 2026-09-03, after a brief period where the two were
treated as coupled during this daemon's move from AntScopeZ — see `## History`).
`antscope-mcp` targets a separate, not-yet-defined AntScopeZ application API and has no
relationship to this daemon or this protocol.

```
NanoVNA (USB-serial, VID 0x0483 / PID 0x5740)
      |
      v
+------------------------+
|   nanovna_api daemon    |   <-- this directory; owns the serial port
|   (Python, FastAPI)     |
+------------------------+
   |                  |
   v                  v
[REST endpoints]   [WebSocket: live sweep stream]
            |
   consumed by BOTH of, independently:
     [MCP server]     [webapp]
```

## Deployment scope for v1

Local network only. No auth/TLS in this phase — add later if/when Casey wants
internet-reachable access. Binds to `0.0.0.0` by default so a phone/laptop on the same LAN
can reach it.

## Protocol reference

- **USB identification**: VID `0x0483`, PID `0x5740` (`analyzer/nanovna_analyzer.h`).
- **Commands** (plain ASCII, `\r\n`-terminated): `info`, `sweep <start_hz> <stop_hz>
  <points>`, `frequencies`, `data 0` (S11), `data 1` (S21). Every reply is terminated by a
  line containing `ch>` — see `analyzer/nanovna_analyzer.cpp`'s own parser for the exact
  per-command sequence this was ported from (`parse()`'s `WAIT_NANO_SWEEP` /
  `WAIT_NANO_FQ` / `WAIT_NANO_DATA` / `WAIT_NANO_DATA_S21` states).
- **`data N` line format**: just `"<re> <im>"` — frequency comes from the separately-fetched
  `frequencies` list, paired by index/order, exactly as the C++ parser does it.
- Only the classic ASCII path is implemented — the newer binary `scan` fast path
  (`probeBinaryScanSupport()`/`parseBinaryScan()` in the C++ reference) isn't needed for v1.
- **Impedance from reflection coefficient** (50Ω reference): ported directly from
  `NanovnaAnalyzer::impedanceFromReflection()` (`analyzer/nanovna_analyzer.cpp`).
- **Confirmed-working example** (real hardware, 2026-08-30): `sweep 420000000 540000000 101`
  then `data 0` returned 101 points; SWR ≈3.0:1 @420MHz → ≈1.05:1 @468MHz → ≈2.8:1 @540MHz,
  matching the connected antenna's known behavior.

## Daemon API

REST (JSON):

- `GET /devices` — list connected NanoVNA-matching serial ports (VID/PID match), not yet connected.
- `POST /connect {port: str}` — open the serial connection.
- `POST /disconnect`
- `GET /info` — firmware/version string from `info`.
- `POST /sweep {start_hz: int, stop_hz: int, points: int}` — run a sweep, return all points once complete.
- `GET /status` — current connection state.

WebSocket:

- `WS /sweep/stream` — client sends `{start_hz, stop_hz, points}` after connecting; server
  streams points as JSON as they arrive, then `{"done": true}` before closing.

Point shape (both REST and WebSocket):

```json
{
  "freq_hz": 468000000.0,
  "s11": {"re": 0.02, "im": 0.01},
  "s21": {"re": 0.9, "im": 0.0},
  "impedance": {"r": 48.1, "x": 1.2},
  "swr": 1.05
}
```

(`s21` omitted for a point if S21 wasn't available from the device.)

## Deferred (explicitly out of scope for v1)

OSL calibration, saved measurement history/persistence, auth/TLS beyond local-network use.

## Running

```
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m nanovna_api --host 0.0.0.0 --port 8765
```

```
curl http://<host>:8765/devices
curl -X POST http://<host>:8765/connect -H "Content-Type: application/json" -d "{\"port\":\"COM20\"}"
curl -X POST http://<host>:8765/sweep -H "Content-Type: application/json" -d "{\"start_hz\":420000000,\"stop_hz\":540000000,\"points\":101}"
```

## MCP server

`nanovna_mcp/` — stdio transport, 6 tools thin-wrapping the daemon's REST API: `list_devices`,
`status`, `connect`, `disconnect`, `get_info`, `sweep` (blocking — returns the finished sweep
rather than streaming). Verified end-to-end via a real `ClientSession` against the running
daemon (no hardware); not yet separately verified against real NanoVNA hardware beyond the
daemon protocol itself (see `## Status`).

```
.venv\Scripts\python -m nanovna_mcp --daemon-url http://<host>:8765
```

## Webapp

Open `http://<host>:8765/` in any browser on the same LAN (phone, laptop, tablet) — the daemon
serves the page itself, so there's nothing separate to install or deploy. Flow: pick a device
from the dropdown and Connect, enter a Start/Stop MHz range and point count, then either
**Sweep once** or **Start live tuning** (repeats the sweep continuously over the WebSocket
stream so the SWR curve updates live while you adjust the antenna). The chart marks the
lowest-SWR point and reports its frequency and impedance; the trace itself is colored red
wherever SWR exceeds 3:1 and green elsewhere. Last-used sweep params are remembered
per-browser (`localStorage`). No auth, matching this project's local-network-only v1 scope.

**Band selection**: ITU Region + Band dropdowns sit above Start/Stop MHz — picking a band
fills Start/Stop from that band's edges (padded 0.05MHz past each edge). Only ITU Region 2
(the Americas, i.e. the US band plan) has real data; Regions 1/3 show a placeholder. Points
steps by 25, Start/Stop MHz step by 0.1MHz.

**"Highlight amateur bands"** overlays the full US band plan (2200m through 23cm, plus 11m
CB) on the chart, sourced from `bands.md` in this directory — Casey's own transcription of
the ARRL band chart, which is the authoritative data for every band edge and per-license-class
privilege in this webapp (not derived from general knowledge of 47 CFR 97.301). Each band
renders as a low-opacity full-height watermark plus ARRL-style mode-color rows (red =
RTTY/Data, green = Phone/Image, yellow = SSB-only, blue = 60m, white = CW-only), each with a
thin border and a hover tooltip naming its license class.

**License dropdown**: "All licenses" shows all four rows stacked (Extra/Advanced/General/
Technician, top to bottom, each labeled with a T/G/A/E initial outside the band's edges —
skipped for a class with zero privilege anywhere in that band, e.g. Technician on 30m).
Picking one specific class instead expands that class's row to fill the strip and grays out
the swept frequencies that fall outside its privileges.

**11m (CB)**, 26.965-27.405MHz, is not an amateur allocation at all (confirmed blank in
`bands.md`) — it renders a black "Not Allowed With Amateur Radio Equipment" bar instead of
privilege rows, is excluded from every class's grayout regardless of selection, and (only
when Extra is selected) adds a small "Even you cannot transmit here" line near the bottom.

**"K4HEZ Style"** (Casey's own request) turns the band watermarks and mode-color rows into an
animated neon-pink flicker effect, purely cosmetic.

**Freq markers dropdown**: overlays FT8, FT4, or JS8 dial frequencies, or a QRP-USA calling-
frequency set, as dashed vertical lines (with a sideways label) at each listed frequency
falling inside the current sweep range. Data is sourced from the `ShackNotes` reference
project (a separate repo, not part of `73MCP`) rather than transcribed inline here.

## Tests

```
.venv\Scripts\python -m pytest tests/ -v
```

## Status

- Implemented, unit-tested (11 tests, `tests/`), and fully smoke-tested (2026-09-03) against
  a running daemon with no hardware attached: `/devices`, `/status`, REST error paths
  (bad port → 400, not-connected → 409, idempotent `/disconnect`, pydantic 422 validation on
  malformed bodies), and the `/sweep/stream` WebSocket (accepts, validates, error-reports,
  closes cleanly) all behave correctly.
- Found and fixed live (2026-09-03): bare `uvicorn` has no WebSocket protocol backend without
  the `websockets` package — `/sweep/stream` silently 404'd instead of upgrading. Now an
  explicit dependency in `pyproject.toml`; a fresh `pip install -e .` picks it up.
- **Verified against real NanoVNA hardware (2026-09-04)**, first time one was available:
  connected on `COM20`, swept 400-550MHz against a real antenna via `sweep.run_sweep()`
  directly. **Found and fixed a real bug in the same pass**: the NanoVNA's shell echoes each
  command back as the first line of every reply (e.g. sending `frequencies` gets a literal
  `"frequencies"` line before the actual data) — `parse_frequency_hz`/`parse_re_im`'s
  permissive fallback silently turned that into a bogus leading `freq_hz=0`/`s11=0` point on
  every sweep. Fixed generically in `device.py`'s `read_until_prompt()` (drops the echoed line
  when it matches the command just sent), not by special-casing zero frequencies. Confirmed
  fixed against the same hardware: first point is now real data at the sweep's start
  frequency. **Also observed**: the firmware's `sweep <start> <stop> <points>` returned
  `2*points - 1` frequency points (11 requested → 21 returned) rather than exactly `points` —
  not yet investigated further, doesn't affect correctness of the returned points, only the
  count.
- **MCP server** (`nanovna_mcp/`) built and verified 2026-09-03 against the real daemon (no
  hardware) via a stdio `ClientSession` exercising all 6 tools, including the error path
  (daemon errors surface as `ToolError` so the real message reaches the caller instead of a
  generic "Error executing tool X" — an `mcp` SDK 2.x behavior change, not the daemon's fault).
  Not yet separately verified against real NanoVNA hardware.
- **Webapp band/privilege data corrected 2026-09-04/05**: originally derived from general
  knowledge of 47 CFR 97.301 (never freshly re-verified against a primary source — WebFetch
  attempts against ecfr.gov/law.cornell.edu/arrl.org all failed). Replaced with `bands.md`
  (Casey's own ARRL chart transcription), which corrected several sub-band edges (80m/40m/
  20m/15m Advanced privileges) and resolved
  [issue #3](https://github.com/kc5cd/73MCP/issues/3) (70cm/2m/1.25m mode coloring had looked
  incomplete but was actually correct once bands.md confirmed those bands have no per-class
  split).
