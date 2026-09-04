# rigctl MCP — Plan

## Context

Hamlib's `rigctld` already normalizes rig control across hundreds of transceiver models
behind one stable TCP protocol — this sub-project only needs to expose that protocol as MCP
tools, not reimplement any rig-specific logic.

## Language/runtime + protocol approach decision (2026-09-04)

**Python**, matching `nanovna-mcp` and `wsjtx-mcp`'s tooling (`mcp` SDK — pinned to an exact
version from the start, per the lesson from `nanovna-mcp`'s build — `pytest-asyncio`,
`pyproject.toml` shape).

**Talk to an already-running `rigctld` over its TCP protocol**, not Hamlib's Python C
binding (the SWIG-generated `Hamlib` module). Reasoning:

- `rigctld` is already the daemon here — same shape as `nanovna-mcp`'s architecture (a
  daemon owns the hardware; everything else is a network client of it), except Hamlib project
  ships that daemon for us, so there's nothing to build on that side.
- The Python binding would make this MCP server itself own the serial/USB connection
  directly, reintroducing the single-owner problem `nanovna-mcp`'s daemon split was built to
  avoid (nothing else — a logging program, a second MCP client — could use the rig at the
  same time), and it's a compiled C extension tied to a specific installed Hamlib version:
  much harder to package/pin than a pure-Python TCP client with no C dependency.
- A ham already running `rigctld` for other software (N1MM+, remote-control setups, etc.) can
  point this MCP server at the same daemon with zero extra setup.

## Protocol reference

