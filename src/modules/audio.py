from __future__ import annotations

import shutil
import subprocess
import sys
from threading import Thread
from time import sleep


def _run_command(cmd: list[str]) -> None:
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def play_sound(path: str) -> None:
    """Attempt to play a sound file if a player is available."""
    # Try simpleaudio if installed
    try:
        import simpleaudio  # type: ignore

        wave_obj = simpleaudio.WaveObject.from_wave_file(path)
        wave_obj.play()
        return
    except Exception:
        pass

    # Try platform players
    players = [
        ["cvlc", "--play-and-exit"],
        ["ffplay", "-nodisp", "-autoexit"],
        ["aplay"],
        ["afplay"],
    ]
    for cmd in players:
        if shutil.which(cmd[0]):
            _run_command(cmd + [path])
            return

    if sys.platform == "win32":
        try:
            import winsound  # type: ignore

            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception:
            pass

    # Fallback: no audio available
    print(f"Audio playback not available for {path}")


def play_background(path: str, delay: float = 0.0) -> None:
    """Continuously play a background audio file in a daemon thread."""

    def _loop() -> None:
        while True:
            play_sound(path)
            # Delay helps avoid tight loop if playback fails
            sleep(delay)

    Thread(target=_loop, daemon=True).start()
