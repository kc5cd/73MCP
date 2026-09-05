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
  `get_status()`/`set_frequency()`/`set_mode()`.
- `rigctl_mcp/` — the MCP server itself (stdio transport), a thin wrapper over
  `rigctl_client`. Tools:
  - `get_status()` — dial frequency (Hz), mode, passband (Hz), VFO, PTT state.
  - `set_frequency(hz)`
  - `set_mode(mode, passband_hz=None)`

  `set_ptt` is deliberately not included yet — it keys a transmitter and deserves its own
  safeguards discussion (e.g. a required `confirm` flag) rather than being a plain tool
  alongside the read/frequency/mode ones. See `PLAN.md` for the full scope decision.

## Running

```
python -m rigctl_mcp --rigctld-host 127.0.0.1 --rigctld-port 4532
```

Flags default to `RIGCTLD_HOST`/`RIGCTLD_PORT` env vars, then `127.0.0.1`/`4532`. Requires a
`rigctld` instance already running and reachable at that address.

## Status

Built 2026-09-05: all 4 implementation phases from `PLAN.md` complete (protocol layer, TCP
client, MCP server, verification). 17 tests pass (`pytest tests/ -v`) — `test_protocol.py`
against hand-built ERP text, `test_client.py`'s `RigctlClient` against an in-process TCP stub
standing in for `rigctld` (its protocol is a raw line-based stream, not HTTP, so a mock
transport wouldn't be faithful). Manually verified end-to-end over stdio with a real MCP
`ClientSession` driving the same stub, confirming all 3 tools round-trip correctly including
the nonzero-`RPRT` → `ToolError` path.

**Real-`rigctld` verification is still outstanding** — this pass only exercised the in-process
stub, same gap as `wsjtx-mcp`'s real-WSJT-X and `nanovna-mcp`'s real-NanoVNA-hardware
verification.
