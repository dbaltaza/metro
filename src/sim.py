
import math
import random

from src.daytime import day_number, demand_at, hour_of, pull_at
from src.metro import Metro
from src.network import Line, Map, Station
from src.passenger import Passenger
from src.routing import Leg, plan
from src.settings import SETTINGS

DWELL_SECONDS = 3.2
# How long a fault sits there if nobody attends to it. It used to be eight
# to sixteen seconds and clear itself; now it waits for the controller, and
# the point of going down to look at it is that you get it moving in one.
STALL_SECONDS = (26.0, 52.0)
RELEASE_SECONDS = 1.4      # the pull away once the fault is cleared
FUMBLE_SECONDS = 4.0       # what the wrong control on the desk costs you
# What can be wrong with a train stopped between stations. Two for each
# control on the driver's desk, so there is more than one thing behind every
# button without the desk growing a row of them.
FAULTS = (
    "traction cut-out", "power supply dip",
    "door interlock", "passenger alarm",
    "brake fault", "wheel slide",
    "signal at danger", "points failure",
)

# The books. A fare off every journey finished, a standing cost for every
# train in service by the hour, something lost every time somebody gives up
# and walks out, and a one-off to bring a unit out of the depot. Set so that
# running about twice the starting fleet pays best: fewer trains is cheap and
# slow, many more costs more than the extra fares bring in.
FARE = 1.45
COST_PER_HOUR = 65.0
GIVE_UP_COST = 0.80
PUT_INTO_SERVICE = 400.0
OPENING_BALANCE = 5000.0
INCIDENT_GAP = (45.0, 110.0)
LOG_LIMIT = 6
SPAWN_PER_SECOND = 1.3
# How far the hour of the day tilts where people set off from and head for.
# At 1.0 the morning peak would leave the middle of the city spawning nobody
# at all; this leaves every station working, just not equally.
TIDE = 0.6
MAX_WAITING = 48
PATIENCE_SECONDS = 150.0   # a platform wait nobody puts up with

# Who is travelling, and how long each of them will stand there. A commuter
# knows the network and knows when to give up on it; a visitor has nowhere
# else to be.
KINDS = ("commuter", "visitor", "student", "shift worker")
PATIENCE_BY_KIND = {"commuter": 0.75, "visitor": 1.55, "student": 1.15, "shift worker": 1.0}
# The mix at a given hour: peak, middle of the day, evening, and the small
# hours, when almost nobody out is travelling for the fun of it.
KIND_MIX = (
    (7.0, (70, 6, 21, 3)),
    (10.0, (30, 40, 25, 5)),
    (17.0, (68, 8, 20, 4)),
    (20.0, (22, 34, 20, 24)),
    (23.5, (16, 10, 14, 60)),
)
# Where a visitor is likely to be going. Only the ones this network has.
VISITOR_STOPS = (
    "Baixa-Chiado", "Rossio", "Terreiro do Paço", "Cais do Sodré", "Aeroporto",
    "Oriente", "Parque", "Marquês de Pombal", "Jardim Zoológico", "Santa Apolónia",
)
GIVE_UP_SWEEP = 1.0        # how often to check for people who have had enough


