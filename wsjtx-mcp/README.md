# wsjtx-mcp

MCP server for [WSJT-X](https://wsjt.sourceforge.io/), exposing its live UDP protocol
(station status, decodes, logged QSOs) to MCP clients.

Status: implemented and verified (no real WSJT-X instance yet — synthetic UDP traffic only,
see `PLAN.md`'s "Verification" section). No daemon: this process binds WSJT-X's UDP feed
itself.

## Running

1. In WSJT-X: Settings → Reporting → enable "UDP Server" (default `127.0.0.1` port `2237`,
   which is also this server's default).
2. `pip install -e .` (from this folder) to install `wsjtx-mcp` and its pinned `mcp` SDK.
3. Run the MCP server: `python -m wsjtx_mcp` (or the `wsjtx-mcp` console script). Point an MCP
   client at it over stdio. Override the bind address with `--udp-host`/`--udp-port` or the
   `WSJTX_UDP_HOST`/`WSJTX_UDP_PORT` env vars if WSJT-X's UDP Server setting isn't the default.

## Tools

- `get_status` — most recent Status (dial frequency, mode, DX call/grid, Tx/Rx state).
- `get_recent_decodes` — buffered Band Activity decode lines, most recent first.
- `get_recent_qsos` — buffered logged QSOs this session, most recent first.

All three take an optional `instance_id` if more than one WSJT-X instance is running and has
been heard from; the error message lists known ids when disambiguation is needed.

See `PLAN.md` for the protocol/architecture background and what's deliberately out of scope
for this pass (sending anything back to WSJT-X, WSPR-specific handling, ADIF log-file access).
