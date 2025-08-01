import asyncio
import os
import sys
import telnetlib3
import pty

HOST = '0.0.0.0'
PORT = 1337

async def run_app(reader: telnetlib3.TelnetReader, writer: telnetlib3.TelnetWriter) -> None:
    master_fd, slave_fd = pty.openpty()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        'bbs_app.py',
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=os.environ.copy(),
    )
    os.close(slave_fd)
    loop = asyncio.get_running_loop()

    async def forward_output():
        try:
            while True:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                if not data:
                    break
                writer.write(data.decode(errors='ignore'))
                await writer.drain()
        except Exception:
            pass

    output_task = asyncio.create_task(forward_output())

    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            await loop.run_in_executor(None, os.write, master_fd, data.encode())
    except Exception:
        pass
    finally:
        output_task.cancel()
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        await process.wait()
        os.close(master_fd)

async def main() -> None:
    server = await telnetlib3.create_server(host=HOST, port=PORT, shell=run_app)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
