
import random

from src.metro import Metro
from src.network import Line, Map
from src.passenger import Passenger
from src.routing import Leg, plan

DWELL_SECONDS = 3.2
SPAWN_PER_SECOND = 1.3
MAX_WAITING = 48


def spread_trains(metro_map: Map, per_line: int) -> list[Metro]:
    """Trains spaced evenly along every line, alternating direction, so the
    service is already flowing at start instead of bunching at the ends."""
    metros: list[Metro] = []
    for line in metro_map.lines:
        last = len(line.stations) - 1
        for k in range(per_line):
            index = round(k * last / max(per_line - 1, 1))
            direction = 1 if k % 2 == 0 else -1
            if index == last:
                direction = -1
            elif index == 0:
                direction = 1
            metros.append(Metro(
                id=len(metros) + 1,
                line=line.name,
                current_station=line.stations[index],
                direction=direction,
            ))
    return metros


class Simulation:
    """Moves trains along their lines and shuffles passengers on and off."""

    def __init__(self, metro_map: Map, metros: list[Metro], seed: int | None = None):
        self.map = metro_map
        self.metros = metros
        self.rng = random.Random(seed)
        self.clock = 0.0
        self.delivered = 0
        self._next_id = 1
        self._routes: dict[tuple[str, str], list[Leg]] = {}
        self.transfers = 0
        # (kind, passenger, metro) tuples since the last drain, so views can
        # animate what happened without the sim knowing about screens.
        self.events: list[tuple[str, Passenger, Metro]] = []
        self._destinations = sorted(metro_map.stations)
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
        here = metro.current_station
        station = self.map.stations[here]
        staying: list[Passenger] = []
        for passenger in metro.riders:
            if passenger.alight_at != here:
                staying.append(passenger)
                continue
            self.events.append(("alight", passenger, metro))
            if passenger.legs:
                passenger.legs = passenger.legs[1:]
            if passenger.legs:
                # Changing lines: back onto the platform for the next leg.
                station.waiting.append(passenger)
                self.transfers += 1
            else:
                self.delivered += 1
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
            if not room or passenger.next_line != line.name:
                continue
            # Only people whose stop on this line lies ahead get on this train.
            if (line.stations.index(passenger.alight_at) - here) * direction > 0:
                boarding.append(passenger)
                room -= 1
        metro.riders.extend(boarding)
        self.events.extend(("board", p, metro) for p in boarding)
        station.waiting = [p for p in station.waiting if p not in boarding]

    def _side_on_arrival(self, metro: Metro) -> int:
        """The platform side a train will occupy at its destination."""
        line = self.map.line_named(metro.line)
        j = line.stations.index(metro.destination)
        if 0 <= j + metro.direction < len(line.stations):
            return metro.direction
        return -metro.direction

    def _blocked(self, metro: Metro) -> bool:
        """Headway rule: a train may not leave while another is on the segment
        ahead going the same way, or standing at the next station on the
        platform it would pull into."""
        for other in self.metros:
            if other is metro or other.line != metro.line:
                continue
            on_segment = (
                other.cooldown == 0 and other.progress > 0
                and other.current_station == metro.current_station
                and other.destination == metro.destination
            )
            if on_segment:
                return True
            at_next_platform = (
                other.current_station == metro.destination and other.progress == 0
                and self.departing_direction(other) == self._side_on_arrival(metro)
            )
            if at_next_platform:
                return True
        return False

    def _advance(self, metro: Metro, dt: float) -> None:
        if metro.cooldown > 0:
            metro.cooldown = max(metro.cooldown - dt, 0.0)
            if metro.cooldown == 0:
                self._plan(metro)
            return
        if metro.progress == 0 and self._blocked(metro):
            metro.held = True
            return
        metro.held = False
        metro.progress = min(metro.progress + metro.speed * dt, 1.0)
        if metro.progress >= 1.0:
            self._arrive(metro)

    # -- passengers -----------------------------------------------------------

    def route(self, origin: str, destination: str) -> list[Leg]:
        key = (origin, destination)
        if key not in self._routes:
            self._routes[key] = plan(self.map, origin, destination)
        return self._routes[key]

    def _lines_through(self, station_name: str) -> list[Line]:
        return [l for l in self.map.lines if station_name in l.stations]

    def _spawn(self, dt: float) -> None:
        for station in self.map.stations.values():
            if len(station.waiting) >= MAX_WAITING:
                continue
            if self.rng.random() >= SPAWN_PER_SECOND * dt:
                continue
            destination = self.rng.choice(self._destinations)
            if destination == station.name:
                continue
            legs = self.route(station.name, destination)
            if not legs:
                continue
            station.waiting.append(Passenger(
                id=self._next_id,
                origin=station.name,
                destination=destination,
                legs=list(legs),
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
