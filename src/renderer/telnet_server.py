import asyncio
import errno
import fcntl
import logging
import os
import pty
import signal
import struct
import sys
import termios
from pathlib import Path

import telnetlib3

SRC_ROOT = Path(__file__).resolve().parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from logging_config import setup_logging
from modules import kademlia

HOST = '0.0.0.0'
PORT = 1337

# Telnet option constants
IAC  = 255
DO   = 253
WILL = 251
SB   = 250
SE   = 240
NAWS = 31

logger = setup_logging(__name__)


def _set_pty_size(master_fd: int, cols: int, rows: int) -> None:
    """Set PTY window size via TIOCSWINSZ ioctl."""
    # struct winsize: rows, cols, xpixel, ypixel (all unsigned short)
    winsize = struct.pack('HHHH', rows, cols, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)


def _send_sigwinch(pid: int) -> None:
    """Send SIGWINCH to the process group so every thread/child receives it."""
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGWINCH)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGWINCH)
        except ProcessLookupError:
            pass


def _resize_pty(master_fd: int, cols: int, rows: int, pid: int) -> None:
    """Resize the PTY and notify the child process."""
    _set_pty_size(master_fd, cols, rows)
    _send_sigwinch(pid)
    logger.debug("PTY resized to %dx%d, SIGWINCH sent to pid %d", cols, rows, pid)


def _read_naws_size(writer: telnetlib3.TelnetWriter):
    """Read terminal size from telnetlib3 extras across version differences."""
    key_pairs = (
        ("cols", "rows"),
        ("columns", "rows"),
        ("width", "height"),
    )

    # Preferred: writer.get_extra_info (public API)
    for cols_key, rows_key in key_pairs:
        try:
            cols = writer.get_extra_info(cols_key)
            rows = writer.get_extra_info(rows_key)
            if isinstance(cols, int) and isinstance(rows, int) and cols > 0 and rows > 0:
                return cols, rows
        except Exception:
            pass

    # Fallback: protocol get_extra_info when available
    protocol = getattr(writer, "protocol", None)
    if protocol is not None and hasattr(protocol, "get_extra_info"):
        for cols_key, rows_key in key_pairs:
            try:
                cols = protocol.get_extra_info(cols_key)
                rows = protocol.get_extra_info(rows_key)
                if isinstance(cols, int) and isinstance(rows, int) and cols > 0 and rows > 0:
                    return cols, rows
            except Exception:
                pass

    # Last resort: direct attrs seen in some telnetlib3 versions
    candidates = (
        (getattr(writer, "cols", None), getattr(writer, "rows", None)),
        (getattr(writer, "columns", None), getattr(writer, "rows", None)),
        (getattr(writer, "width", None), getattr(writer, "height", None)),
        (getattr(protocol, "cols", None) if protocol else None, getattr(protocol, "rows", None) if protocol else None),
        (getattr(protocol, "columns", None) if protocol else None, getattr(protocol, "rows", None) if protocol else None),
        (getattr(protocol, "width", None) if protocol else None, getattr(protocol, "height", None) if protocol else None),
    )
    for cols, rows in candidates:
        if isinstance(cols, int) and isinstance(rows, int) and cols > 0 and rows > 0:
            return cols, rows
    return None


