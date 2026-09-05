"""Run the rigctl-mcp MCP server: `python -m rigctl_mcp` or the `rigctl-mcp`
console script installed by pyproject.toml.

Talks to an already-running rigctld over its TCP Extended Response Protocol
-- it never spawns rigctld itself. Start rigctld separately first (e.g.
`rigctld -m <model> -r <device>`), then point this at its host/port.
"""

from __future__ import annotations

import argparse
import os

from rigctl_client import DEFAULT_HOST, DEFAULT_PORT


def main() -> None:
    parser = argparse.ArgumentParser(description="rigctl-mcp MCP server (stdio transport)")
    parser.add_argument(
        "--rigctld-host",
        default=os.environ.get("RIGCTLD_HOST", DEFAULT_HOST),
        help=f"host of a running rigctld instance (default {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--rigctld-port",
        type=int,
        default=int(os.environ.get("RIGCTLD_PORT", DEFAULT_PORT)),
        help=f"port of a running rigctld instance (default {DEFAULT_PORT})",
    )
    args = parser.parse_args()
    os.environ["RIGCTLD_HOST"] = args.rigctld_host
    os.environ["RIGCTLD_PORT"] = str(args.rigctld_port)

    from .server import mcp  # imported after the env vars are set, so _get_client() picks them up

    mcp.run()


if __name__ == "__main__":
    main()
