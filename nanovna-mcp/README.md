# nanovna-mcp

Local network API daemon + MCP server for NanoVNA antenna analyzers, talking directly to
the device's serial protocol (no dependency on AntScopeZ or any other desktop app).

See [`PLAN.md`](./PLAN.md) for the full design: architecture, protocol reference, and the
API contract the MCP server and a companion webapp build against.

## Status

- **`nanovna_api/`** — the daemon (serial protocol owner + REST/WebSocket API): **implemented**.
  Unit-tested (`tests/`, no hardware required) and smoke-tested against the running daemon
  (`/status`, `/devices`, error paths for not-connected/bad-port). **Not yet verified against
  real NanoVNA hardware** — no device was connected when this was built; run the manual
  verification step in `PLAN.md` once one is available.
- **MCP server** — planned, not yet implemented (a separate effort — see `PLAN.md`'s
  "Division of labor").
- **Webapp** — planned, not yet implemented (same).

## Running the daemon

```
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m nanovna_api --host 0.0.0.0 --port 8765
```

Then, e.g.:

```
curl http://<host>:8765/devices
curl http://<host>:8765/status
curl -X POST http://<host>:8765/connect -H "Content-Type: application/json" -d "{\"port\":\"COM20\"}"
curl -X POST http://<host>:8765/sweep -H "Content-Type: application/json" -d "{\"start_hz\":420000000,\"stop_hz\":540000000,\"points\":101}"
```

## Tests

```
.venv\Scripts\python -m pytest tests/ -v
```
