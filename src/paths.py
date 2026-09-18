"""Where the game's files live, both from a source checkout and inside a
PyInstaller bundle (which unpacks everything under sys._MEIPASS)."""

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
