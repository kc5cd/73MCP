# rigctl-mcp

MCP server for [Hamlib](https://github.com/Hamlib/Hamlib)'s `rigctl`/`rigctld` rig-control
interface, so an MCP client can query and drive a transceiver (frequency, mode, PTT, and the
rest of Hamlib's `set`/`get` command set) without talking to the radio's own vendor protocol
directly. Hamlib already normalizes that part across hundreds of rig models — this project's
job is only the MCP-facing layer on top of it.

Two ways this could talk to Hamlib, to be decided before implementation starts:
- **`rigctld`'s TCP command protocol** — connect to an already-running `rigctld` daemon
  (`localhost:4532` by default), same approach `nanovna-mcp` took toward its own daemon (no
  serial-port ownership in this process).
- **Hamlib's C API via a Python binding** (`Hamlib` module, SWIG-generated) — talks to the rig
  directly, no separate daemon process required.

## Status

Planned, not yet implemented. No language/runtime, protocol approach, or tool scope has been
decided yet — those need their own plan-mode session (same process `wsjtx-mcp` and
`nanovna-mcp` went through) before any code gets written.
