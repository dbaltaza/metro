
import random

from src.metro import Metro
from src.network import Line, Map
from src.passenger import Passenger

DWELL_SECONDS = 3.2
SPAWN_PER_SECOND = 1.3
MAX_WAITING = 48


class Simulation:
    """Moves trains along their lines and shuffles passengers on and off."""

    def __init__(self, metro_map: Map, metros: list[Metro], seed: int | None = None):
        self.map = metro_map
        self.metros = metros
        self.rng = random.Random(seed)
        self.clock = 0.0
        self.delivered = 0
        self._next_id = 1
        # (kind, passenger, metro) tuples since the last drain, so views can
        # animate what happened without the sim knowing about screens.
        self.events: list[tuple[str, Passenger, Metro]] = []
        for metro in self.metros:
            self._plan(metro)

    # -- trains ---------------------------------------------------------------

    def _plan(self, metro: Metro) -> None:
        """Choose the next stop, turning around at the end of the line."""
        line = self.map.line_named(metro.line)
        i = line.stations.index(metro.current_station)
        j = i + metro.direction
        if j < 0 or j >= len(line.stations):
            metro.direction *= -1
            j = i + metro.direction
        metro.destination = line.stations[j]

    def _arrive(self, metro: Metro) -> None:
        assert metro.destination is not None
        metro.current_station = metro.destination
        metro.progress = 0.0
        metro.cooldown = DWELL_SECONDS
        self._alight(metro)
        self._board(metro)

    def _alight(self, metro: Metro) -> None:
        staying = [p for p in metro.riders if p.destination != metro.current_station]
        for passenger in metro.riders:
            if passenger.destination == metro.current_station:
                self.events.append(("alight", passenger, metro))
        self.delivered += len(metro.riders) - len(staying)
        metro.riders = staying

    def departing_direction(self, metro: Metro) -> int:
        """The way a train will leave its current station: reversed at a terminus."""
        line = self.map.line_named(metro.line)
        i = line.stations.index(metro.current_station)
        if 0 <= i + metro.direction < len(line.stations):
            return metro.direction
        return -metro.direction

    def _board(self, metro: Metro) -> None:
        station = self.map.stations[metro.current_station]
        line = self.map.line_named(metro.line)
        here = line.stations.index(metro.current_station)
        direction = self.departing_direction(metro)
        room = metro.capacity - len(metro.riders)
        boarding: list[Passenger] = []
        for passenger in station.waiting:
            if not room or passenger.destination not in line.stations:
                continue
            # Only people whose destination lies ahead get on this train.
            if (line.stations.index(passenger.destination) - here) * direction > 0:
                boarding.append(passenger)
                room -= 1
        metro.riders.extend(boarding)
        self.events.extend(("board", p, metro) for p in boarding)
        station.waiting = [p for p in station.waiting if p not in boarding]

    def _advance(self, metro: Metro, dt: float) -> None:
        if metro.cooldown > 0:
            metro.cooldown = max(metro.cooldown - dt, 0.0)
            if metro.cooldown == 0:
                self._plan(metro)
            return
        metro.progress = min(metro.progress + metro.speed * dt, 1.0)
        if metro.progress >= 1.0:
            self._arrive(metro)

    # -- passengers -----------------------------------------------------------

    def _lines_through(self, station_name: str) -> list[Line]:
        return [l for l in self.map.lines if station_name in l.stations]

    def _spawn(self, dt: float) -> None:
        for station in self.map.stations.values():
            if len(station.waiting) >= MAX_WAITING:
                continue
            if self.rng.random() >= SPAWN_PER_SECOND * dt:
                continue
            reachable = {
                name
                for line in self._lines_through(station.name)
                for name in line.stations
                if name != station.name
            }
            if not reachable:
                continue
            station.waiting.append(Passenger(
                id=self._next_id,
                origin=station.name,
                destination=self.rng.choice(sorted(reachable)),
            ))
            self._next_id += 1

    # -- public ---------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.clock += dt
        self._spawn(dt)
        for metro in self.metros:
            self._advance(metro, dt)

    def drain_events(self) -> list[tuple[str, Passenger, Metro]]:
        events, self.events = self.events, []
        return events

    def waiting_total(self) -> int:
        return sum(len(s.waiting) for s in self.map.stations.values())

    def trains_at(self, station_name: str) -> list[Metro]:
        return [
            m for m in self.metros
            if m.cooldown > 0 and m.current_station == station_name
        ]
