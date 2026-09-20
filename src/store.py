"""What the game remembers between runs.

The settings you chose and the best day you have run, in one small JSON file
in the place the platform keeps such things. Nothing here is allowed to take
the game down: a file that is missing, unreadable, or written by a newer
version than this one simply means starting fresh.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from src.paths import saves
from src.settings import SETTINGS, Settings

FILE = "save.json"


class DaySummary(BaseModel):
    """How one day on the network went."""

    day: int = 1
    delivered: int = 0
    gave_up: int = 0
    average_wait: float = 0.0
    released: int = 0
    trains: int = 0
    earned: float = 0.0
    spent: float = 0.0
    balance: float = 0.0

    @property
    def profit(self) -> float:
        return self.earned - self.spent

    def better_than(self, other: "DaySummary | None") -> bool:
        """Delivering more people is the point; everything else is detail."""
        return other is None or self.delivered > other.delivered


class Save(BaseModel):
    settings: Settings = Field(default_factory=Settings)
    best: DaySummary | None = None
    days_run: int = 0


def path() -> Path:
    return saves() / FILE


def load() -> Save:
    """What was kept last time, or a fresh one if there is nothing to read."""
    try:
        return Save.model_validate_json(path().read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return Save()


def write(save: Save) -> bool:
    """Keep it. Says whether it managed to, and never raises if it did not:
    a game that will not start because a directory is read-only is worse
    than one that forgets."""
    try:
        target = path()
        target.parent.mkdir(parents=True, exist_ok=True)
        # Written beside and moved into place, so an interrupted save cannot
        # leave half a file behind for the next run to choke on.
        spare = target.with_suffix(".tmp")
        spare.write_text(json.dumps(save.model_dump(), indent=1), encoding="utf-8")
        spare.replace(target)
        return True
    except OSError:
        return False


def apply_settings(save: Save) -> None:
    """Put the settings that were kept back into the live ones."""
    for name in type(SETTINGS).model_fields:
        setattr(SETTINGS, name, getattr(save.settings, name))


def capture_settings(save: Save) -> Save:
    return save.model_copy(update={"settings": SETTINGS.model_copy()})
