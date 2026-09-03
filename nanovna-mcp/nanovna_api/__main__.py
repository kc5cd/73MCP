"""Run the nanovna-api daemon: `python -m nanovna_api` or the
`nanovna-api` console script installed by pyproject.toml.
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="nanovna-api daemon")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="bind address (default 0.0.0.0 -- LAN-visible, per PLAN.md's v1 deployment scope)",
    )
    parser.add_argument("--port", type=int, default=8765, help="TCP port (default 8765)")
    args = parser.parse_args()

    uvicorn.run("nanovna_api.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
