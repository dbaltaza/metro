
import math
import random

import pygame

from src.metro import Metro
from src.network import Line
from src.passenger import Passenger
from src import sprites
from src.route import (
    HIGHLIGHT, MUTED, PANEL_BG, PANEL_EDGE, TEXT, WINDOW_H, WINDOW_W, World,
    lines_serving,
)
from src.sprites import OUTLINE, draw_character, shade
from src.sim import DWELL_SECONDS, Simulation

# --- screen layout (full resolution) ---------------------------------------------

HEADER_H = 74
BOARD = pygame.Rect(0, 592, WINDOW_W, WINDOW_H - 592)
VIEW = pygame.Rect(0, HEADER_H, WINDOW_W, BOARD.y - HEADER_H)

# The world is drawn at half size and scaled up without smoothing, which is
# what gives it chunky pixels. Everything below is in world pixels.
PIX = 2
IW, IH = VIEW.width // PIX, VIEW.height // PIX

WALL_CAP = pygame.Rect(0, 0, IW, 7)
WALL_FACE = pygame.Rect(0, 7, IW, 37)
PLATFORM_1 = pygame.Rect(0, 44, IW, 54)
EDGE_1 = pygame.Rect(0, 98, IW, 6)
PIT_A = pygame.Rect(0, 104, IW, 32)
KERB = pygame.Rect(0, 136, IW, 6)
PIT_B = pygame.Rect(0, 142, IW, 32)
LIP_2 = pygame.Rect(0, 174, IW, 4)
PLATFORM_2 = pygame.Rect(0, 178, IW, 58)
FRONT_CAP = pygame.Rect(0, 236, IW, IH - 236)

# --- palette -------------------------------------------------------------------------

WALL_CAP_C = (152, 148, 142)
WALL_C = (128, 120, 106)
WALL_BAND = (108, 100, 88)
WALL_DARK = (96, 90, 80)
FLOOR_A = (98, 92, 82)
FLOOR_B = (92, 86, 76)
GROUT = (80, 74, 66)
STAIN = (86, 80, 70)
EDGE_FACE = (56, 52, 50)
TACTILE = (216, 184, 62)
TACTILE_DARK = (152, 128, 42)
PIT = (30, 28, 32)
GRAVEL = (44, 42, 46)
SLEEPER = (60, 54, 50)
RAIL = (148, 150, 158)
RAIL_HI = (200, 202, 210)
KERB_C = (80, 82, 90)
KERB_HI = (108, 110, 118)
FRONT_C = (44, 46, 54)
FRONT_HI = (74, 76, 86)
PILLAR = (150, 146, 140)
PILLAR_HI = (184, 180, 174)
PILLAR_DK = (104, 100, 94)
BENCH = (120, 82, 50)
BENCH_DK = (84, 56, 34)
SIGN_BG = (28, 40, 78)
SIGN_EDGE = (220, 224, 232)
GLASS = (168, 214, 236)
INTERIOR = (255, 226, 150)
HEADLIGHT = (255, 244, 190)

HEADER_BG = (20, 22, 27)
BUTTON = (40, 44, 52)
BUTTON_HOVER = (58, 64, 76)

# --- trains ----------------------------------------------------------------------------

CARS = 3
CAR_LEN = 132
CAR_GAP = 6
ROOF_H = 13
SIDE_H = 16
TRAIN_LEN = CARS * CAR_LEN + (CARS - 1) * CAR_GAP
DOOR_W = 12
DOOR_FRACTIONS = [0.24, 0.76]

WANDER_SPEED = 13.0
WANDER_RANGE = (44.0, 9.0)
LED = (255, 172, 64)
LED_BG = (18, 16, 20)
EXIT_GREEN = (70, 190, 110)

ENTER_AFTER = 0.55
LEAVE_UNTIL = 0.45
WALK_SPEED = 46.0        # world px per second for people crossing the platform
DOOR_OPEN_SECONDS = 0.45
DOOR_CLOSE_SECONDS = 0.4
STEP_GAP = 0.2           # seconds between people going through one door
ENTER_SECONDS = 0.3
EXIT_SECONDS = 0.3

# Lisbon livery: silver body, dark window band, red M.
SILVER = (198, 202, 208)
SILVER_HI = (232, 234, 238)
SILVER_LO = (150, 154, 162)
BAND = (38, 42, 52)
GLASS_PANE = (96, 132, 160)
SKIRT = (58, 60, 68)
ROOF_GREY = (176, 180, 186)
ML_RED = (216, 40, 46)
BOARD_AMBER = (255, 178, 40)


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in(t: float) -> float:
    return t ** 3


def box(surface, rect: pygame.Rect, color, outline=OUTLINE) -> None:
    """A filled rect with a 1px outline, a light top edge and a dark bottom edge."""
    pygame.draw.rect(surface, outline, rect.inflate(2, 2))
    pygame.draw.rect(surface, color, rect)
    pygame.draw.line(surface, shade(color, 26), rect.topleft, (rect.right - 1, rect.top))
    pygame.draw.line(surface, shade(color, -26), (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))


# --- the scene ------------------------------------------------------------------------------

