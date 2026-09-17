"""The inside of one station: platforms, live trains, people, and the chrome
around them. Layout and the backdrop live in station_layout, the train in
station_train."""

import math
import random

import pygame

from src import sprites
from src.metro import Metro
from src.network import Line
from src.passenger import Passenger
from src.route import (
    HIGHLIGHT, MUTED, PANEL_BG, PANEL_EDGE, TEXT, WINDOW_H, WINDOW_W, World,
    lines_serving,
)
from src.sim import DWELL_SECONDS, Simulation
from src.sprites import draw_character, shade
from src.station_layout import (
    IH, IW,
    BOARD, BUTTON, BUTTON_HOVER, DOOR_CLOSE_SECONDS, DOOR_OPEN_SECONDS, DOOR_W,
    ENTER_AFTER, ENTER_SECONDS, EXIT_SECONDS, FRONT_CAP, HEADER_BG, HEADER_H,
    LEAVE_UNTIL, LED, PIT_A, PIT_B, PIX, PLATFORM_1, PLATFORM_2, ROOF_H, SIDE_H,
    SIGN_EDGE, STEP_GAP, TRAIN_LEN, VIEW, WALK_SPEED, WALL_FACE, WANDER_RANGE,
    WANDER_SPEED, ease_in, ease_out, exits, render_backdrop,
)
from src.station_train import door_xs, draw_train


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
        self.backdrop, self.sign_rect, self.led_rects = render_backdrop(
            self.name, self.line.color, self.world.map.lines
        )
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
            seconds = (1 - metro.progress) * hop + metro.stalled

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
            doors = door_xs(IW / 2)
            facing_train = -1 if side < 0 else 1

            if kind == "alight":
                door_x = random.Random(passenger.id).choice(doors)
                idx = alighting_per_door.get((metro.id, door_x), 0)
                alighting_per_door[(metro.id, door_x)] = idx + 1
                t_out = max(arrival + DOOR_OPEN_SECONDS, self.time) + idx * STEP_GAP
                out_pt = (door_x + random.Random(passenger.id + 3).uniform(-4, 4), edge_y)
                stairs = min(exits(platform), key=lambda r: abs(r.centerx - door_x))
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

    # -- dynamic drawing --------------------------------------------------------

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
                draw_train(self, s, metro, x, pit)

    def draw(self, screen: pygame.Surface, paused: bool, speed: float = 1.0) -> None:
        self.speed = speed
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
            if metro.current_station == self.name and metro.held and self._side(metro) == direction:
                return f"P{number}   HOLDING   #{metro.id}"
            if metro.direction == direction and metro.destination == self.name and metro.progress > ENTER_AFTER:
                return f"P{number}   ARRIVING   #{metro.id}"
            if metro.stalled > 0 and self._eta(metro, direction) is not None:
                return f"P{number}   DELAYED   #{metro.id}"
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
        flags = " ".join(f for f in ("PAUSED" if paused else "", f"{self.speed:g}x" if getattr(self, "speed", 1.0) != 1.0 else "") if f)
        if flags:
            screen.blit(sprites.text(self.head, flags, HIGHLIGHT), (136 + title.get_width() + 18, 30))

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
