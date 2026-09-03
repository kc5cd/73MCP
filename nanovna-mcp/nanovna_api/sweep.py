"""Sweep orchestration: drives the sweep/frequencies/data 0/data 1
command sequence and yields SweepPoints as they arrive.

Synchronous by design (matches device.py) -- api.py bridges this to
async consumers (the REST handler collects the full generator; the
WebSocket handler forwards each point as it's yielded).
"""

from __future__ import annotations

from collections.abc import Iterator

from . import protocol
from .device import NanovnaDevice


def get_device_info(device: NanovnaDevice) -> str:
    device.send_command(protocol.info_command())
    lines = device.read_until_prompt()
    return "\n".join(lines)


def run_sweep(device: NanovnaDevice, start_hz: int, stop_hz: int, points: int) -> Iterator[protocol.SweepPoint]:
    """Run one sweep, yielding SweepPoints as S21 data (or S11-only,
    if S21 isn't available) arrives for each frequency point.

    Sequence mirrors AntScopeZ's own parser exactly (see PLAN.md's
    protocol reference): configure the sweep, fetch the frequency list,
    fetch the S11 pass in full, then fetch the S21 pass -- yielding a
    complete point the moment each S21 line arrives, since by then both
    its frequency and S11 value are already known from the earlier
    passes. This is what gives a WebSocket stream real incremental
    points instead of one big blob at the end.
    """
    device.send_command(protocol.sweep_command(start_hz, stop_hz, points))
    device.read_until_prompt()  # sweep config has no data payload to capture

    device.send_command(protocol.frequencies_command())
    freqs = [protocol.parse_frequency_hz(line) for line in device.read_until_prompt()]

    device.send_command(protocol.data_command(0))
    s11_values = [protocol.parse_re_im(line) for line in device.read_until_prompt()]

    n = min(len(freqs), len(s11_values))

    device.send_command(protocol.data_command(1))
    yielded = 0
    while True:
        line = device.read_line()
        if protocol.PROMPT_MARKER in line or line == "":
            break
        if yielded >= n:
            continue  # more S21 lines than frequency/S11 points -- ignore the stray line
        s21 = protocol.parse_re_im(line)
        yield protocol.make_sweep_point(freqs[yielded], s11_values[yielded], s21)
        yielded += 1

    # Firmware without S21 support replies to "data 1" with nothing (or
    # fewer lines than the sweep has points) -- yield the remaining
    # points S11-only rather than silently dropping them.
    for i in range(yielded, n):
        yield protocol.make_sweep_point(freqs[i], s11_values[i], None)
