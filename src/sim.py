
import random

from src.metro import Metro
from src.network import Line, Map, Station
from src.passenger import Passenger
from src.routing import Leg, plan
from src.settings import SETTINGS

DWELL_SECONDS = 3.2
STALL_SECONDS = (8.0, 16.0)
INCIDENT_GAP = (45.0, 110.0)
LOG_LIMIT = 6
SPAWN_PER_SECOND = 1.3
MAX_WAITING = 48
PATIENCE_SECONDS = 150.0   # a platform wait nobody puts up with
GIVE_UP_SWEEP = 1.0        # how often to check for people who have had enough


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
        self.gave_up = 0
        # Score inputs and the event log shown in the panel.
        self.wait_total = 0.0
        self.boardings = 0
        self.log: list[tuple[float, str]] = []
        self.incidents = True
        self._next_incident = self.rng.uniform(*INCIDENT_GAP)
        self._next_sweep = GIVE_UP_SWEEP
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
        if metro.retiring:
            self._retire(metro)
            return
        self._board(metro)

    def _join_platform(self, station: Station, passenger: Passenger) -> None:
        """Put someone on a platform to wait for their next train. Always
        admitted: MAX_WAITING only stops new demand being invented at a busy
        platform, and turning a transfer away would delete a journey the
        player has already been scored on. PATIENCE_SECONDS is what bounds
        the queue."""
        passenger.waited_since = self.clock
        station.waiting.append(passenger)

    def _retire(self, metro: Metro) -> None:
        station = self.map.stations[metro.current_station]
        for passenger in metro.riders:
            self._join_platform(station, passenger)
        metro.riders = []
        self.metros.remove(metro)
        self.note(f"Train #{metro.id} taken out of service at {metro.current_station}")

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
                self._join_platform(station, passenger)
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
            if not room:
                break
            if passenger.next_line != line.name:
                continue
            # Only people whose stop on this line lies ahead get on this train.
            if (line.stations.index(passenger.alight_at) - here) * direction > 0:
                boarding.append(passenger)
                room -= 1
                self.wait_total += self.clock - passenger.waited_since
                self.boardings += 1
        metro.riders.extend(boarding)
        self.events.extend(("board", p, metro) for p in boarding)
        # By identity: Passenger is a pydantic model, so `p not in boarding`
        # would deep-compare every field of every pair and cost whole frames.
        leaving = {id(p) for p in boarding}
        station.waiting = [p for p in station.waiting if id(p) not in leaving]

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
        if metro.stalled > 0:
            metro.stalled = max(metro.stalled - dt, 0.0)
            return
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
            if self.rng.random() >= SPAWN_PER_SECOND * SETTINGS.demand * dt:
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
                created=self.clock,
                waited_since=self.clock,
            ))
            self._next_id += 1

    # -- public ---------------------------------------------------------------

    def note(self, text: str) -> None:
        self.log.append((self.clock, text))
        del self.log[:-LOG_LIMIT]

    def _tick_give_ups(self, dt: float) -> None:
        """People who have waited past all patience walk out of the station.
        Without this a busy interchange grows without bound, because trains
        going their way keep arriving full."""
        self._next_sweep -= dt
        if self._next_sweep > 0:
            return
        self._next_sweep = GIVE_UP_SWEEP
        cutoff = self.clock - SETTINGS.patience
        for station in self.map.stations.values():
            if not station.waiting:
                continue
            keeping = [p for p in station.waiting if p.waited_since > cutoff]
            self.gave_up += len(station.waiting) - len(keeping)
            station.waiting = keeping

    def _tick_incidents(self, dt: float) -> None:
        if not (self.incidents and SETTINGS.incidents):
            return
        self._next_incident -= dt
        if self._next_incident > 0:
            return
        self._next_incident = self.rng.uniform(*INCIDENT_GAP)
        moving = [m for m in self.metros if m.cooldown == 0 and m.progress > 0 and m.stalled == 0]
        if not moving:
            return
        metro = self.rng.choice(moving)
        metro.stalled = self.rng.uniform(*STALL_SECONDS)
        self.note(f"Train #{metro.id} stalled between {metro.current_station} and {metro.destination}")

    def trains_on(self, line_name: str) -> list[Metro]:
        return [m for m in self.metros if m.line == line_name]

    def add_train(self, line_name: str) -> Metro | None:
        """Put a new train into service on the first free platform of a line."""
        line = self.map.line_named(line_name)
        taken = {
            (m.current_station, self.departing_direction(m))
            for m in self.metros if m.progress == 0 and m.line == line_name
        }
        for station in line.stations:
            for direction in (1, -1):
                index = line.stations.index(station)
                if not 0 <= index + direction < len(line.stations):
                    continue
                if (station, direction) in taken:
                    continue
                metro = Metro(
                    id=max((m.id for m in self.metros), default=0) + 1,
                    line=line_name,
                    current_station=station,
                    direction=direction,
                    cooldown=DWELL_SECONDS,
                )
                self.metros.append(metro)
                self._board(metro)
                self.note(f"Train #{metro.id} enters service at {station}")
                return metro
        return None

    def remove_train(self, line_name: str) -> Metro | None:
        """Take a train off a line: one standing at a platform goes at once,
        otherwise the emptiest one retires at its next stop."""
        candidates = [m for m in self.trains_on(line_name) if not m.retiring]
        if not candidates:
            return None
        standing = [m for m in candidates if m.progress == 0]
        if standing:
            metro = min(standing, key=lambda m: len(m.riders))
            self._retire(metro)
            return metro
        metro = min(candidates, key=lambda m: len(m.riders))
        metro.retiring = True
        self.note(f"Train #{metro.id} will leave service at {metro.destination}")
        return metro

    def average_wait(self) -> float:
        return self.wait_total / self.boardings if self.boardings else 0.0

    def delivered_per_minute(self) -> float:
        return self.delivered / (self.clock / 60) if self.clock > 1 else 0.0

    def update(self, dt: float) -> None:
        self.clock += dt
        self._spawn(dt)
        self._tick_give_ups(dt)
        self._tick_incidents(dt)
        for metro in list(self.metros):
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
