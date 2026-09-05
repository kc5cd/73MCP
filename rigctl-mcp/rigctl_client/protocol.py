"""Pure encode/decode for rigctld's Extended Response Protocol (ERP).

No I/O here -- see client.py for the TCP connection that actually talks to
rigctld. Grammar confirmed against rigctld(1):
https://hamlib.sourceforge.net/html/rigctld.1.html

A `+`-prefixed command gets a response shaped as:
  - one header line: the long command name echoed, followed by ": " and any
    argument values for a set command (e.g. "set_freq: 14074000"), or just
    "get_mode:" with nothing after the colon for a get command.
  - zero or more "Key: value" lines (get commands only).
  - a terminating "RPRT x" line, x = 0 on success, a negative Hamlib error
    code otherwise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

RPRT_RE = re.compile(r"^RPRT (-?\d+)$")


class RigctlProtocolError(Exception):
    """A rigctld response did not match the expected ERP grammar."""


@dataclass
class ERPResponse:
    command: str
    echoed_args: str
    values: dict[str, str] = field(default_factory=dict)
    rprt: int = 0


def build_command(cmd: str, *args: str) -> bytes:
    """Encode one ERP command line, e.g. build_command(r"\\get_freq") or
    build_command("F", "14074000")."""
    return ("+" + " ".join((cmd, *args)) + "\n").encode("ascii")


def parse_response(lines: list[str]) -> ERPResponse:
    """Parse the full set of lines collected for one ERP response.

    `lines` must already have line endings stripped and must include the
    terminating RPRT line as its last element.
    """
    if not lines:
        raise RigctlProtocolError("empty response")

    rprt_match = RPRT_RE.match(lines[-1])
    if rprt_match is None:
        raise RigctlProtocolError(f"response missing terminating RPRT line: {lines!r}")
    rprt = int(rprt_match.group(1))

    command, sep, echoed_args = lines[0].partition(":")
    if not sep:
        raise RigctlProtocolError(f"malformed header line: {lines[0]!r}")
    command = command.strip()
    echoed_args = echoed_args.strip()

    values: dict[str, str] = {}
    for line in lines[1:-1]:
        key, sep, value = line.partition(":")
        if not sep:
            raise RigctlProtocolError(f"malformed key/value line: {line!r}")
        values[key.strip()] = value.strip()

    return ERPResponse(command=command, echoed_args=echoed_args, values=values, rprt=rprt)