async def run_app(reader: telnetlib3.TelnetReader, writer: telnetlib3.TelnetWriter) -> None:
    logger.debug("Opening pty for BBS subprocess")
    master_fd, slave_fd = pty.openpty()

    # Set an initial sane PTY size before the child starts
    default_cols, default_rows = 80, 24
    _set_pty_size(master_fd, default_cols, default_rows)

    bbs_path = os.path.join(os.path.dirname(__file__), 'bbs_app.py')
    env = os.environ.copy()
    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    env['PYTHONPATH'] = os.pathsep.join([src_root, env.get('PYTHONPATH', '')])
    # Pass initial terminal dimensions so Textual starts at the right size
    env['COLUMNS'] = str(default_cols)
    env['LINES']   = str(default_rows)

    logger.debug("Launching BBS application %s", bbs_path)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        bbs_path,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    logger.debug("BBS subprocess started with PID %s", process.pid)
    os.close(slave_fd)
    loop = asyncio.get_running_loop()

    # --- NAWS negotiation ------------------------------------------------
    # Ask the client to send us its window size.
    # IAC DO NAWS -> "please tell me your terminal dimensions"
    async def request_naws() -> None:
        for attempt in range(10):
            try:
                if hasattr(writer, "iac"):
                    writer.iac(DO, NAWS)
                    logger.debug("Sent IAC DO NAWS via writer.iac")
                    return
                transport = getattr(getattr(writer, "protocol", None), "transport", None)
                if transport is not None:
                    transport.write(bytes([IAC, DO, NAWS]))
                    logger.debug("Sent IAC DO NAWS via raw transport")
                    return
            except Exception:
                pass
            await asyncio.sleep(0.1)
        logger.debug("Could not send IAC DO NAWS after retries")

    # Track current size so we only resize when it actually changes
    _current_size: list[tuple[int, int]] = [(default_cols, default_rows)]

    async def monitor_naws() -> None:
        """Poll telnetlib3 for NAWS updates and resize the PTY on change.

        telnetlib3 stores the negotiated window size in its protocol extras
        under the keys 'cols' and 'rows' whenever it parses an IAC SB NAWS
        subnegotiation from the client.  Polling is more reliable than trying
        to hook an undocumented internal callback attribute.
        """
        while True:
            await asyncio.sleep(0.15)
            try:
                new_size = _read_naws_size(writer)
                if new_size is not None and new_size != _current_size[0]:
                    logger.debug(
                        "NAWS size change: %dx%d -> %dx%d",
                        *_current_size[0], *new_size,
                    )
                    _current_size[0] = new_size
                    env['COLUMNS'] = str(new_size[0])
                    env['LINES']   = str(new_size[1])
                    _resize_pty(master_fd, new_size[0], new_size[1], process.pid)
            except Exception:
                pass

    naws_request_task = asyncio.create_task(request_naws())
    naws_task = asyncio.create_task(monitor_naws())
    child_exited = asyncio.Event()

    # --- I/O forwarding --------------------------------------------------

    async def forward_output() -> None:
        try:
            while True:
                try:
                    data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                except OSError as exc:
                    # PTY master returns EIO when the slave side closes; treat as EOF.
                    if exc.errno == errno.EIO:
                        logger.debug("PTY read reached EOF (EIO)")
                        break
                    raise
                if not data:
                    logger.debug("No more data from BBS subprocess")
                    break
                writer.write(data.decode(errors='ignore'))
                await writer.drain()
        except Exception:
            logger.exception("Error while forwarding output")
        finally:
            child_exited.set()

    async def forward_stderr() -> None:
        if process.stderr is None:
            return
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                logger.error("BBS stderr: %s", line.decode(errors="replace").rstrip())
        except Exception:
            logger.exception("Error while forwarding child stderr")

    async def watch_child_exit() -> None:
        rc = await process.wait()
        logger.debug("BBS subprocess exited with code %s", rc)
        child_exited.set()
        try:
            writer.close()
        except Exception:
            pass

    output_task = asyncio.create_task(forward_output())
    stderr_task = asyncio.create_task(forward_stderr())
    exit_task = asyncio.create_task(watch_child_exit())

    try:
        while not child_exited.is_set():
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if not data:
                logger.debug("Telnet client closed connection")
                break
            await loop.run_in_executor(None, os.write, master_fd, data.encode())
    except Exception:
        logger.exception("Error while reading from telnet client")
    finally:
        naws_task.cancel()
        naws_request_task.cancel()
        output_task.cancel()
        stderr_task.cancel()
        exit_task.cancel()
        try:
            process.terminate()
        except ProcessLookupError:
            logger.debug("BBS subprocess already terminated")
        try:
            await process.wait()
        except Exception:
            pass
        os.close(master_fd)
        logger.debug("Closed connection and cleaned up")


async def main() -> None:
    # Start a global P2P service in the long-lived renderer process so
    # bootstrap port 7331 stays open even when no user session is logged in.
    try:
        svc = kademlia.get_service()
        if not svc.unique_id:
            svc.set_identity(os.getenv("PLAYER_USERNAME", "bootstrap"), os.getenv("PLAYER_UNIQUE_ID", "bootstrap"))
        svc.start()
        logger.debug(
            "Global P2P service started in telnet server process (bootstrap_mode=%s, peer_port=%s, bootstrap_port=%s)",
            svc.bootstrap_mode,
            svc.peer_port,
            svc.bootstrap_port,
        )
    except Exception:
        logger.exception("Failed to start global P2P service")

    logger.debug("Starting telnet server on %s:%s", HOST, PORT)
    server = await telnetlib3.create_server(host=HOST, port=PORT, shell=run_app)
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
