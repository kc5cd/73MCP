# 73MCP

A collection of [Model Context Protocol](https://modelcontextprotocol.io) servers for
Amateur Radio software, letting AI assistants interact with the tools hams already use.

## Sub-projects

| Folder | Target software | Status |
|---|---|---|
| [`wsjtx-mcp`](./wsjtx-mcp) | [WSJT-X](https://wsjt.sourceforge.io/) | planned |
| [`antscope-mcp`](./antscope-mcp) | NanoVNA data via a remote API (API daemon lives in the `AntScopeZ` repo's `remote-api` branch) | plan written; MCP server + webapp not started |
| [`rigctl-mcp`](./rigctl-mcp) | Hamlib `rigctl` | planned |
| [`nanovna-mcp`](./nanovna-mcp) | *(reserved for a separate, unrelated future effort)* | planned |

Each sub-project is self-contained with its own build/run instructions in its own README.

## License

MIT — see [LICENSE](./LICENSE).
