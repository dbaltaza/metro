
from pydantic import BaseModel, Field


class Passenger(BaseModel):
    id: int
    origin: str
    destination: str
    # The journey still ahead: (line, station to get off at) per leg. The
    # first leg is the one being waited for or ridden right now.
    legs: list[tuple[str, str]] = Field(default_factory=list)

    @property
    def next_line(self) -> str | None:
        return self.legs[0][0] if self.legs else None

    @property
    def alight_at(self) -> str:
        return self.legs[0][1] if self.legs else self.destination

    @property
    def changes(self) -> int:
        return max(len(self.legs) - 1, 0)
