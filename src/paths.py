"""Where the game's files live, both from a source checkout and inside a
PyInstaller bundle (which unpacks everything under sys._MEIPASS), and where
it is allowed to write."""

import os
import sys
from pathlib import Path


def root() -> Path:
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen)
    return Path(__file__).resolve().parent.parent


def resource(*parts: str) -> Path:
    """A file shipped with the game, e.g. resource("data", "lisbon.json")."""
    return root().joinpath(*parts)


def saves() -> Path:
    """Where the game keeps what it remembers between runs.

    Not next to the code: inside a bundled app that directory is read-only,
    and on any machine it is not ours to write to. Each platform has a place
    it expects this to go."""
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support" / "Metro Lisboa"
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", home)) / "Metro Lisboa"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "metro-lisboa"
    return base
