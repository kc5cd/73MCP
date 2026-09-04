# 73MCP

A collection of [Model Context Protocol](https://modelcontextprotocol.io) servers for
Amateur Radio software, letting AI assistants interact with the tools hams already use.

## Sub-projects

| Folder | Target software | Status |
|---|---|---|
| [`wsjtx-mcp`](./wsjtx-mcp) | [WSJT-X](https://wsjt.sourceforge.io/) | planned |
| [`antscope-mcp`](./antscope-mcp) | Future MCP server for the AntScopeZ app's own API (not yet defined/built) | blocked — waiting on that API |
| [`rigctl-mcp`](./rigctl-mcp) | Hamlib `rigctl` | planned |
| [`nanovna-mcp`](./nanovna-mcp) | NanoVNA hardware, direct serial (own standalone API daemon) | daemon implemented (`nanovna-mcp` branch); MCP server + webapp not started |

Each sub-project is self-contained with its own build/run instructions in its own README.

## License

MIT — see [LICENSE](./LICENSE).
