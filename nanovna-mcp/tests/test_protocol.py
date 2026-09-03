"""Unit tests for nanovna_api.protocol -- no hardware required.

Note: the "confirmed-working example" cited in PLAN.md (sweep
420-540MHz, SWR ~3.0/1.05/2.8) was captured as derived SWR values only;
the raw re/im lines from that session were never saved, so it can't be
used as a byte-exact fixture here. Instead these tests check the
impedance/SWR math against well-known analytic reference points (open,
short, matched load) that are independently verifiable, plus the line
parsers against both well-formed and malformed input.
"""

import math

from nanovna_api import protocol


def test_parse_re_im_well_formed():
    assert protocol.parse_re_im("0.5 -0.25") == complex(0.5, -0.25)


def test_parse_re_im_malformed_is_permissive():
    # Mirrors NanovnaAnalyzer::parseReIm()'s own tolerance: a bad line
    # yields 0+0j rather than raising, so one garbage line doesn't abort
    # an entire sweep.
    assert protocol.parse_re_im("") == complex(0, 0)
    assert protocol.parse_re_im("garbage") == complex(0, 0)
    assert protocol.parse_re_im("not a number") == complex(0, 0)


def test_parse_frequency_hz():
    assert protocol.parse_frequency_hz("468000000") == 468000000.0
    assert protocol.parse_frequency_hz("garbage") == 0.0


def test_impedance_matched_load():
    # Gamma = 0 -> perfectly matched, Z = Z0 exactly.
    z = protocol.impedance_from_reflection(complex(0, 0))
    assert math.isclose(z.real, 50.0)
    assert math.isclose(z.imag, 0.0, abs_tol=1e-9)


def test_impedance_open_circuit():
    # Gamma = 1 -> open circuit, R -> infinity.
    z = protocol.impedance_from_reflection(complex(1, 0))
    assert math.isinf(z.real)


def test_impedance_short_circuit():
    # Gamma = -1 -> short circuit, Z = 0.
    z = protocol.impedance_from_reflection(complex(-1, 0))
    assert math.isclose(z.real, 0.0, abs_tol=1e-9)
    assert math.isclose(z.imag, 0.0, abs_tol=1e-9)


def test_swr_matched_load():
    assert math.isclose(protocol.swr_from_reflection(complex(0, 0)), 1.0)


def test_swr_known_magnitude():
    # |Gamma| = 0.5 -> SWR = (1+0.5)/(1-0.5) = 3.0 -- same order of
    # magnitude as the real 420MHz-edge SWR (~3.0:1) cited in PLAN.md,
    # a useful sanity anchor even without the exact captured re/im.
    assert math.isclose(protocol.swr_from_reflection(complex(0.5, 0.0)), 3.0)


def test_swr_full_reflection_is_infinite():
    assert math.isinf(protocol.swr_from_reflection(complex(1, 0)))


def test_make_sweep_point_to_dict_shape():
    point = protocol.make_sweep_point(freq_hz=468000000.0, s11=complex(0.02, 0.01), s21=complex(0.9, 0.0))
    d = point.to_dict()
    assert d["freq_hz"] == 468000000.0
    assert set(d["s11"]) == {"re", "im"}
    assert set(d["s21"]) == {"re", "im"}
    assert set(d["impedance"]) == {"r", "x"}
    assert isinstance(d["swr"], float)


def test_make_sweep_point_without_s21_omits_it():
    point = protocol.make_sweep_point(freq_hz=468000000.0, s11=complex(0.02, 0.01), s21=None)
    d = point.to_dict()
    assert "s21" not in d
