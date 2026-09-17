
import json
from pathlib import Path

from pydantic import BaseModel, Field
from src.error import MetroError, StationError
from src.passenger import Passenger


class Station(BaseModel):
    name: str
    waiting: list[Passenger] = Field(default_factory=list)
    x: int = Field(ge=0, le=1000)
    y: int = Field(ge=0, le=1000)


class Line(BaseModel):
    name: str
    color: tuple[int, int, int]
    stations: list[str]


class Map(BaseModel):
    stations: dict[str, Station] = Field(default_factory=dict)
    lines: list[Line] = Field(default_factory=list)

    def add_station(self, station: Station) -> None:
        self.stations[station.name] = station

    def add_line(self, line: Line) -> None:
        for name in line.stations:
            if name not in self.stations:
                raise StationError(
                    f"Line {line.name!r} references unknown station {name!r}"
                )
        self.lines.append(line)

    def line_named(self, line_name: str) -> Line:
        for line in self.lines:
            if line.name == line_name:
                return line
        raise MetroError(f"No line named {line_name!r}")

    def next_station(self, line_name: str, station_name: str) -> str | None:
        for line in self.lines:
            if line.name == line_name:
                try:
                    i = line.stations.index(station_name)
                except ValueError:
                    raise StationError(
                        f"Station {station_name!r} is not on line {line_name!r}"
                    ) from None
                if i + 1 < len(line.stations):
                    return line.stations[i + 1]
                return None
        raise MetroError(f"No line named {line_name!r}")

    def lines_at(self, station_name: str) -> list:
        lines_at = []
        for line in self.lines:
            if station_name in line.stations:
                lines_at.append(line)
        return lines_at


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_map(path: str | Path) -> Map:
    """Build a network from a JSON file of stations and lines.

    The file holds plain data: each station has a name and 0..1000 grid
    coordinates, each line a name, an RGB colour and its ordered stations.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    m = Map()
    for entry in raw["stations"]:
        m.add_station(Station(name=entry["name"], x=entry["x"], y=entry["y"]))
    for entry in raw["lines"]:
        m.add_line(Line(name=entry["name"], color=tuple(entry["color"]), stations=entry["stations"]))
    return m


def build_demo_map() -> Map:
    """The Lisbon metro network, from data/lisbon.json."""
    return load_map(DATA_DIR / "lisbon.json")
