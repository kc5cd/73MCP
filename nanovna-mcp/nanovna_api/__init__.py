"""nanovna_api -- serial protocol owner and local network API for NanoVNA antenna analyzers.

Lives on the `remote-api` branch (off `master`, deliberately separate from
`windows-port`) because this is general project functionality, not
Windows-specific or tied to the desktop app's Qt UI. See README.md in
this directory for the design and API contract; consumed by the
`antscope-mcp` sub-project of the separate `73MCP` repo (MCP server) and
a future companion webapp, both as HTTP/WebSocket clients -- neither is
part of this repo.
"""

__version__ = "0.1.0"
