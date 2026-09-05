"""Run the rigctl-mcp MCP server: `python -m rigctl_mcp` or the `rigctl-mcp`
console script installed by pyproject.toml.

Talks to an already-running rigctld over its TCP Extended Response Protocol
-- it never spawns rigctld itself. Start rigctld separately first (e.g.
`rigctld -m <model> -r <device>`), then point this at its host/port.
"""

from __future__ import annotations

import argparse
import os

from rigctl_client import DEFAULT_HOST, DEFAULT_MAX_PTT_SECONDS, DEFAULT_PORT


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


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
    parser.add_argument(
        "--allow-ptt",
        action="store_true",
        default=_env_flag("RIGCTL_ALLOW_PTT"),
        help="enable the set_ptt tool (off by default -- it keys a transmitter)",
    )
    parser.add_argument(
        "--max-ptt-seconds",
        type=float,
        default=float(os.environ.get("RIGCTL_MAX_PTT_SECONDS", DEFAULT_MAX_PTT_SECONDS)),
        help="auto-unkey watchdog: seconds after set_ptt(True) before it's forced back off if "
        f"set_ptt(False) never arrives (default {DEFAULT_MAX_PTT_SECONDS}s -- long enough for "
        "most digital modes' transmit cycles, e.g. WSPR's ~110s; only matters with --allow-ptt)",
    )
    args = parser.parse_args()
    os.environ["RIGCTLD_HOST"] = args.rigctld_host
    os.environ["RIGCTLD_PORT"] = str(args.rigctld_port)
    os.environ["RIGCTL_ALLOW_PTT"] = "1" if args.allow_ptt else ""
    os.environ["RIGCTL_MAX_PTT_SECONDS"] = str(args.max_ptt_seconds)

    from .server import mcp  # imported after the env vars are set, so _get_client() picks them up

    mcp.run()


if __name__ == "__main__":
    main()
