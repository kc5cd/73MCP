"""RigctlClient against a small in-process asyncio TCP stub standing in for
rigctld -- its ERP is a raw line-based stream, not HTTP, so a real stand-in
socket server is the simplest faithful double (no mock transport)."""

import asyncio
import contextlib

import pytest
import pytest_asyncio

from rigctl_client.client import RigctlClient, RigctlError

pytestmark = pytest.mark.asyncio

RESPONSES = {
    "+\\get_freq": ["get_freq:", "Frequency: 14074000", "RPRT 0"],
    "+\\get_mode": ["get_mode:", "Mode: USB", "Passband: 2400", "RPRT 0"],
    "+\\get_vfo": ["get_vfo:", "VFO: VFOA", "RPRT 0"],
    "+\\get_ptt": ["get_ptt:", "PTT: 0", "RPRT 0"],
    "+F 14074000": ["set_freq: 14074000", "RPRT 0"],
    "+M USB 2400": ["set_mode: USB 2400", "RPRT 0"],
    "+F -1": ["set_freq: -1", "RPRT -1"],
}


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            raw = await reader.readline()
            if not raw:
                break
            cmd = raw.decode("ascii").rstrip("\r\n")
            for line in RESPONSES.get(cmd, ["RPRT -11"]):
                writer.write((line + "\n").encode("ascii"))
            await writer.drain()
    finally:
        writer.close()


@pytest_asyncio.fixture
async def stub_rigctld():
    server = await asyncio.start_server(_handle, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    serve_task = asyncio.create_task(server.serve_forever())
    try:
        yield host, port
    finally:
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task
        server.close()
        await server.wait_closed()


async def test_get_status(stub_rigctld):
    host, port = stub_rigctld
    client = RigctlClient(host, port)
    try:
        status = await client.get_status()
    finally:
        await client.close()
    assert status == {
        "frequency_hz": 14074000,
        "mode": "USB",
        "passband_hz": 2400,
        "vfo": "VFOA",
        "ptt": 0,
    }


async def test_set_frequency(stub_rigctld):
    host, port = stub_rigctld
    client = RigctlClient(host, port)
    try:
        await client.set_frequency(14074000)
    finally:
        await client.close()


async def test_set_mode(stub_rigctld):
    host, port = stub_rigctld
    client = RigctlClient(host, port)
    try:
        await client.set_mode("USB", 2400)
    finally:
        await client.close()


async def test_nonzero_rprt_raises_rigctl_error(stub_rigctld):
    host, port = stub_rigctld
    client = RigctlClient(host, port)
    try:
        with pytest.raises(RigctlError) as exc_info:
            await client.set_frequency(-1)
        assert exc_info.value.rprt == -1
        assert exc_info.value.command == "set_freq"
    finally:
        await client.close()


async def test_connection_reused_across_calls(stub_rigctld):
    host, port = stub_rigctld
    client = RigctlClient(host, port)
    try:
        await client.set_frequency(14074000)
        writer_after_first = client._writer
        await client.set_mode("USB", 2400)
        assert client._writer is writer_after_first
    finally:
        await client.close()
