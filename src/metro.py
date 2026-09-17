
from pydantic import BaseModel, Field

from src.passenger import Passenger


class Metro(BaseModel):
    id: int
    line: str
    current_station: str
    destination: str | None = None
    direction: int = 1
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    cooldown: float = Field(default=0.0, ge=0.0)
    speed: float = Field(default=0.45, gt=0.0)
    capacity: int = Field(default=116, gt=0)
    # True while waiting at a platform for the track ahead to clear.
    held: bool = False
    riders: list[Passenger] = Field(default_factory=list)
