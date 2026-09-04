# rigctl-mcp

MCP server for [Hamlib](https://github.com/Hamlib/Hamlib)'s `rigctl`/`rigctld` rig-control
interface, so an MCP client can query and drive a transceiver (frequency, mode, PTT, and the
rest of Hamlib's `set`/`get` command set) without talking to the radio's own vendor protocol
directly. Hamlib already normalizes that part across hundreds of rig models — this project's
job is only the MCP-facing layer on top of it.

## Status

Language/runtime and protocol approach decided (Python, talking to an already-running
`rigctld` over its TCP protocol — see `PLAN.md`), implementation not yet started. Next step is
a plan-mode session to finalize tool scope/phasing, same process `wsjtx-mcp` and
`nanovna-mcp` went through.
