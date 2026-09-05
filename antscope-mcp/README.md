# antscope-mcp

Future MCP server (and possibly companion webapp) for driving the AntScopeZ desktop
application itself, once it exposes an API — **that API doesn't exist yet and is being
designed/built separately, in the `AntScopeZ` repo.** See [`PLAN.md`](./PLAN.md).

**Not to be confused with [`nanovna-mcp`](../nanovna-mcp)** — that's a separate, fully
decoupled sub-project in this same repo for direct NanoVNA hardware control over serial. The
two were briefly coupled in an earlier planning pass (see `PLAN.md`'s `## History`); that was
a mistake, corrected 2026-09-03. `antscope-mcp` has no dependency on `nanovna-mcp`.

Status: blocked — waiting on an AntScopeZ application API that doesn't exist yet.
