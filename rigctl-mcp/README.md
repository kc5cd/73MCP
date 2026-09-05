# rigctl-mcp

MCP server for [Hamlib](https://github.com/Hamlib/Hamlib)'s `rigctl`/`rigctld` rig-control
interface, so an MCP client can query and drive a transceiver (frequency, mode, PTT, and the
rest of Hamlib's `set`/`get` command set) without talking to the radio's own vendor protocol
directly. Hamlib already normalizes that part across hundreds of rig models — this project's
job is only the MCP-facing layer on top of it.

## How it works

There's no daemon of our own: `rigctld` (started separately, e.g. `rigctld -m <model> -r
<device>`) already owns the rig connection, so this server talks to it directly over its TCP
Extended Response Protocol (default `127.0.0.1:4532`), connecting lazily on first tool call
and reusing that connection afterward.

- `rigctl_client/` — protocol + TCP client, no MCP awareness. `protocol.py` has pure
  `build_command()`/`parse_response()` functions (no I/O); `client.py`'s `RigctlClient` holds
  the persistent `asyncio` connection (lock-guarded, one command at a time) and exposes
  `get_status()`/`set_frequency()`/`set_mode()`/`set_ptt()`.
- `rigctl_mcp/` — the MCP server itself (stdio transport), a thin wrapper over
  `rigctl_client`. Tools:
  - `get_status()` — dial frequency (Hz), mode, passband (Hz), VFO, PTT state.
  - `set_frequency(hz)`
  - `set_mode(mode, passband_hz=None)`
  - `set_ptt(on, confirm=None)` — **only registered at all if the server was started with
    `--allow-ptt`**. Keying on (`on=True`) requires `confirm="transmit"` exactly; unkeying
    never needs it. A server-side watchdog force-unkeys after `--max-ptt-seconds` (default
    130s) even if `set_ptt(False)` never arrives. See `PLAN.md`'s "First-pass tool scope" for
    the full safeguards rationale.

## Running

```
python -m rigctl_mcp --rigctld-host 127.0.0.1 --rigctld-port 4532
```

Flags default to `RIGCTLD_HOST`/`RIGCTLD_PORT` env vars, then `127.0.0.1`/`4532`. Requires a
`rigctld` instance already running and reachable at that address.

To also enable `set_ptt` (off by default — it keys a transmitter):

```
python -m rigctl_mcp --rigctld-host 127.0.0.1 --rigctld-port 4532 --allow-ptt --max-ptt-seconds 130
```

(`RIGCTL_ALLOW_PTT=1` / `RIGCTL_MAX_PTT_SECONDS` env vars work the same way.) Pick
`--max-ptt-seconds` to comfortably clear your longest expected transmit cycle — the default
(130s) covers WSPR's ~110s, but adjust it down for a pass built only around short CW/voice
keying, or up for a longer digital-mode cycle.

## Status

Built 2026-09-05: all 4 implementation phases from `PLAN.md` complete (protocol layer, TCP
client, MCP server, verification). 18 tests pass (`pytest tests/ -v`) — `test_protocol.py`
against hand-built ERP text, `test_client.py`'s `RigctlClient` against an in-process TCP stub
standing in for `rigctld` (its protocol is a raw line-based stream, not HTTP, so a mock
transport wouldn't be faithful). Manually verified end-to-end over stdio with a real MCP
`ClientSession` driving the same stub, confirming all 3 tools round-trip correctly including
the nonzero-`RPRT` → `ToolError` path.

**Real-`rigctld` verified 2026-09-05**: WSJT-X ships its own private Hamlib build
(`rigctld-wsjtx.exe`), run here with the Hamlib Dummy rig backend (`-m 1`) — a fully simulated
rig, no hardware or antenna needed. `get_status`, `set_frequency`, and `set_mode` all
round-tripped correctly against the real binary (not the test stub), with a frequency/mode
change confirmed by a follow-up `get_status`. One finding: the Dummy backend accepts any
string as a mode without validating it, so it doesn't exercise the nonzero-`RPRT` → `ToolError`
path — that path stays covered by the in-process-stub tests instead, where the response can be
scripted deliberately.

**`set_ptt` added and verified 2026-09-05**: the safeguards deferred on 2026-09-04 are all
implemented together — opt-in `--allow-ptt`, required `confirm="transmit"` to key on, and a
`--max-ptt-seconds` auto-unkey watchdog. Verified against the same real Dummy `rigctld`
(simulated PTT, no real transmitter): opt-in gating, both confirm-rejection cases, successful
keying, the watchdog actually firing on schedule, and confirm-free unkeying all confirmed.