def _centrality(metro_map: Map) -> dict[str, float]:
    """How central each station is, 0 out at the ends of the lines to 1 in the
    middle of the city. Taken from where the stations actually are, so it
    needs nothing said about them in the data."""
    stations = list(metro_map.stations.values())
    mid_x = sum(s.x for s in stations) / len(stations)
    mid_y = sum(s.y for s in stations) / len(stations)
    away = {s.name: math.hypot(s.x - mid_x, s.y - mid_y) for s in stations}
    furthest = max(away.values()) or 1.0
    return {name: 1.0 - d / furthest for name, d in away.items()}


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
        self.released = 0      # faults the controller cleared in person
        # Where the counters stood when the current day of service began, and
        # the day just finished, for whoever wants to show it.
        self.day = 1
        self.finished_day: object | None = None
        self._day_mark = (0, 0, 0, 0.0, 0)
        # The books, all cumulative; the balance is worked out from them.
        self.earned = 0.0
        self.run_cost = 0.0
        self.lost = 0.0
        self._money_mark = (0.0, 0.0, 0.0)
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
        self._visitor_stops = [n for n in VISITOR_STOPS if n in metro_map.stations] or self._destinations
        self._centrality = _centrality(metro_map)
        # Every train takes the same time to run a hop and the same time to
        # stand at a platform, so a fleet that all starts at once stays in
        # step for ever: the whole network arrives and departs on one beat.
        # A moment of dwell each, to taste, and that never happens.
        for metro in self.metros:
            # Over the whole cycle, dwell and hop together, or there would
            # still be a stretch of it with nobody moving anywhere.
            metro.cooldown = self.rng.uniform(0.0, DWELL_SECONDS + 1.0 / metro.speed)
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
                self.earned += FARE
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
            if metro.stalled == 0:
                metro.fault = ""
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

    def _kind_at(self, hour: float) -> str:
        """Who turns up at this hour. The peaks are commuters and students;
        the middle of the day belongs to visitors; the small hours to people
        going to and from work at the wrong end of the clock."""
        weights = KIND_MIX[-1][1]
        for from_hour, mix in KIND_MIX:
            if hour >= from_hour:
                weights = mix
        return self.rng.choices(KINDS, weights=weights)[0]

    def _lines_through(self, station_name: str) -> list[Line]:
        return [l for l in self.map.lines if station_name in l.stations]

    def _spawn(self, dt: float) -> None:
        hour = hour_of(self.clock)
        busy = SPAWN_PER_SECOND * SETTINGS.demand * demand_at(hour) * dt
        pull = pull_at(hour)
        for station in self.map.stations.values():
            if len(station.waiting) >= MAX_WAITING:
                continue
            # In the morning the outskirts empty into the middle, in the
            # evening the middle empties back out, and the destinations lean
            # the same way: two candidates, keep whichever suits the hour.
            tide = 1.0 + pull * (0.5 - self._centrality[station.name]) * 2 * TIDE
            if self.rng.random() >= busy * tide:
                continue
            kind = self._kind_at(hour)
            if kind == "visitor" and self.rng.random() < 0.7:
                destination = self.rng.choice(self._visitor_stops)
            else:
                destination = self.rng.choice(self._destinations)
                if pull:
                    other = self.rng.choice(self._destinations)
                    if (self._centrality[other] - self._centrality[destination]) * pull > 0:
                        destination = other
            if destination == station.name:
                continue
            legs = self.route(station.name, destination)
            if not legs:
                continue
            station.waiting.append(Passenger(
                id=self._next_id,
                origin=station.name,
                destination=destination,
                kind=kind,
                legs=list(legs),
                created=self.clock,
                waited_since=self.clock,
            ))
            self._next_id += 1

    # -- public ---------------------------------------------------------------

    def _tick_day(self) -> None:
        """Count one day of service off from the next. Service ends in the
        small hours with the network empty, which is where the line is."""
        today = day_number(self.clock)
        if today == self.day:
            return
        delivered, gave_up, released, waits, boardings = self._day_mark
        earned, run_cost, lost = self._money_mark
        from src.store import DaySummary
        self.finished_day = DaySummary(
            day=self.day,
            delivered=self.delivered - delivered,
            gave_up=self.gave_up - gave_up,
            released=self.released - released,
            average_wait=((self.wait_total - waits) / (self.boardings - boardings)
                          if self.boardings > boardings else 0.0),
            trains=len(self.metros),
            earned=self.earned - earned,
            spent=(self.run_cost - run_cost) + (self.lost - lost),
            balance=self.balance,
        )
        self.day = today
        self._mark_day()

    def _mark_day(self) -> None:
        self._day_mark = (self.delivered, self.gave_up, self.released, self.wait_total, self.boardings)
        self._money_mark = (self.earned, self.run_cost, self.lost)

    def take_finished_day(self):
        """The day that just ended, once. None if none has."""
        done, self.finished_day = self.finished_day, None
        return done

    @property
    def balance(self) -> float:
        return OPENING_BALANCE + self.earned - self.run_cost - self.lost

    def _tick_money(self, dt: float) -> None:
        """Every train in service costs by the hour, whether it is carrying
        anybody or standing at a terminus. Sixty seconds of clock is an hour."""
        self.run_cost += len(self.metros) * COST_PER_HOUR * dt / 60.0

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
        # One cutoff per kind rather than per person: the comparison is in
        # the hot loop and there are only a handful of kinds.
        cutoff = {k: self.clock - SETTINGS.patience * m for k, m in PATIENCE_BY_KIND.items()}
        fallback = self.clock - SETTINGS.patience
        for station in self.map.stations.values():
            if not station.waiting:
                continue
            keeping = [p for p in station.waiting if p.waited_since > cutoff.get(p.kind, fallback)]
            walked_out = len(station.waiting) - len(keeping)
            self.gave_up += walked_out
            self.lost += walked_out * GIVE_UP_COST
            station.waiting = keeping

    def _tick_incidents(self, dt: float) -> None:
        if not (self.incidents and SETTINGS.incidents):
            return
        self._next_incident -= dt
        if self._next_incident > 0:
            return
        moving = [m for m in self.metros if m.cooldown == 0 and m.progress > 0 and m.stalled == 0]
        if not moving:
            # Nothing between stations to break down. Come back shortly rather
            # than spending the slot: at the top of the hour the whole fleet
            # can be standing at platforms, and incidents were being skipped.
            self._next_incident = 1.0
            return
        self._next_incident = self.rng.uniform(*INCIDENT_GAP)
        metro = self.rng.choice(moving)
        metro.stalled = self.rng.uniform(*STALL_SECONDS)
        metro.fault = self.rng.choice(FAULTS)
        self.note(f"Train #{metro.id} stopped: {metro.fault}")

    def release(self, metro: Metro) -> bool:
        """The controller has cleared the fault. The train pulls away rather
        than sitting there for the rest of its several minutes."""
        if metro.stalled <= 0:
            return False
        metro.stalled = min(metro.stalled, RELEASE_SECONDS)
        metro.fault = ""
        self.released += 1
        self.note(f"Train #{metro.id} released by the controller")
        return True

    def fumble(self, metro: Metro) -> None:
        """The wrong control. Nothing breaks, but it costs a few seconds."""
        if metro.stalled > 0:
            metro.stalled += FUMBLE_SECONDS

    def trains_on(self, line_name: str) -> list[Metro]:
        return [m for m in self.metros if m.line == line_name]

    def can_afford_a_train(self) -> bool:
        return self.balance >= PUT_INTO_SERVICE

    def add_train(self, line_name: str) -> Metro | None:
        """Put a new train into service on the first free platform of a line.
        Costs a one-off to get it out of the depot, and will not run up a
        debt to do it."""
        if not self.can_afford_a_train():
            return None
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
                    cooldown=self.rng.uniform(0.4, DWELL_SECONDS),
                )
                self.metros.append(metro)
                self.run_cost += PUT_INTO_SERVICE
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
        self._tick_day()
        self._tick_money(dt)
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