`rigctld`'s TCP protocol (default port `4532`), confirmed against Hamlib's own `rigctld(1)`
manpage (https://hamlib.sourceforge.net/html/rigctld.1.html):

- Plain form: one command per line, short letter for common ops (lowercase = get, uppercase =
  set) — `f`/`F` (frequency), `m`/`M` (mode), `t`/`T` (PTT), `v`/`V` (VFO) — or a long form
  prefixed with `\` (`\get_freq`, `\set_freq`, etc.). A get command's plain response is bare
  values, one per line; a set command responds `RPRT x` (`x` = 0 on success, negative Hamlib
  error code otherwise).
- **Extended Response Protocol (ERP)**: prefix a command with `+` to get a response with the
  command's long name echoed, `Key: value` pairs for each returned field, and a trailing
  `RPRT x`. E.g. `+\get_mode` →
  ```
  get_mode:
  Mode: USB
  Passband: 2400
  RPRT 0
  ```
  **Use ERP for every command**, not the plain form — parsing labeled `Key: value` pairs is
  far less fragile than positional bare-value lines, and the trailing `RPRT x` gives a
  uniform, unambiguous success/error signal for both get and set commands (the plain form
  only returns `RPRT x` for set commands, leaving get-command failures ambiguous).
- `\dump_state` returns backend/rig capability info (useful for a future `get_rig_info` tool,
  not decided yet).
- `\chk_vfo` reports whether the daemon was started with `-o`/`--vfo` (per-command VFO
  targeting) — relevant to whether tools need a `vfo` parameter at all; check this at
  connection time rather than assuming.

## Architecture

```
Radio (owned by rigctld -- serial/USB/network backend, whatever rigctld was started with)
      |
      v
+------------------+
|  rigctld            |   <-- Hamlib's own daemon, not built here; already normalizes
|  (ships with Hamlib) |       rig-specific protocols behind one TCP interface
+------------------+
      |
      v  TCP, ERP-prefixed commands, port 4532 by default
      |
+------------------+
|  rigctl_client       |   <-- thin async TCP client (this repo), no daemon of our own
+------------------+
      |
      v
+------------------+
|  rigctl_mcp           |   <-- MCP tools, stdio transport (same choice as the other two
+------------------+       sub-projects, same reasoning: launched as a subprocess by
                             the MCP client, no network exposure of its own)
```

## First-pass tool scope

- `get_status` — frequency, mode, VFO, PTT state in one call (multiple ERP commands
  combined, since an LLM caller usually wants "what's the rig doing" as one answer).
- `set_frequency(hz: int)`
- `set_mode(mode: str, passband_hz: int | None = None)`

**`set_ptt` is explicitly deferred, decided with Casey 2026-09-04** — it keys a transmitter,
and deserves its own discussion about safeguards (e.g. a required `confirm` flag) rather than
being added as a plain tool alongside the read/frequency/mode ones. Not in this pass.

Also deferred: `\dump_state`-derived rig-capability introspection, VFO-targeted multi-VFO
control, anything beyond a single default rig/connection.

## Verification

No `rigctld` instance is available in this environment (same gap `wsjtx-mcp` had with a real
WSJT-X instance). Plan: unit tests against a mocked TCP transport (same technique
`nanovna-mcp`'s `httpx.MockTransport` tests and `wsjtx-mcp`'s hand-built-datagram tests used,
adapted for a raw TCP line protocol), plus a manual end-to-end pass driving the real MCP
server against either a real `rigctld` (if available) or a small stub TCP server standing in
for one. Real-rig verification stays outstanding after that, same status as the other two
sub-projects' real-hardware gaps.

## Implementation plan (drafted 2026-09-04, plan-mode approved — not yet built)

This section is the finalized build plan from a plan-mode session with Casey. It's recorded
here (not just in Claude Code's own ephemeral plan-mode file, which gets overwritten by the
next planning session) so the build can resume later without re-deriving it. **Nothing below
has been implemented yet** — Casey asked to pause after planning and pick this back up later.

### Package layout

```
rigctl-mcp/
  rigctl_client/            # rigctld ERP protocol + TCP client, no MCP awareness
    __init__.py
    protocol.py               # build_command()/parse_response() -- pure functions, no I/O
    client.py                  # asyncio TCP client: persistent connection, one command at a
                                # time (guarded by an asyncio.Lock)
  rigctl_mcp/
    __init__.py
    __main__.py                 # `python -m rigctl_mcp` entry point, stdio transport
    server.py                   # MCP tool definitions, thin wrapper over rigctl_client
  tests/
    test_protocol.py             # build_command()/parse_response() against hand-built text,
                                  # no network
    test_client.py                # RigctlClient against a real local asyncio TCP server
                                   # stub (not a mock transport -- rigctld's protocol is a
                                   # raw line-based stream, not HTTP, so a small stand-in
                                   # server started on 127.0.0.1 in the test itself is the
                                   # simplest faithful double)
  pyproject.toml
```

Mirrors `nanovna-mcp`/`wsjtx-mcp`'s split (protocol/IO layer vs. MCP glue layer as separate
packages).

### `rigctl_client/protocol.py`

- `build_command(cmd: str, *args: str) -> bytes` — encodes `+{cmd} {arg1} {arg2}...\n` (ERP
  prefix, space-joined args, newline-terminated).
- `parse_response(lines: list[str]) -> ERPResponse` — given the full set of lines collected
  for one response (header line + zero or more `Key: value` lines + trailing `RPRT x`),
  returns a dataclass with the echoed command, a `dict[str, str]` of any `Key: value` pairs,
  and the return code. Raises `RigctlProtocolError` (caught by the client, not by tools
  directly) for a response that doesn't end in a parseable `RPRT` line.
- `RPRT_RE = re.compile(r"^RPRT (-?\d+)$")` used by both the parser (to find the terminating
  line) and the client (to know when to stop reading more lines from the stream).

### `rigctl_client/client.py`

`RigctlClient` — one persistent `asyncio` TCP connection to `rigctld` (default
`127.0.0.1:4532`, configurable), opened lazily on first command. `_send(cmd, *args) ->
ERPResponse`: under an `asyncio.Lock` (so concurrent tool calls don't interleave on the same
socket), writes `build_command(...)`, reads lines via the `StreamReader` until one matches
`RPRT_RE`, parses with `parse_response()`, and raises `RigctlError` (carrying the `RPRT` code
and the command that failed) if the code is nonzero.

Methods matching the in-scope tools:
- `get_status() -> dict` — issues `get_freq`, `get_mode`, `get_vfo`, `get_ptt` sequentially
  over the one connection, combines into one dict.
- `set_frequency(hz: int) -> None`
- `set_mode(mode: str, passband_hz: int | None = None) -> None`

`RigctlError` carries a clear message (e.g. `"set_freq failed: RPRT -1"` — mapped to a
human-readable Hamlib error description if practical, otherwise the raw code) — same
"caller-actionable message" intent as `nanovna-mcp`'s `DaemonError` and `wsjtx-mcp`'s
`ListenerError`.

### `rigctl_mcp/server.py` / `__main__.py`

Same shape as the other two sub-projects: `MCPServer("rigctl-mcp")`, stdio transport. Tools:

- `get_status()` — dial frequency, mode (+ passband), VFO, PTT state.
- `set_frequency(hz: int)`
- `set_mode(mode: str, passband_hz: int | None = None)`

Each tool catches `RigctlError` and re-raises as `mcp.server.mcpserver.exceptions.ToolError`
so the real `rigctld` error message reaches the calling model — same lesson from
`nanovna-mcp`'s Phase 4 (`MCPServer` only forwards `ToolError`'s own message; anything else
becomes a generic "Error executing tool X").

`__main__.py`: `argparse` for `--rigctld-host`/`--rigctld-port` (env var fallback
`RIGCTLD_HOST`/`RIGCTLD_PORT`, default `127.0.0.1`/`4532`), same CLI/env pattern as the other
two sub-projects, then `mcp.run()`.

### `pyproject.toml`

New package `rigctl-mcp`, dependency `mcp==2.1.1` (pinned exactly, matching `wsjtx-mcp`'s
pin — confirmed as still the current latest at implementation time before locking it in). No
`httpx` needed (raw TCP, not HTTP). Dev deps: `pytest>=8.0`, `pytest-asyncio>=0.24`. Console
script `rigctl-mcp = rigctl_mcp.__main__:main`.

### Tests

- `tests/test_protocol.py`: `build_command()` output for a few commands/arg counts;
  `parse_response()` against hand-built line lists for both the get-command shape
  (`Key: value` lines + `RPRT 0`) and the set-command shape (echoed value line + `RPRT 0`),
  plus a nonzero-`RPRT` case and a missing-`RPRT`-line (malformed) case.
- `tests/test_client.py`: a small `asyncio.start_server`-based stub standing in for `rigctld`
  in the test process itself (accepts a connection, replies with pre-scripted ERP responses
  per command) — exercises `RigctlClient.get_status()`/`set_frequency()`/`set_mode()` against
  it, including the nonzero-`RPRT`-raises-`RigctlError` case. No real `rigctld` or hardware
  needed.

No new test file for `server.py` — thin glue over already-tested `client.py`, verified
manually below (same reasoning the other two sub-projects' plans used).

### Verification steps (detail)

1. `pytest tests/ -v` — all tests pass.
2. Manual smoke test, same shape as `wsjtx-mcp`'s Phase 4: drive the MCP server over stdio
   with a real `ClientSession` (throwaway script). No real `rigctld` is available in this
   environment, so point the script's own small stub TCP server (same technique as
   `test_client.py`, reused rather than reinvented) at the MCP server's configured
   `--rigctld-host`/`--rigctld-port`, and confirm all 3 tools round-trip correctly, including
   the nonzero-`RPRT`-becomes-`ToolError` path.
3. Real-`rigctld` verification stays outstanding after this pass, same status as the other
   two sub-projects' real-hardware/real-instance gaps — tracked as a follow-up, not blocking.

### Phasing — approval gate after each

- **Phase 1 — `rigctl_client/protocol.py`**: re-confirm the exact ERP response grammar against
  `rigctld`'s manpage/source, implement `build_command()`/`parse_response()`,
  `tests/test_protocol.py`. Stop for approval before Phase 2.
- **Phase 2 — `rigctl_client/client.py`**: `RigctlClient` (persistent connection, lock-guarded
  commands, `get_status`/`set_frequency`/`set_mode`), `tests/test_client.py` against the
  in-process stub server. Stop for approval before Phase 3.
- **Phase 3 — `rigctl_mcp/server.py` / `__main__.py` / `pyproject.toml`**: 3 MCP tools, stdio
  transport, pinned `mcp` version, console script. Stop for approval before Phase 4.
- **Phase 4 — verification**: run the server against the stub `rigctld`, drive it via a stdio
  `ClientSession`, confirm each tool including the error path. Report results; done after this.

### Not in this pass

- `set_ptt` (deferred — needs its own safeguards discussion; see "First-pass tool scope").
- `\dump_state`-derived rig-capability introspection.
- VFO-targeted multi-VFO control.
- Real-`rigctld`/real-rig verification (in-process stub server only, this pass).

## Next step

Implementation plan above is finalized and approved but **not yet built** — resume with
Phase 1 when Casey is ready.
