"""Run the nanovna-mcp MCP server: `python -m nanovna_mcp` or the
`nanovna-mcp` console script installed by pyproject.toml.

Talks to an already-running nanovna-api daemon over HTTP -- it never opens
the NanoVNA's serial port itself. Start the daemon separately first
(`python -m nanovna_api`, see nanovna-mcp/README.md).
"""

from __future__ import annotations

import argparse
import os

from .client import DEFAULT_DAEMON_URL


def main() -> None:
    parser = argparse.ArgumentParser(description="nanovna-mcp MCP server (stdio transport)")
    parser.add_argument(
        "--daemon-url",
        default=os.environ.get("NANOVNA_DAEMON_URL", DEFAULT_DAEMON_URL),
        help=f"base URL of a running nanovna-api daemon (default {DEFAULT_DAEMON_URL})",
    )
    args = parser.parse_args()
    os.environ["NANOVNA_DAEMON_URL"] = args.daemon_url

    from .server import mcp  # imported after the env var is set, so _get_client() picks it up

    mcp.run()


if __name__ == "__main__":
    main()
