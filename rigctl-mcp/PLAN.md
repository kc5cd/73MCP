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

## Likely first-pass tool scope (to be finalized in a plan-mode session)

- `get_status` — frequency, mode, VFO, PTT state in one call (multiple ERP commands
  combined, since an LLM caller usually wants "what's the rig doing" as one answer).
- `set_frequency(hz: int)`
- `set_mode(mode: str, passband_hz: int | None = None)`
- `set_ptt(on: bool)` — likely gated behind explicit confirmation semantics given this
  actually keys a transmitter; needs discussion before it's in scope, not assumed here.

Deferred: `\dump_state`-derived rig-capability introspection, VFO-targeted multi-VFO control,
anything beyond a single default rig/connection.

## Verification

No `rigctld` instance is available in this environment (same gap `wsjtx-mcp` had with a real
WSJT-X instance). Plan: unit tests against a mocked TCP transport (same technique
`nanovna-mcp`'s `httpx.MockTransport` tests and `wsjtx-mcp`'s hand-built-datagram tests used,
adapted for a raw TCP line protocol), plus a manual end-to-end pass driving the real MCP
server against either a real `rigctld` (if available) or a small stub TCP server standing in
for one. Real-rig verification stays outstanding after that, same status as the other two
sub-projects' real-hardware gaps.

## Next step

This document records the language/runtime/protocol decision and rough shape only. Actual
implementation should go through the same plan-mode scope/design/phasing process
`wsjtx-mcp` and `nanovna-mcp` did before writing code.
