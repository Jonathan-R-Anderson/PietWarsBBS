import asyncio
import logging
import os
import pty
import sys
from pathlib import Path

import telnetlib3

SRC_ROOT = Path(__file__).resolve().parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from logging_config import setup_logging

HOST = '0.0.0.0'
PORT = 1337

logger = setup_logging(__name__)

async def run_app(reader: telnetlib3.TelnetReader, writer: telnetlib3.TelnetWriter) -> None:
    logger.debug("Opening pty for BBS subprocess")
    master_fd, slave_fd = pty.openpty()
    bbs_path = os.path.join(os.path.dirname(__file__), 'bbs_app.py')
    env = os.environ.copy()
    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    env['PYTHONPATH'] = os.pathsep.join([src_root, env.get('PYTHONPATH', '')])
    logger.debug("Launching BBS application %s", bbs_path)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        bbs_path,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
    )
    logger.debug("BBS subprocess started with PID %s", process.pid)
    os.close(slave_fd)
    loop = asyncio.get_running_loop()

    async def forward_output():
        try:
            while True:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                if not data:
                    logger.debug("No more data from BBS subprocess")
                    break
                logger.debug("Forwarding %r to telnet client", data)
                writer.write(data.decode(errors='ignore'))
                await writer.drain()
        except Exception:
            logger.exception("Error while forwarding output")

    output_task = asyncio.create_task(forward_output())

    try:
        while True:
            data = await reader.read(1024)
            if not data:
                logger.debug("Telnet client closed connection")
                break
            logger.debug("Received %r from telnet client", data)
            await loop.run_in_executor(None, os.write, master_fd, data.encode())
    except Exception:
        logger.exception("Error while reading from telnet client")
    finally:
        output_task.cancel()
        try:
            process.terminate()
        except ProcessLookupError:
            logger.debug("BBS subprocess already terminated")
        await process.wait()
        os.close(master_fd)
        logger.debug("Closed connection and cleaned up")

async def main() -> None:
    logger.debug("Starting telnet server on %s:%s", HOST, PORT)
    server = await telnetlib3.create_server(host=HOST, port=PORT, shell=run_app)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
