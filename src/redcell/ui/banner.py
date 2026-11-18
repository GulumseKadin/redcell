"""Opening banner (Decepticon-style red scanner eye).

Pure presentation: shows a short "red eye" sweep animation + the REDCELL
logo at the start of a run. It observes nothing and touches no agent state
or tool — it only draws. Safe to skip entirely (non-TTY, --ui, --no-banner,
NO_COLOR) in which case a single static line is printed instead.
"""
from __future__ import annotations

import os
import time

from rich.console import Console
from rich.text import Text

# Compact block logo. Kept deliberately small so it fits an 80-col terminal.
_LOGO = r"""
 ██▀███  ▓█████ ▓█████▄  ▄████▄  ▓█████ ██▓     ██▓
▓██ ▒ ██▒▓█   ▀ ▒██▀ ██▌▒██▀ ▀█  ▓█   ▀▓██▒    ▓██▒
▓██ ░▄█ ▒▒███   ░██   █▌▒▓█    ▄ ▒███  ▒██░    ▒██░
▒██▀▀█▄  ▒▓█  ▄ ░▓█▄   ▌▒▓▓▄ ▄██▒▒▓█  ▄▒██░    ▒██░
░██▓ ▒██▒░▒████▒░▒████▓ ▒ ▓███▀ ░░▒████░██████▒░██████▒
"""

_EYE_WIDTH = 18          # inner cells of the scanner bar
_FPS = 14                # frames per second
_MAX_SECONDS = 1.8       # hard cap so we never make the user wait

_SUBTITLE = "authorized red-team agent"


def _eye_frame(pos: int, direction: int) -> Text:
    """One scanner frame: a bright red eye at `pos` with a fading trail behind."""
    t = Text()
    t.append("  [", style="bold red")
    for i in range(_EYE_WIDTH):
        dist = i - pos
        # the trail sits *behind* the eye relative to travel direction
        behind = dist * direction
        if dist == 0:
            t.append("●", style="bold bright_red")
        elif behind == -1 or behind == 1 and dist != 0:
            t.append("•", style="red")
        elif abs(dist) == 2:
            t.append("·", style="red dim")
        else:
            t.append("─", style="grey23")
    t.append("]", style="bold red")
    return t


def _bounce_positions(width: int) -> list[tuple[int, int]]:
    """Positions (idx, direction) for one left→right→left sweep."""
    seq: list[tuple[int, int]] = []
    for i in range(width):
        seq.append((i, 1))
    for i in range(width - 2, 0, -1):
        seq.append((i, -1))
    return seq


def _static_line(console: Console, version: str) -> None:
    """Fallback one-liner when animation is skipped."""
    console.print(
        Text.assemble(
            ("[", "bold red"),
            ("●", "bold bright_red"),
            ("] ", "bold red"),
            ("REDCELL", "bold red"),
            (f" v{version}", "red"),
            (f"  ·  {_SUBTITLE}", "red dim"),
        )
    )


def _print_logo(console: Console, version: str) -> None:
    console.print(Text(_LOGO, style="bold red"), highlight=False)
    console.print(
        Text.assemble(
            ("  REDCELL", "bold red"),
            (f"  v{version}", "red"),
            ("   ·   ", "red dim"),
            (_SUBTITLE, "red dim"),
        )
    )


def show_banner(console: Console, version: str, animate: bool = True) -> None:
    """Draw the opening banner.

    animate=True runs the red-eye sweep (bounded, interruptible); when the
    output is not a real terminal or animation is disabled, a single static
    line is printed instead. Never raises on Ctrl-C — it just stops early.
    """
    no_color = bool(os.environ.get("NO_COLOR"))
    if not console.is_terminal or no_color:
        animate = False

    if not animate:
        _static_line(console, version)
        return

    from rich.live import Live

    frames = _bounce_positions(_EYE_WIDTH)
    delay = 1.0 / _FPS
    deadline = time.monotonic() + _MAX_SECONDS

    try:
        with Live(console=console, refresh_per_second=_FPS, transient=True) as live:
            for pos, direction in frames:
                if time.monotonic() >= deadline:
                    break
                live.update(_eye_frame(pos, direction))
                time.sleep(delay)
    except KeyboardInterrupt:
        # transient Live already cleared the line; fall through to static banner.
        pass

    # Leave a clean, static banner on screen after the sweep.
    _print_logo(console, version)


__all__ = ["show_banner"]
