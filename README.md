# 73MCP

A collection of [Model Context Protocol](https://modelcontextprotocol.io) servers for
Amateur Radio software, letting AI assistants interact with the tools hams already use.

## Sub-projects

| Folder | Target software | Status |
|---|---|---|
| [`wsjtx-mcp`](./wsjtx-mcp) | [WSJT-X](https://wsjt.sourceforge.io/) | built, verified against synthetic traffic (real-WSJT-X verification outstanding) |
| [`antscope-mcp`](./antscope-mcp) | Future MCP server for the AntScopeZ app's own API (not yet defined/built) | blocked — waiting on that API |
| [`rigctl-mcp`](./rigctl-mcp) | Hamlib `rigctl` | built, verified against a stub `rigctld` (real-`rigctld` verification outstanding) |
| [`nanovna-mcp`](./nanovna-mcp) | NanoVNA hardware, direct serial (own standalone API daemon) | daemon, MCP server, and webapp all built; verified against real hardware once |

Each sub-project is self-contained with its own build/run instructions in its own README.

## License

MIT — see [LICENSE](./LICENSE).
