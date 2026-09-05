"""Run the wsjtx-mcp MCP server: `python -m wsjtx_mcp` or the `wsjtx-mcp`
console script installed by pyproject.toml.

Binds WSJT-X's UDP feed itself (default 127.0.0.1:2237, matching WSJT-X's
own out-of-the-box UDP Server setting) -- there's no separate daemon to
start first, unlike nanovna-mcp.
"""

from __future__ import annotations

import argparse
import os

from .server import DEFAULT_UDP_HOST, DEFAULT_UDP_PORT


def main() -> None:
    parser = argparse.ArgumentParser(description="wsjtx-mcp MCP server (stdio transport)")
    parser.add_argument(
        "--udp-host",
        default=os.environ.get("WSJTX_UDP_HOST", DEFAULT_UDP_HOST),
        help=f"address to bind for WSJT-X's UDP feed (default {DEFAULT_UDP_HOST})",
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=int(os.environ.get("WSJTX_UDP_PORT", DEFAULT_UDP_PORT)),
        help=f"port to bind for WSJT-X's UDP feed (default {DEFAULT_UDP_PORT})",
    )
    args = parser.parse_args()
    os.environ["WSJTX_UDP_HOST"] = args.udp_host
    os.environ["WSJTX_UDP_PORT"] = str(args.udp_port)

    from .server import mcp  # imported after the env vars are set, so the lifespan picks them up

    mcp.run()


if __name__ == "__main__":
    main()