class StationView:
    """Inside one station, drawn in three-quarter top-down pixel art."""

    def __init__(self, world: World, sim: Simulation, station_name: str):
        self.world = world
        self.sim = sim
        self.name = station_name
        self.lines: list[Line] = lines_serving(world.map, station_name)
        self.tab = 0
        self.time = 0.0
        self.walkers: list[dict] = []
        self.arrivals: dict[int, float] = {}
        self.hover = None
        self.mouse = (0, 0)
        self.labels: list[tuple[pygame.Surface, tuple[float, float]]] = []
        self.people: dict[int, dict] = {}
        self._waiting_cache: list[tuple[Passenger, int]] | None = None

        self.title = pygame.font.SysFont("helvetica,arial", 26, bold=True)
        self.head = pygame.font.SysFont("helvetica,arial", 15, bold=True)
        self.body = pygame.font.SysFont("helvetica,arial", 14)
        self.small = pygame.font.SysFont("helvetica,arial", 12)
        self.sign = pygame.font.SysFont("helvetica,arial", 13, bold=True)
        self.tiny = pygame.font.SysFont("helvetica,arial", 8, bold=True)

        self.back_rect = pygame.Rect(18, 19, 92, 36)
        self.tab_rects: list[pygame.Rect] = []
        # 24-bit for the same reason as the map: no stray alpha bytes.
        self.world_surface = pygame.Surface((IW, IH), 0, 24)
        self.backdrop = self._render_backdrop()
        self.train_shadow = pygame.Surface((TRAIN_LEN + 4, 14), pygame.SRCALPHA)
        self.train_shadow.fill((0, 0, 0, 110))
        self.spill = pygame.Surface((DOOR_W + 8, 9), pygame.SRCALPHA)
        self.spill.fill((255, 226, 150, 70))

    # -- helpers ----------------------------------------------------------------

    @property
    def line(self) -> Line:
        return self.lines[self.tab]

    def _index(self, station_name: str) -> int:
        return self.line.stations.index(station_name)

    @staticmethod
    def _platform_for(direction: int) -> pygame.Rect:
        return PLATFORM_1 if direction < 0 else PLATFORM_2

    @staticmethod
    def _pit_for(direction: int) -> pygame.Rect:
        return PIT_A if direction < 0 else PIT_B

    def _spot(self, passenger: Passenger, platform: pygame.Rect) -> tuple[float, float]:
        rng = random.Random(passenger.id * 7919)
        x = 28 + rng.random() * (IW - 56)
        y = platform.y + 30 + rng.random() * (platform.height - 36)
        return x, y

    def _passenger_direction(self, passenger: Passenger) -> int | None:
        """Which platform this person waits on here, or None if their next
        leg is on another line (they show up on that line's tab)."""
        if passenger.next_line != self.line.name or passenger.alight_at not in self.line.stations:
            return None
        if passenger.alight_at == self.name:
            return None
        return -1 if self._index(passenger.alight_at) < self._index(self.name) else 1

    def _waiting_here(self) -> list[tuple[Passenger, int]]:
        if self._waiting_cache is not None:
            return self._waiting_cache
        station = self.world.map.stations[self.name]
        pairs = []
        for passenger in station.waiting:
            direction = self._passenger_direction(passenger)
            if direction is not None:
                pairs.append((passenger, direction))
        self._waiting_cache = pairs
        return pairs

    def _train_x(self, metro: Metro) -> float | None:
        centre = IW / 2
        off_left, off_right = -TRAIN_LEN / 2 - 10, IW + TRAIN_LEN / 2 + 10
        far, near = (off_right, off_left) if metro.direction < 0 else (off_left, off_right)
        if metro.current_station == self.name and metro.cooldown > 0:
            return centre
        if metro.destination == self.name and metro.progress > ENTER_AFTER:
            t = (metro.progress - ENTER_AFTER) / (1 - ENTER_AFTER)
            return far + (centre - far) * ease_out(t)
        if metro.current_station == self.name and metro.cooldown == 0 and metro.progress < LEAVE_UNTIL:
            return centre + (near - centre) * ease_in(metro.progress / LEAVE_UNTIL)
        return None

    @staticmethod
    def _door_xs(x: float) -> list[float]:
        left = x - TRAIN_LEN / 2
        xs = []
        for car in range(CARS):
            cx = left + car * (CAR_LEN + CAR_GAP)
            xs.extend(cx + f * CAR_LEN for f in DOOR_FRACTIONS)
        return xs

    def _eta(self, metro: Metro, arriving_direction: int) -> float | None:
        """Seconds until this train stops here travelling in the given direction.

        Builds one timeline: where the train is now, when it reaches its next
        stop, then dwell plus a hop for every stop after that, bouncing at the
        ends of the line the way the simulation does. No hop is ever counted
        twice, so the number falls smoothly from frame to frame.
        """
        stops = self.line.stations
        here = self._index(self.name)
        hop = 1 / metro.speed

        if metro.cooldown > 0:
            # Sitting at a platform. It leaves when the cooldown runs out and
            # heads the way the simulation will plan, reversing at a terminus.
            index = self._index(metro.current_station)
            direction = metro.direction
            if not 0 <= index + direction < len(stops):
                direction = -direction
            if index == here and direction == arriving_direction:
                return 0.0
            seconds = metro.cooldown
            index += direction
            seconds += hop
        else:
            if metro.destination is None:
                return None
            index = self._index(metro.destination)
            direction = metro.direction
            seconds = (1 - metro.progress) * hop

        # From here on the train is about to arrive at stops[index].
        for _ in range(2 * len(stops) + 2):
            if index == here and direction == arriving_direction:
                return seconds
            seconds += DWELL_SECONDS
            if not 0 <= index + direction < len(stops):
                direction = -direction
            index += direction
            seconds += hop
        return None

    # -- input / update ---------------------------------------------------------

    def handle(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "back"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB and len(self.lines) > 1:
            self.tab = (self.tab + 1) % len(self.lines)
            self.people.clear()
            self._waiting_cache = None
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                return "back"
            for i, rect in enumerate(self.tab_rects):
                if rect.collidepoint(event.pos) and i != self.tab:
                    self.tab = i
                    self.people.clear()
                    self._waiting_cache = None
        return None

    def _exits(self, platform: pygame.Rect) -> list[pygame.Rect]:
        y = platform.y + 6 if platform is PLATFORM_1 else platform.bottom - 28
        return [pygame.Rect(6, y, 26, 22), pygame.Rect(IW - 32, y, 26, 22)]

    def _tick_people(self, dt: float) -> None:
        """Waiting passengers drift around their spot so the platform feels alive."""
        alive = set()
        for passenger, direction in self._waiting_here():
            alive.add(passenger.id)
            platform = self._platform_for(direction)
            state = self.people.get(passenger.id)
            if state is None:
                home = self._spot(passenger, platform)
                state = dict(pos=home, home=home, target=home, until=self.time + random.Random(passenger.id).uniform(0.5, 4.0), moving=False, facing=1)
                self.people[passenger.id] = state
            if self.time >= state["until"]:
                rng = random.Random(passenger.id * 31 + int(self.time * 10))
                hx, hy = state["home"]
                tx = min(max(hx + rng.uniform(-WANDER_RANGE[0], WANDER_RANGE[0]), 40), IW - 40)
                ty = min(max(hy + rng.uniform(-WANDER_RANGE[1], WANDER_RANGE[1]), platform.y + 30), platform.bottom - 6)
                state["target"] = (tx, ty)
                state["until"] = self.time + rng.uniform(3.0, 9.0)
            x, y = state["pos"]
            tx, ty = state["target"]
            dx, dy = tx - x, ty - y
            dist = math.hypot(dx, dy)
            if dist > 0.6:
                step = min(WANDER_SPEED * dt, dist)
                x, y = x + dx / dist * step, y + dy / dist * step
                state["moving"] = True
                state["facing"] = -1 if dy < -0.35 * abs(dx) else 1
            else:
                state["moving"] = False
                state["facing"] = 1
            state["pos"] = (x, y)
        self.people = {pid: st for pid, st in self.people.items() if pid in alive}

    def _side(self, metro: Metro) -> int:
        """Which track and platform a train uses here. While it sits at the
        platform that is the way it will leave, so a terminus train boards
        from the right side instead of the one it arrived on."""
        if metro.current_station == self.name and metro.cooldown > 0:
            return self.sim.departing_direction(metro)
        return metro.direction

    def _next_stop(self, metro: Metro) -> str:
        """The stop the cab board should show: the planned next one, even while
        the train is still sitting at this platform."""
        if metro.cooldown <= 0 and metro.destination:
            return metro.destination
        stops = self.line.stations
        index = self._index(metro.current_station)
        direction = metro.direction
        if not 0 <= index + direction < len(stops):
            direction = -direction
        return stops[index + direction]

    def _door_state(self, metro: Metro) -> float:
        """How open a dwelling train's doors are, 0..1."""
        arrival = self.arrivals.get(metro.id)
        if arrival is None or metro.cooldown <= 0:
            return 0.0
        opening = (self.time - arrival) / DOOR_OPEN_SECONDS
        closing = metro.cooldown / DOOR_CLOSE_SECONDS
        return max(0.0, min(opening, closing, 1.0))

    def _track_arrivals(self) -> None:
        for metro in self.sim.metros:
            if metro.current_station == self.name and metro.cooldown > 0:
                if metro.id not in self.arrivals:
                    self.arrivals[metro.id] = self.time - (DWELL_SECONDS - metro.cooldown)
            else:
                self.arrivals.pop(metro.id, None)

    def _walk_time(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return max(math.hypot(b[0] - a[0], b[1] - a[1]) / WALK_SPEED, 0.15)

    def update(self, dt: float, events: list[tuple[str, Passenger, Metro]]) -> None:
        self.time += dt
        self._waiting_cache = None
        self._tick_people(dt)
        self._track_arrivals()

        # Group this frame's events by train and door, so people at the same
        # door take turns instead of piling through at once.
        per_door: dict[tuple[int, float, str], int] = {}
        alighting_per_door: dict[tuple[int, float], int] = {}
        for kind, passenger, metro in events:
            if metro.current_station != self.name or metro.line != self.line.name:
                continue
            arrival = self.arrivals.get(metro.id, self.time)
            side = self._side(metro)
            pit = self._pit_for(side)
            platform = self._platform_for(side)
            edge_y = platform.bottom - 12 if side < 0 else platform.top + 16
            door_y = pit.top - 2 if side < 0 else pit.top + ROOF_H + SIDE_H - 2
            doors = self._door_xs(IW / 2)
            facing_train = -1 if side < 0 else 1

            if kind == "alight":
                door_x = random.Random(passenger.id).choice(doors)
                idx = alighting_per_door.get((metro.id, door_x), 0)
                alighting_per_door[(metro.id, door_x)] = idx + 1
                t_out = max(arrival + DOOR_OPEN_SECONDS, self.time) + idx * STEP_GAP
                out_pt = (door_x + random.Random(passenger.id + 3).uniform(-4, 4), edge_y)
                stairs = min(self._exits(platform), key=lambda r: abs(r.centerx - door_x))
                exit_pt = (stairs.centerx, stairs.centery + 8)
                t_exit_end = t_out + EXIT_SECONDS
                t_walk_end = t_exit_end + self._walk_time(out_pt, exit_pt)
                segments = [
                    ("hidden", (door_x, door_y), (door_x, door_y), self.time, t_out),
                    ("move", (door_x, door_y), out_pt, t_out, t_exit_end),
                    ("move", out_pt, exit_pt, t_exit_end, t_walk_end),
                ]
                self.walkers.append(dict(kind=kind, passenger=passenger, segments=segments, fade_last=0.25, end=t_walk_end))
            else:
                state = self.people.pop(passenger.id, None)
                start = state["pos"] if state else self._spot(passenger, platform)
                door_x = min(doors, key=lambda d: abs(d - start[0]))
                idx = per_door.get((metro.id, door_x, "board"), 0)
                per_door[(metro.id, door_x, "board")] = idx + 1
                lane = (idx % 3 - 1) * 6
                queue_pt = (door_x + lane, edge_y + (idx // 3) * 7 * (-1 if side < 0 else 1))
                # Everyone must be inside before the doors start closing, so
                # people far from the door hurry: their walk is squeezed to fit.
                enter_time = ENTER_SECONDS + abs(queue_pt[1] - door_y) / WALK_SPEED
                deadline = arrival + DWELL_SECONDS - DOOR_CLOSE_SECONDS - enter_time - 0.1
                alighters = alighting_per_door.get((metro.id, door_x), 0)
                t_arrive = self.time + self._walk_time(start, queue_pt)
                t_go = max(t_arrive, arrival + DOOR_OPEN_SECONDS + alighters * STEP_GAP + 0.15) + idx * STEP_GAP
                t_go = min(t_go, max(deadline, self.time + 0.15))
                t_arrive = min(t_arrive, t_go)
                t_in = t_go + enter_time
                segments = [
                    ("move", start, queue_pt, self.time, t_arrive),
                    ("wait", queue_pt, queue_pt, t_arrive, t_go),
                    ("move", queue_pt, (door_x, door_y), t_go, t_in),
                ]
                self.walkers.append(dict(kind=kind, passenger=passenger, segments=segments, fade_last=0.5, end=t_in, face=facing_train, train=metro.id))
        self.walkers = [w for w in self.walkers if self.time < w["end"]]

    def _walker_pose(self, walker: dict):
        """Where a walker is right now: (x, y, facing, step, alpha), or None if hidden."""
        for i, (kind, a, b, t0, t1) in enumerate(walker["segments"]):
            if self.time < t0:
                continue
            if self.time >= t1 and i < len(walker["segments"]) - 1:
                continue
            last = i == len(walker["segments"]) - 1
            if kind == "hidden":
                return None
            span = max(t1 - t0, 1e-6)
            k = min(max((self.time - t0) / span, 0.0), 1.0)
            x, y = a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
            moving = kind == "move" and k < 1.0
            facing = 1
            if moving:
                facing = -1 if b[1] < a[1] - 0.5 else 1
            elif walker["kind"] == "board":
                facing = walker.get("face", 1)
            step = int(self.time * 9) % 2 + 1 if moving else 0
            alpha = 255
            if last and k > 1 - walker["fade_last"]:
                alpha = round(255 * (1 - k) / walker["fade_last"])
            return x, y, facing, step, alpha
        return None

    # -- static backdrop --------------------------------------------------------

    def _render_backdrop(self) -> pygame.Surface:
        s = pygame.Surface((IW, IH), 0, 24)
        rng = random.Random(hash(self.name) & 0xFFFF)

        # Back wall: a light cap on top, then the face with a darker band.
        pygame.draw.rect(s, WALL_CAP_C, WALL_CAP)
        pygame.draw.line(s, shade(WALL_CAP_C, 30), (0, 0), (IW, 0))
        pygame.draw.rect(s, WALL_C, WALL_FACE)
        pygame.draw.rect(s, WALL_BAND, (0, WALL_FACE.y, IW, 3))
        pygame.draw.rect(s, WALL_DARK, (0, WALL_FACE.bottom - 5, IW, 5))
        for x in range(0, IW, 16):  # brick courses
            pygame.draw.line(s, shade(WALL_C, -10), (x, WALL_FACE.y + 10), (x, WALL_FACE.bottom - 6))
        pygame.draw.line(s, shade(WALL_C, -10), (0, WALL_FACE.y + 20), (IW, WALL_FACE.y + 20))

        self._floor(s, PLATFORM_1, rng)
        self._floor(s, PLATFORM_2, rng)
        self._tactile(s, PLATFORM_1.bottom - 8)
        self._tactile(s, PLATFORM_2.top + 4)

        # Platform 1 drops into the pit, so we see its front face.
        pygame.draw.rect(s, EDGE_FACE, EDGE_1)
        pygame.draw.line(s, shade(EDGE_FACE, 24), (0, EDGE_1.y), (IW, EDGE_1.y))
        self._pit(s, PIT_A, rng)
        pygame.draw.rect(s, KERB_C, KERB)
        pygame.draw.line(s, KERB_HI, (0, KERB.y), (IW, KERB.y))
        self._pit(s, PIT_B, rng)
        pygame.draw.rect(s, shade(FLOOR_A, 30), LIP_2)
        pygame.draw.line(s, OUTLINE, (0, LIP_2.y), (IW, LIP_2.y))

        pygame.draw.rect(s, FRONT_C, FRONT_CAP)
        pygame.draw.line(s, FRONT_HI, (0, FRONT_CAP.y), (IW, FRONT_CAP.y))
        pygame.draw.line(s, OUTLINE, (0, FRONT_CAP.y - 1), (IW, FRONT_CAP.y - 1))

        self._furniture(s)
        return s

    def _floor(self, s, rect: pygame.Rect, rng: random.Random) -> None:
        pygame.draw.rect(s, GROUT, rect)
        tile = 8
        for ty in range(rect.y, rect.bottom, tile):
            for tx in range(0, IW, tile):
                color = FLOOR_A if ((tx // tile + ty // tile) % 2 == 0) else FLOOR_B
                if rng.random() < 0.06:
                    color = STAIN
                pygame.draw.rect(s, color, (tx, ty, tile - 1, min(tile - 1, rect.bottom - ty)))
        # Soft pools of light from the ceiling.
        pool = pygame.Surface((90, 26), pygame.SRCALPHA)
        pygame.draw.ellipse(pool, (255, 240, 200, 18), pool.get_rect())
        for x in range(60, IW, 160):
            s.blit(pool, (x - 45, rect.centery - 13))

    @staticmethod
    def _tactile(s, y: int) -> None:
        for x in range(0, IW, 12):
            pygame.draw.rect(s, TACTILE, (x + 2, y, 8, 3))
            pygame.draw.line(s, TACTILE_DARK, (x + 2, y + 3), (x + 9, y + 3))

    @staticmethod
    def _pit(s, rect: pygame.Rect, rng: random.Random) -> None:
        pygame.draw.rect(s, PIT, rect)
        for _ in range(IW // 2):
            gx, gy = rng.randrange(IW), rng.randrange(rect.y + 3, rect.bottom - 3)
            s.set_at((gx, gy), GRAVEL)
        for x in range(0, IW, 9):
            pygame.draw.rect(s, SLEEPER, (x + 2, rect.y + 6, 4, rect.height - 12))
        for ry in (rect.y + 10, rect.y + 22):
            pygame.draw.line(s, RAIL, (0, ry), (IW, ry), 2)
            pygame.draw.line(s, RAIL_HI, (0, ry - 1), (IW, ry - 1))

    def _pillar(self, s, x: int, top: int, bottom: int) -> None:
        shadow = pygame.Surface((14, bottom - top), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 50))
        s.blit(shadow, (x + 6, top + 4))
        box(s, pygame.Rect(x, top, 8, bottom - top), PILLAR)
        pygame.draw.line(s, PILLAR_HI, (x, top), (x, bottom - 1))
        pygame.draw.line(s, PILLAR_DK, (x + 7, top), (x + 7, bottom - 1))

    def _furniture(self, s) -> None:
        # Station sign on the wall, text drawn later at full resolution.
        self.sign_rect = pygame.Rect(IW // 2 - 78, WALL_FACE.y + 8, 156, 16)
        box(s, self.sign_rect, SIGN_BG, SIGN_EDGE)
        pygame.draw.rect(s, self.line.color, (self.sign_rect.x + 3, self.sign_rect.y + 3, 5, 10))

        # Posters, a network map board, a clock, a ticket machine, a vending machine.
        for i, color in enumerate([(200, 80, 70), (70, 130, 200), (230, 190, 80)]):
            box(s, pygame.Rect(118 + i * 22, WALL_FACE.y + 9, 16, 18), color)
            pygame.draw.rect(s, shade(color, 60), (121 + i * 22, WALL_FACE.y + 12, 10, 4))
        board = pygame.Rect(196, WALL_FACE.y + 8, 44, 24)
        box(s, board, (236, 232, 222))
        for i, line in enumerate(self.world.map.lines):
            pygame.draw.line(s, line.color, (board.x + 4 + i * 3, board.y + 4 + i * 5), (board.right - 5 - i * 4, board.bottom - 4 - i * 2), 2)
        box(s, pygame.Rect(256, WALL_FACE.y + 10, 12, 12), (236, 236, 240))
        pygame.draw.line(s, OUTLINE, (262, WALL_FACE.y + 16), (262, WALL_FACE.y + 12))
        pygame.draw.line(s, OUTLINE, (262, WALL_FACE.y + 16), (265, WALL_FACE.y + 16))

        # Live LED boards: one on the wall for platform 1, one on the front for 2.
        self.led_rects = {
            -1: pygame.Rect(IW // 2 + 82, WALL_FACE.y + 10, 108, 14),
            1: pygame.Rect(IW // 2 + 82, FRONT_CAP.y + 5, 108, 14),
        }
        for rect in self.led_rects.values():
            box(s, rect, LED_BG, (90, 70, 40))

        # Exit stairs at both ends of each platform, with a green sign.
        for platform in (PLATFORM_1, PLATFORM_2):
            for stairs in self._exits(platform):
                box(s, stairs, (74, 70, 66))
                for i in range(5):
                    y = stairs.y + 3 + i * 4
                    pygame.draw.line(s, shade((74, 70, 66), 30 - i * 8), (stairs.x + 2, y), (stairs.right - 3, y))
                    pygame.draw.line(s, OUTLINE, (stairs.x + 2, y + 1), (stairs.right - 3, y + 1))
                plate = pygame.Rect(stairs.x + 4, stairs.y - 6, 18, 5)
                box(s, plate, EXIT_GREEN)
        # Bins beside the pillars.
        for px in (96, 320, 544):
            box(s, pygame.Rect(px + 14, PLATFORM_1.y + 30, 6, 8), (52, 88, 62))
            box(s, pygame.Rect(px + 14, PLATFORM_2.y + 24, 6, 8), (52, 88, 62))
        box(s, pygame.Rect(IW - 140, WALL_FACE.y + 8, 18, 30), (160, 164, 172))
        pygame.draw.rect(s, (60, 120, 160), (IW - 137, WALL_FACE.y + 11, 12, 8))
        pygame.draw.rect(s, (80, 220, 100), (IW - 128, WALL_FACE.y + 22, 2, 2))
        box(s, pygame.Rect(IW - 90, WALL_FACE.y + 6, 20, 32), (190, 60, 60))
        pygame.draw.rect(s, GLASS, (IW - 87, WALL_FACE.y + 9, 14, 18))
        for row in range(3):
            pygame.draw.line(s, (120, 40, 40), (IW - 86, WALL_FACE.y + 14 + row * 5), (IW - 74, WALL_FACE.y + 14 + row * 5))

        # Benches on both platforms, then pillars over everything.
        for bx in (110, 420):
            box(s, pygame.Rect(bx, PLATFORM_1.y + 10, 28, 6), BENCH)
            pygame.draw.rect(s, BENCH_DK, (bx + 2, PLATFORM_1.y + 16, 2, 3))
            pygame.draw.rect(s, BENCH_DK, (bx + 24, PLATFORM_1.y + 16, 2, 3))
            box(s, pygame.Rect(bx + 90, PLATFORM_2.bottom - 16, 28, 6), BENCH)
        for px in (96, 320, 544):
            self._pillar(s, px, PLATFORM_1.y + 4, PLATFORM_1.y + 40)
            self._pillar(s, px, PLATFORM_2.y + 14, PLATFORM_2.bottom - 4)
        # Yellow wet-floor signs like in the reference, just for flavour.
        for wx in (IW - 60, IW - 44):
            pygame.draw.polygon(s, TACTILE, [(wx, PLATFORM_1.y + 30), (wx + 5, PLATFORM_1.y + 20), (wx + 10, PLATFORM_1.y + 30)])
            pygame.draw.polygon(s, OUTLINE, [(wx, PLATFORM_1.y + 30), (wx + 5, PLATFORM_1.y + 20), (wx + 10, PLATFORM_1.y + 30)], 1)

    # -- dynamic drawing --------------------------------------------------------

    def _draw_train(self, s, metro: Metro, x: float, pit: pygame.Rect) -> None:
        """A Lisbon Metro train: silver cars, dark window band, red M, lit cab board."""
        color = self.line.color
        y0 = pit.top - 5
        left = round(x - TRAIN_LEN / 2)
        dwelling = metro.current_station == self.name and metro.cooldown > 0
        doors_visible = self._side(metro) > 0
        open_k = self._door_state(metro) if dwelling else 0.0
        side_y = y0 + ROOF_H

        s.blit(self.train_shadow, (left - 2, y0 + ROOF_H + SIDE_H - 4))
        heads = len(metro.riders)
        front_car = 0 if metro.direction < 0 else CARS - 1
        rear_car = CARS - 1 - front_car
        for car in range(CARS):
            cx = left + car * (CAR_LEN + CAR_GAP)
            if car:
                pygame.draw.rect(s, OUTLINE, (cx - CAR_GAP, side_y + 4, CAR_GAP, 7))
                pygame.draw.rect(s, SKIRT, (cx - CAR_GAP + 1, side_y + 6, CAR_GAP - 2, 3))
            body = pygame.Rect(cx, y0, CAR_LEN, ROOF_H + SIDE_H)
            pygame.draw.rect(s, OUTLINE, body.inflate(2, 2), border_radius=3)

            # Roof with air-conditioning units.
            pygame.draw.rect(s, ROOF_GREY, (cx, y0, CAR_LEN, ROOF_H), border_top_left_radius=3, border_top_right_radius=3)
            pygame.draw.line(s, shade(ROOF_GREY, 30), (cx + 2, y0 + 1), (cx + CAR_LEN - 3, y0 + 1))
            pygame.draw.line(s, shade(ROOF_GREY, -40), (cx, y0 + ROOF_H - 1), (cx + CAR_LEN - 1, y0 + ROOF_H - 1))
            for ax in (cx + 26, cx + CAR_LEN - 48):
                box(s, pygame.Rect(ax, y0 + 4, 22, 6), shade(ROOF_GREY, -24))

            # Side: silver top band, window band, line stripe, silver skirt, dark underframe.
            pygame.draw.rect(s, SILVER, (cx, side_y, CAR_LEN, SIDE_H))
            pygame.draw.line(s, SILVER_HI, (cx, side_y), (cx + CAR_LEN - 1, side_y))
            pygame.draw.rect(s, BAND, (cx, side_y + 3, CAR_LEN, 6))
            pygame.draw.rect(s, color, (cx, side_y + 9, CAR_LEN, 1))
            pygame.draw.rect(s, SILVER_LO, (cx, side_y + 12, CAR_LEN, 1))
            pygame.draw.rect(s, SKIRT, (cx, side_y + 13, CAR_LEN, 3))

            door_xs = [cx + f * CAR_LEN for f in DOOR_FRACTIONS]
            for wx in range(cx + 6, cx + CAR_LEN - 8, 9):
                if any(abs(wx + 3 - d) < DOOR_W / 2 + 4 for d in door_xs):
                    continue
                pygame.draw.rect(s, GLASS_PANE, (wx, side_y + 4, 7, 4))
                pygame.draw.line(s, shade(GLASS_PANE, 50), (wx, side_y + 4), (wx + 6, side_y + 4))
                if heads > 0:
                    pygame.draw.rect(s, (40, 36, 44), (wx + 2, side_y + 5, 3, 3))
                    heads -= 1

            # Red M logo between the doors.
            lx, ly = cx + CAR_LEN // 2 - 3, side_y + 10
            pygame.draw.rect(s, ML_RED, (lx, ly - 1, 6, 4))
            for px_, py_ in ((1, 0), (1, 1), (1, 2), (4, 0), (4, 1), (4, 2), (2, 1), (3, 1)):
                s.set_at((lx + px_, ly + py_ - 1), (250, 250, 250))

            # Doors: two leaves that slide apart, dark rubber edges.
            for d in door_xs:
                door = pygame.Rect(round(d - DOOR_W / 2), side_y + 1, DOOR_W, SIDE_H - 4)
                slide = round(open_k * (DOOR_W / 2 - 1)) if doors_visible else 0
                if slide:
                    pygame.draw.rect(s, INTERIOR, door)
                    pygame.draw.rect(s, shade(INTERIOR, -70), (door.x, door.bottom - 2, door.width, 2))
                leaf_w = DOOR_W // 2
                for leaf_x in (door.x - slide, door.centerx + slide):
                    leaf = pygame.Rect(leaf_x, door.y, leaf_w, door.height)
                    leaf.clamp_ip(pygame.Rect(door.x - leaf_w, door.y, DOOR_W + leaf_w * 2, door.height))
                    pygame.draw.rect(s, SILVER_LO, leaf)
                    pygame.draw.rect(s, BAND, (leaf.x + 1, side_y + 3, leaf_w - 2, 6))
                    pygame.draw.rect(s, GLASS_PANE, (leaf.x + 1, side_y + 4, leaf_w - 2, 3))
                    pygame.draw.rect(s, color, (leaf.x, side_y + 9, leaf_w, 1))
                    pygame.draw.line(s, OUTLINE, (leaf.x, leaf.y), (leaf.x, leaf.bottom - 1))
                    pygame.draw.line(s, OUTLINE, (leaf.right - 1, leaf.y), (leaf.right - 1, leaf.bottom - 1))
                # Silver body shows again outside the door opening.
                pygame.draw.rect(s, OUTLINE, (door.x - 1, door.y, 1, door.height))
                pygame.draw.rect(s, OUTLINE, (door.right, door.y, 1, door.height))

            # Bogies under the car.
            for bx in (cx + 14, cx + CAR_LEN - 30):
                pygame.draw.rect(s, OUTLINE, (bx, y0 + ROOF_H + SIDE_H, 16, 3))
                pygame.draw.rect(s, (28, 28, 32), (bx + 2, y0 + ROOF_H + SIDE_H + 1, 4, 2))
                pygame.draw.rect(s, (28, 28, 32), (bx + 10, y0 + ROOF_H + SIDE_H + 1, 4, 2))

            # Cab end: wrap-around windshield, destination board, lights.
            if car == front_car:
                fx = cx + 1 if metro.direction < 0 else cx + CAR_LEN - 8
                pygame.draw.rect(s, BAND, (fx, side_y + 2, 7, 8))
                pygame.draw.rect(s, GLASS_PANE, (fx + 1, side_y + 3, 5, 5))
                lamp_x = cx + 1 if metro.direction < 0 else cx + CAR_LEN - 4
                pygame.draw.rect(s, HEADLIGHT, (lamp_x, side_y + 11, 3, 2))
                board = pygame.Rect(0, y0 + 2, 34, 5)
                board.x = cx + 4 if metro.direction < 0 else cx + CAR_LEN - 38
                box(s, board, (30, 30, 36))
                dest = self._next_stop(metro)[:11]
                self.labels.append((sprites.text(self.tiny, dest.upper(), BOARD_AMBER), (board.centerx, board.centery)))
            if car == rear_car:
                lamp_x = cx + CAR_LEN - 4 if metro.direction < 0 else cx + 1
                pygame.draw.rect(s, ML_RED, (lamp_x, side_y + 11, 3, 2))

        if dwelling and not doors_visible and open_k > 0:
            for d in self._door_xs(x):
                s.blit(self.spill, (round(d - DOOR_W / 2) - 4, PLATFORM_1.bottom - 9))

        tag = sprites.text(self.small, f"#{metro.id}", TEXT)
        self.labels.append((tag, (x, y0 + ROOF_H + SIDE_H + 11)))
        body_full = pygame.Rect(left, y0, TRAIN_LEN, ROOF_H + SIDE_H)
        if body_full.collidepoint(self._mouse_world()):
            self.hover = ("train", metro, (x, y0 - 4))

    def _mouse_world(self) -> tuple[float, float]:
        return (self.mouse[0] / PIX, (self.mouse[1] - VIEW.y) / PIX)

    def _draw_world(self) -> None:
        s = self.world_surface
        s.blit(self.backdrop, (0, 0))
        self.labels = []
        self.hover = None
        mouse = self._mouse_world()

        # Everything with a foot on the ground is sorted by y so nearer things
        # draw over farther ones, which is what sells the perspective.
        drawables: list[tuple[float, int, object]] = []
        walking = {w["passenger"].id for w in self.walkers}
        for passenger, direction in self._waiting_here():
            state = self.people.get(passenger.id)
            if passenger.id in walking or state is None:
                continue
            x, y = state["pos"]
            step = int(self.time * 8) % 2 + 1 if state["moving"] else 0
            drawables.append((y, 0, ("person", x, y, passenger, state["facing"], step, 255)))
        staff_x, staff_y = IW - 112, PLATFORM_1.y + 40
        drawables.append((staff_y, 0, ("staff", staff_x, staff_y)))
        for walker in self.walkers:
            pose = self._walker_pose(walker)
            if pose is None:
                continue
            x, y, facing, step, alpha = pose
            drawables.append((y, 0, ("person", x, y, walker["passenger"], facing, step, alpha)))
        for metro in self.sim.metros:
            if metro.line != self.line.name:
                continue
            x = self._train_x(metro)
            if x is not None:
                pit = self._pit_for(self._side(metro))
                drawables.append((pit.top + ROOF_H + SIDE_H - 5, 1, ("train", metro, x, pit)))

        for _, _, item in sorted(drawables, key=lambda d: (d[0], d[1])):
            if item[0] == "staff":
                draw_character(s, item[1], item[2], -1, 1, 0, 255)
                if pygame.Rect(item[1] - 8, item[2] - 30, 16, 32).collidepoint(mouse):
                    self.hover = ("staff", None, (item[1], item[2] - 34))
            elif item[0] == "person":
                _, x, y, passenger, facing, step, alpha = item
                draw_character(s, x, y, passenger.id, facing, step, alpha)
                if alpha == 255 and pygame.Rect(x - 8, y - 30, 16, 32).collidepoint(mouse):
                    self.hover = ("passenger", passenger, (x, y - 34))
            else:
                _, metro, x, pit = item
                self._draw_train(s, metro, x, pit)

    def draw(self, screen: pygame.Surface, paused: bool) -> None:
        self._draw_world()
        scaled = pygame.transform.scale(self.world_surface, VIEW.size)
        screen.blit(scaled, VIEW.topleft)

        # Crisp text over the pixel world: sign, platform names, train tags.
        sign = sprites.text(self.sign, self.name.upper(), SIGN_EDGE)
        cx = (self.sign_rect.centerx + 4) * PIX
        cy = VIEW.y + self.sign_rect.centery * PIX
        screen.blit(sign, sign.get_rect(center=(cx, cy)))
        for text, (x, y) in self.labels:
            screen.blit(text, text.get_rect(center=(x * PIX, VIEW.y + y * PIX)))
        for direction, platform in ((-1, PLATFORM_1), (1, PLATFORM_2)):
            number = 1 if direction < 0 else 2
            end = self.line.stations[0] if direction < 0 else self.line.stations[-1]
            # Platform 1's plate hangs on the back wall, platform 2's sits on the
            # front ledge, so neither covers anyone standing on the floor.
            y = VIEW.y + (WALL_FACE.y + 8) * PIX if direction < 0 else VIEW.y + (FRONT_CAP.y + 5) * PIX
            label = sprites.text(self.sign, f"PLATFORM {number}", TEXT)
            toward = sprites.text(self.small, f"towards {end}", shade(TEXT, -50))
            plate = pygame.Rect(24, y - 4, max(label.get_width(), toward.get_width()) + 34, 34)
            shade_plate = pygame.Surface(plate.size, pygame.SRCALPHA)
            shade_plate.fill((14, 14, 18, 150))
            screen.blit(shade_plate, plate.topleft)
            pygame.draw.rect(screen, self.line.color, (plate.x, plate.y, 4, plate.height))
            for surf, dy in ((label, 0), (toward, 15)):
                screen.blit(surf, (plate.x + 12, y + dy))

            led = self.led_rects[direction]
            text = sprites.text(self.small, self._platform_status(direction), LED)
            screen.blit(text, text.get_rect(center=((led.centerx) * PIX, VIEW.y + led.centery * PIX)))

        self._draw_header(screen, paused)
        self._draw_board(screen)
        self._draw_tooltip(screen)

    @staticmethod
    def _countdown(eta: float) -> str:
        if eta == 0:
            return "at the platform"
        if eta < 1:
            return "arriving"
        return f"in {math.ceil(eta)}s"

    def _platform_status(self, direction: int) -> str:
        number = 1 if direction < 0 else 2
        for metro in self.sim.metros:
            if metro.line != self.line.name:
                continue
            if metro.current_station == self.name and metro.cooldown > 0 and self._side(metro) == direction:
                return f"P{number}   BOARDING   #{metro.id}"
            if metro.direction == direction and metro.destination == self.name and metro.progress > ENTER_AFTER:
                return f"P{number}   ARRIVING   #{metro.id}"
        etas = [eta for m in self.sim.metros if m.line == self.line.name and (eta := self._eta(m, direction)) is not None]
        if not etas:
            return f"P{number}   NO SERVICE"
        return f"P{number}   NEXT TRAIN  {math.ceil(min(etas))}s"

    # -- chrome (full resolution) ------------------------------------------------

    def _draw_header(self, screen, paused: bool) -> None:
        pygame.draw.rect(screen, HEADER_BG, (0, 0, WINDOW_W, HEADER_H))
        pygame.draw.line(screen, PANEL_EDGE, (0, HEADER_H), (WINDOW_W, HEADER_H), 2)
        hovering = self.back_rect.collidepoint(self.mouse)
        pygame.draw.rect(screen, BUTTON_HOVER if hovering else BUTTON, self.back_rect, border_radius=8)
        pygame.draw.polygon(screen, TEXT, [(34, 37), (44, 29), (44, 45)])
        screen.blit(sprites.text(self.head, "MAP", TEXT), (52, 28))
        title = sprites.text(self.title, self.name, TEXT)
        screen.blit(title, (136, 22))
        if paused:
            screen.blit(sprites.text(self.head, "PAUSED", HIGHLIGHT), (136 + title.get_width() + 18, 30))

        self.tab_rects = []
        x = WINDOW_W - 24
        for i in reversed(range(len(self.lines))):
            line = self.lines[i]
            name = sprites.text(self.body, line.name, TEXT if i == self.tab else MUTED)
            rect = pygame.Rect(0, 0, name.get_width() + 34, 34)
            rect.topright = (x, 20)
            if i == self.tab:
                pygame.draw.rect(screen, BUTTON, rect, border_radius=8)
                pygame.draw.rect(screen, line.color, (rect.x + 10, rect.bottom - 4, rect.width - 20, 3))
            pygame.draw.circle(screen, line.color, (rect.x + 14, rect.centery), 5)
            screen.blit(name, (rect.x + 24, rect.y + 9))
            self.tab_rects.insert(0, rect)
            x = rect.x - 8

    def _draw_board(self, screen) -> None:
        pygame.draw.rect(screen, PANEL_BG, BOARD)
        pygame.draw.line(screen, PANEL_EDGE, BOARD.topleft, BOARD.topright, 2)
        x, y = 24, BOARD.y + 18
        screen.blit(sprites.text(self.head, "DEPARTURES", TEXT), (x, y))
        y += 30
        waiting = self._waiting_here()
        for direction in (-1, 1):
            number = 1 if direction < 0 else 2
            end = self.line.stations[0] if direction < 0 else self.line.stations[-1]
            count = sum(1 for _, d in waiting if d == direction)
            arriving = sorted(
                (eta, m) for m in self.sim.metros
                if m.line == self.line.name
                and (eta := self._eta(m, direction)) is not None
            )
            if not arriving:
                status = "no train scheduled"
            else:
                status = f"train #{arriving[0][1].id} {self._countdown(arriving[0][0])}"
                if len(arriving) > 1:
                    status += f", then #{arriving[1][1].id} {self._countdown(arriving[1][0])}"
            pygame.draw.circle(screen, self.line.color, (x + 6, y + 9), 6)
            screen.blit(sprites.text(self.body, f"Platform {number}   towards {end}", TEXT), (x + 22, y))
            screen.blit(sprites.text(self.body, status, MUTED), (x + 22, y + 20))
            screen.blit(sprites.text(self.small, f"{count} waiting", MUTED), (x + 22, y + 40))
            y += 70
        other = len(self.world.map.stations[self.name].waiting) - len(waiting)
        if other:
            screen.blit(sprites.text(self.small, f"{other} more waiting for another line", MUTED), (x, y))
        hint = sprites.text(self.small, "Esc or MAP returns to the network.   Space pauses.   Tab switches line.", MUTED)
        screen.blit(hint, (WINDOW_W - hint.get_width() - 24, WINDOW_H - 28))

    def _draw_tooltip(self, screen) -> None:
        if self.hover is None:
            return
        kind, thing, (wx, wy) = self.hover
        x, y = wx * PIX, VIEW.y + wy * PIX
        if kind == "passenger":
            lines = [f"to {thing.destination}"]
            if thing.changes:
                lines.append(f"changes at {thing.alight_at}")
        elif kind == "staff":
            lines = ["Station staff", "Mind the gap."]
        else:
            lines = [f"Train #{thing.id}", f"{len(thing.riders)} aboard", f"next stop {thing.destination or 'turning around'}"]
        rendered = [sprites.text(self.small, t, TEXT) for t in lines]
        rect = pygame.Rect(0, 0, max(r.get_width() for r in rendered) + 16, sum(r.get_height() for r in rendered) + 12)
        rect.midbottom = (round(x), round(y))
        rect.clamp_ip(screen.get_rect())
        pygame.draw.rect(screen, HEADER_BG, rect, border_radius=6)
        pygame.draw.rect(screen, PANEL_EDGE, rect, 1, border_radius=6)
        ty = rect.y + 6
        for r in rendered:
            screen.blit(r, (rect.x + 8, ty))
            ty += r.get_height()
