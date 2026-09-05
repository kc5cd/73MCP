import pytest

from rigctl_client.protocol import ERPResponse, RigctlProtocolError, build_command, parse_response


def test_build_command_no_args():
    assert build_command("\\get_freq") == b"+\\get_freq\n"


def test_build_command_one_arg():
    assert build_command("F", "14074000") == b"+F 14074000\n"


def test_build_command_multiple_args():
    assert build_command("M", "USB", "2400") == b"+M USB 2400\n"


def test_parse_get_response_multiple_values():
    lines = ["get_mode:", "Mode: USB", "Passband: 2400", "RPRT 0"]
    resp = parse_response(lines)
    assert resp == ERPResponse(
        command="get_mode",
        echoed_args="",
        values={"Mode": "USB", "Passband": "2400"},
        rprt=0,
    )


def test_parse_get_response_single_value():
    lines = ["get_freq:", "Frequency: 14074000", "RPRT 0"]
    resp = parse_response(lines)
    assert resp.values == {"Frequency": "14074000"}
    assert resp.rprt == 0


def test_parse_set_response():
    lines = ["set_freq: 14074000", "RPRT 0"]
    resp = parse_response(lines)
    assert resp == ERPResponse(command="set_freq", echoed_args="14074000", values={}, rprt=0)


def test_parse_set_response_multiple_echoed_args():
    lines = ["set_mode: USB 2400", "RPRT 0"]
    resp = parse_response(lines)
    assert resp.command == "set_mode"
    assert resp.echoed_args == "USB 2400"


def test_parse_nonzero_rprt_does_not_raise():
    lines = ["set_freq: 14074000", "RPRT -1"]
    resp = parse_response(lines)
    assert resp.rprt == -1


def test_parse_empty_response_raises():
    with pytest.raises(RigctlProtocolError):
        parse_response([])


def test_parse_missing_rprt_line_raises():
    with pytest.raises(RigctlProtocolError):
        parse_response(["get_mode:", "Mode: USB", "Passband: 2400"])


def test_parse_malformed_key_value_line_raises():
    with pytest.raises(RigctlProtocolError):
        parse_response(["get_mode:", "not a key value line", "RPRT 0"])


def test_parse_malformed_header_line_raises():
    with pytest.raises(RigctlProtocolError):
        parse_response(["no colon here", "RPRT 0"])
