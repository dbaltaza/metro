"""Player-tunable settings, shared by the simulation and the scenes.

One process-wide instance, because the settings menu changes them while the
game is running and both the simulation and the station scene have to see
the change at once.
"""

from pydantic import BaseModel, Field


class Settings(BaseModel):
    demand: float = Field(default=1.0, description="multiplier on how fast passengers appear")
    incidents: bool = Field(default=True, description="whether trains ever stall")
    patience: float = Field(default=150.0, description="seconds before someone gives up waiting")
    crowd: int = Field(default=44, description="people drawn on each platform at once")
    sound: float = Field(default=0.5, ge=0.0, le=1.0, description="how loud the game is, 0 for silence")

    def reset(self) -> None:
        for name, field in type(self).model_fields.items():
            setattr(self, name, field.default)


# What the settings menu shows: (field, label, [(choice, value), ...], note).
OPTIONS: list[tuple[str, str, list[tuple[str, object]], str]] = [
    ("demand", "Passenger demand",
     [("Quiet", 0.5), ("Normal", 1.0), ("Rush hour", 1.8)],
     "how fast people arrive at every station"),
    ("incidents", "Incidents",
     [("Off", False), ("On", True)],
     "trains stalling between stations"),
    ("patience", "How long people wait",
     [("Short", 90.0), ("Normal", 150.0), ("Long", 240.0)],
     "before they give up and walk out"),
    ("crowd", "Platform crowd",
     [("Sparse", 24), ("Normal", 44), ("Packed", 64)],
     "how many are drawn standing on a platform"),
    ("sound", "Sound",
     [("Off", 0.0), ("Quiet", 0.5), ("Full", 1.0)],
     "chimes, trains and the crowd on the platform"),
]

SETTINGS = Settings()


def choice_index(field: str) -> int:
    """Which choice is currently selected for a row, nearest match."""
    for name, _, choices, _ in OPTIONS:
        if name != field:
            continue
        current = getattr(SETTINGS, field)
        for i, (_, value) in enumerate(choices):
            if value == current:
                return i
        # A value set from outside the menu: fall back to the closest number.
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            return min(range(len(choices)), key=lambda i: abs(float(choices[i][1]) - float(current)))
    return 0
