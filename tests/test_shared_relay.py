"""The host relay must not follow a substituted socket into host services."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import shared_no_sudo as shared


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_state = shared.STATE
        self.old_namespace = shared.SANDBOX_PID_NAMESPACE
        shared.STATE = Path(self.temp.name)
        (shared.STATE / 'sockets').mkdir()
        self.received = asyncio.Queue()
        async def echo(reader, writer):
            try:
                data = await reader.read(100)
                await self.received.put(data)
                if data:
                    writer.write(data)
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        self.unix = await asyncio.start_unix_server(echo, path=str(shared.STATE / 'sockets/jupyter.sock'))
        self.bridge = await asyncio.start_server(shared.relay, '127.0.0.1', 0)
        self.port = self.bridge.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        for server in [self.bridge, self.unix]:
            server.close()
            await server.wait_closed()
        shared.STATE = self.old_state
        shared.SANDBOX_PID_NAMESPACE = self.old_namespace
        self.temp.cleanup()

    async def request(self, value):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        try:
            writer.write(value)
            await writer.drain()
            return await asyncio.wait_for(reader.read(), 3)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_matching_namespace_relays_bytes(self):
        shared.SANDBOX_PID_NAMESPACE = str(Path('/proc/self/ns/pid').readlink())
        self.assertEqual(await self.request(b'hello'), b'hello')
        self.assertEqual(await asyncio.wait_for(self.received.get(), 3), b'hello')

    async def test_other_namespace_receives_no_request_bytes(self):
        shared.SANDBOX_PID_NAMESPACE = 'pid:[not-the-peer]'
        self.assertEqual(await self.request(b'private-request'), b'')
        self.assertEqual(await asyncio.wait_for(self.received.get(), 3), b'')


if __name__ == '__main__':
    unittest.main()
