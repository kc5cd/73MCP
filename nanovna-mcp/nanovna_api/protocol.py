"""NanoVNA serial wire protocol: command strings, line parsing, and the
reflection-coefficient-to-impedance/SWR math.

Ported from AntScopeZ's C++ reference implementation
(analyzer/nanovna_analyzer.cpp in the AntScopeZ repo) -- see PLAN.md's
"Protocol reference" section for the command sequence and citations.
Only the classic ASCII sweep/frequencies/data path is implemented here
(proven working against real hardware); the newer binary "scan" fast
path is not needed for v1 and is left for a future addition.
"""

from __future__ import annotations

from dataclasses import dataclass

# USB identification (analyzer/nanovna_analyzer.h in AntScopeZ).
USB_VID = 0x0483
USB_PID = 0x5740

# The NanoVNA's shell-style prompt. Every command's reply is terminated
# by a line containing this -- read_until_prompt() in device.py uses it
# as the sole end-of-reply marker, mirroring AntScopeZ's own parser
# (which never assumes a fixed reply line count either).
PROMPT_MARKER = "ch>"

Z0 = 50.0  # reference impedance (ohms)


def info_command() -> str:
    return "info\r\n"


def sweep_command(start_hz: int, stop_hz: int, points: int) -> str:
    return f"sweep {start_hz} {stop_hz} {points}\r\n"


def frequencies_command() -> str:
    return "frequencies\r\n"


def data_command(channel: int) -> str:
    """channel: 0 for S11 (reflection), 1 for S21 (through)."""
    return f"data {channel}\r\n"


def parse_re_im(line: str) -> complex:
    """Parse a "data 0"/"data 1" reply line: "<re> <im>" -> complex.

    Mirrors NanovnaAnalyzer::parseReIm() (analyzer/nanovna_analyzer.cpp
    in AntScopeZ): permissive, a malformed line yields 0+0j rather than
    raising, matching the reference implementation's own tolerance for
    the occasional short/garbage line.
    """
    tok = line.split()
    if len(tok) < 2:
        return complex(0, 0)
    try:
        return complex(float(tok[0]), float(tok[1]))
    except ValueError:
        return complex(0, 0)


def parse_frequency_hz(line: str) -> float:
    """Parse a "frequencies" reply line (a single Hz value) -> float.

    Permissive like parse_re_im() -- an unparsable line yields 0.0
    rather than raising, so one bad line doesn't abort an entire sweep.
    """
    try:
        return float(line.strip())
    except ValueError:
        return 0.0


def impedance_from_reflection(gamma: complex, z0: float = Z0) -> complex:
    """50-ohm-reference impedance from a reflection coefficient.

    Exactly NanovnaAnalyzer::impedanceFromReflection()
    (analyzer/nanovna_analyzer.cpp in AntScopeZ) ported to Python --
    that function itself was added to deduplicate two copies of this
    same formula in the C++ reference implementation.
    """
    re, im = gamma.real, gamma.imag
    denom = (1 - re) ** 2 + im ** 2
    if denom == 0:
        return complex(float("inf"), float("inf"))
    r = (1 - re * re - im * im) / denom * z0
    x = (2 * im) / denom * z0
    return complex(r, x)


def swr_from_reflection(gamma: complex) -> float:
    """Voltage standing wave ratio from a reflection coefficient magnitude."""
    mag = abs(gamma)
    if mag >= 1:
        return float("inf")
    return (1 + mag) / (1 - mag)


@dataclass
class SweepPoint:
    freq_hz: float
    s11: complex
    s21: complex | None
    impedance: complex
    swr: float

    def to_dict(self) -> dict:
        d = {
            "freq_hz": self.freq_hz,
            "s11": {"re": self.s11.real, "im": self.s11.imag},
            "impedance": {"r": self.impedance.real, "x": self.impedance.imag},
            "swr": self.swr,
        }
        if self.s21 is not None:
            d["s21"] = {"re": self.s21.real, "im": self.s21.imag}
        return d


def make_sweep_point(freq_hz: float, s11: complex, s21: complex | None) -> SweepPoint:
    return SweepPoint(
        freq_hz=freq_hz,
        s11=s11,
        s21=s21,
        impedance=impedance_from_reflection(s11),
        swr=swr_from_reflection(s11),
    )
