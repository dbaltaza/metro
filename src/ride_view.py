"""Riding inside a train: a cutaway of one car in the same pixel style as the
station scene. Windows and doors on the far wall show the tunnel scrolling by
and platforms sliding in; riders sit and stand inside; people get on and off
through the doors at each stop."""

import math
import random

import pygame

from src import sprites
from src.metro import Metro
from src.passenger import Passenger
from src.route import HIGHLIGHT, MUTED, PANEL_BG, PANEL_EDGE, TEXT, WINDOW_H, WINDOW_W, World
from src.sim import DWELL_SECONDS, Simulation
from src.sprites import OUTLINE, draw_character, shade
from src.station_layout import (
    BAND, BOARD, DOOR_CLOSE_SECONDS, DOOR_OPEN_SECONDS, FLOOR_A, FLOOR_B, GLASS_PANE,
    GROUT, HEADER_H, IH, IW, LED, LED_BG, ML_RED, PIX, PILLAR, PILLAR_DK, PILLAR_HI,
    SILVER, SILVER_HI, SILVER_LO, SKIRT, STEP_GAP, TACTILE, TACTILE_DARK, VIEW, WALL_BAND,
    WALL_C, box,
)

# --- car layout (world pixels) --------------------------------------------------------

ROOF = pygame.Rect(0, 0, IW, 12)
OUTSIDE = pygame.Rect(0, 12, IW, 60)      # seen through windows and open doors
FAR_WALL = pygame.Rect(0, 12, IW, 60)
FAR_BENCH = pygame.Rect(0, 72, IW, 18)
FLOOR = pygame.Rect(0, 72, IW, 132)
NEAR_BENCH = pygame.Rect(0, 186, IW, 18)
NEAR_WALL = pygame.Rect(0, 204, IW, 30)
SKIRT_BAND = pygame.Rect(0, 234, IW, IH - 234)

DOOR_XS = (round(IW * 0.24), round(IW * 0.76))
DOOR_W = 34
CAR_WINDOW_W, WINDOW_STEP = 44, 68
POLE_XS = (150, 320, 490)

SEGMENT_PX = 1500.0        # how far the outside scrolls between two stations
PLATFORM_W = 980
TUNNEL = (36, 34, 40)
TUNNEL_RING = (28, 26, 32)
PIPE = (70, 66, 74)
LAMP = (255, 236, 180)
INTERIOR_WALL = (222, 224, 229)
INTERIOR_LINE = (166, 170, 178)
SEAT = (44, 74, 150)
SEAT_HI = (86, 120, 196)
SEAT_DK = (26, 44, 96)
PRIORITY = (168, 72, 60)          # priority seats, marked with a pictogram
PRIORITY_HI = (206, 112, 96)
CAR_FLOOR_A = (62, 64, 74)        # dark studded flooring, not station tile
CAR_FLOOR_B = (56, 58, 68)
FLOOR_RIB = (48, 50, 60)
DOOR_MAT = (198, 168, 58)         # yellow mat where you step on and off
POLE = (206, 210, 218)
POLE_DK = (138, 142, 150)
STRAP = (210, 212, 218)
CEILING = (238, 240, 244)
CEILING_LIGHT = (255, 250, 226)
AD_PANEL = (206, 210, 218)

WALK_SPEED = 46.0
DOOR_Y = FAR_BENCH.bottom + 4       # feet y at the door threshold
EXIT_SECONDS = 0.35                 # stepping out through the doorway
MAX_STANDING = 22


def smoothstep(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


class RideView:
    """Inside one train, riding it along its line."""

    def __init__(self, world: World, sim: Simulation, metro: Metro):
        self.world = world
        self.sim = sim
        self.metro = metro
        self.line = world.map.line_named(metro.line)
        self.time = 0.0
        self.speed = 1.0
        self.mouse = (0, 0)
        self.hover = None
        self.labels: list[tuple[pygame.Surface, tuple[float, float]]] = []
        self.walkers: list[dict] = []
        self.seats: dict[int, int] = {}   # passenger id -> spot index
        self.spots = self._spots()

        self.title = pygame.font.SysFont("helvetica,arial", 26, bold=True)
        self.head = pygame.font.SysFont("helvetica,arial", 15, bold=True)
        self.body = pygame.font.SysFont("helvetica,arial", 14)
        self.small = pygame.font.SysFont("helvetica,arial", 12)
        self.sign = pygame.font.SysFont("helvetica,arial", 13, bold=True)
        self.tiny = pygame.font.SysFont("helvetica,arial", 10)

        self.back_rect = pygame.Rect(18, 19, 92, 36)
        self.leave_rect = pygame.Rect(WINDOW_W - 250, BOARD.y + 18, 226, 36)
        # 24-bit for the same reason as the other scenes: no stray alpha bytes.
        self.world_surface = pygame.Surface((IW, IH), 0, 24)
        self.interior = self._render_interior()
        self.openings = self._openings()
        self._assign_seats()   # everyone already aboard is visible from the first frame

    def _openings(self) -> list[pygame.Rect]:
        """Door and window rectangles in the far wall, where the outside shows."""
        doors = [pygame.Rect(d - DOOR_W // 2, FAR_WALL.y + 2, DOOR_W, FAR_WALL.height - 2) for d in DOOR_XS]
        windows = []
        for x in range(30, IW - 30, WINDOW_STEP):
            win = pygame.Rect(x, FAR_WALL.y + 10, CAR_WINDOW_W, 30)
            if not any(win.colliderect(o.inflate(16, 0)) for o in doors):
                windows.append(win)
        return doors + windows

    # -- spots: where riders sit or stand ----------------------------------------------

    def _spots(self) -> list[tuple[float, float, int]]:
        """(x, feet y, facing) for every seat and standing place in the car."""
        spots = []
        for x in range(28, IW - 20, 24):
            if any(abs(x - d) < DOOR_W / 2 + 10 for d in DOOR_XS):
                continue
            spots.append((x, FAR_BENCH.bottom + 10, 1))
        for x in range(40, IW - 20, 24):
            spots.append((x, NEAR_BENCH.bottom + 8, -1))
        rng = random.Random(4)
        for k in range(MAX_STANDING):
            x = 70 + k * (IW - 140) / (MAX_STANDING - 1) + rng.uniform(-8, 8)
            spots.append((x, 150 + rng.uniform(-10, 10), 1))
        return spots

    def _assign_seats(self) -> None:
        aboard = {p.id for p in self.metro.riders}
        for pid in list(self.seats):
            if pid not in aboard:
                del self.seats[pid]
        free = [i for i in range(len(self.spots)) if i not in self.seats.values()]
        for passenger in self.metro.riders:
            if passenger.id in self.seats or not free:
                continue
            rng = random.Random(passenger.id)
            self.seats[passenger.id] = free.pop(rng.randrange(len(free)))

    # -- train state ------------------------------------------------------------------

    def _dwelling(self) -> bool:
        return self.metro.cooldown > 0

    def _door_open(self) -> float:
        if not self._dwelling():
            return 0.0
        elapsed = DWELL_SECONDS - self.metro.cooldown
        return max(0.0, min(elapsed / DOOR_OPEN_SECONDS, self.metro.cooldown / DOOR_CLOSE_SECONDS, 1.0))

    def _distance(self) -> float:
        """How far along the current segment the outside has scrolled."""
        if self._dwelling() or self.metro.destination is None:
            return 0.0
        return SEGMENT_PX * smoothstep(self.metro.progress)

    def _next_stop(self) -> str:
        if self.metro.cooldown <= 0 and self.metro.destination:
            return self.metro.destination
        stops = self.line.stations
        index = stops.index(self.metro.current_station)
        direction = self.metro.direction
        if not 0 <= index + direction < len(stops):
            direction = -direction
        return stops[index + direction]

    # -- input / update ---------------------------------------------------------------

    def handle(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "back"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e and self._dwelling():
            return ("station", self.metro.current_station)
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                return "back"
            if self._dwelling() and self.leave_rect.collidepoint(event.pos):
                return ("station", self.metro.current_station)
        return None

    def update(self, dt: float, events: list[tuple[str, Passenger, Metro]]):
        """Advance animations. Returns an action if the ride has to end."""
        self.time += dt
        if self.metro not in self.sim.metros:
            return ("station", self.metro.current_station)
        mine = [(kind, passenger) for kind, passenger, metro in events if metro is self.metro]
        if mine:
            self._choreograph(mine)
        else:
            self._assign_seats()
        self.walkers = [w for w in self.walkers if self.time < w["t1"] + w["exit"]]
        return None

    def _choreograph(self, mine: list[tuple[str, Passenger]]) -> None:
        """Queue everyone through the nearest door: leavers first, then boarders,
        one person per STEP_GAP, and squeeze the whole thing so it is over before
        the doors close, however many people there are."""
        now = self.time
        elapsed = DWELL_SECONDS - self.metro.cooldown
        open_at = now + max(0.0, DOOR_OPEN_SECONDS - elapsed)
        close_at = now + self.metro.cooldown - DOOR_CLOSE_SECONDS

        # Leavers while they still own a seat, so we know where they stand up from.
        leavers = []
        for kind, passenger in mine:
            if kind != "alight":
                continue
            spot = self.seats.pop(passenger.id, None)
            if spot is not None:
                leavers.append((passenger, self.spots[spot]))
        self._assign_seats()
        boarders = []
        for kind, passenger in mine:
            if kind != "board":
                continue
            spot = self.seats.get(passenger.id)
            if spot is not None:
                boarders.append((passenger, self.spots[spot]))

        made = []
        for door in DOOR_XS:
            t_door = open_at
            queue = [(p, xyf) for p, xyf in leavers if min(DOOR_XS, key=lambda d: abs(d - xyf[0])) == door]
            queue.sort(key=lambda item: (abs(item[1][0] - door), item[0].id))
            for passenger, (x, y, _) in queue:
                walk = math.hypot(door - x, DOOR_Y - y) / WALK_SPEED
                t1 = max(t_door, now + walk)
                made.append(dict(passenger=passenger, start=(x, y), end=(door, DOOR_Y), t0=t1 - walk, t1=t1, fade=True, exit=EXIT_SECONDS, facing=-1))
                t_door = t1 + STEP_GAP
            t_door += STEP_GAP  # a beat before people start getting on
            for passenger, (x, y, facing) in boarders:
                if min(DOOR_XS, key=lambda d: abs(d - x)) != door:
                    continue
                walk = math.hypot(door - x, DOOR_Y - y) / WALK_SPEED
                made.append(dict(passenger=passenger, start=(door, DOOR_Y), end=(x, y), t0=t_door, t1=t_door + walk, fade=False, exit=0.0, facing=facing))
                t_door += STEP_GAP

        # Through the door before it closes: last leaver fully out, last boarder in.
        last = max((w["t1"] + w["exit"] if w["fade"] else w["t0"] + 0.3 for w in made), default=now)
        if last > close_at and last > now:
            # k hits 0 only if the doors are already closing: they just appear.
            k = max((close_at - now) / (last - now), 0.0)
            for w in made:
                w["t0"] = now + (w["t0"] - now) * k
                w["t1"] = now + (w["t1"] - now) * k
                w["exit"] *= k
        self.walkers.extend(made)

    # -- static interior ----------------------------------------------------------------

    def _render_interior(self) -> pygame.Surface:
        """Everything that never moves: flooring, seats, near wall, skirt."""
        s = pygame.Surface((IW, IH), 0, 24)
        s.fill(CAR_FLOOR_A)

        # Floor: dark studded rubber, run lengthwise, with a yellow mat at each
        # doorway the way the real cars have.
        pygame.draw.rect(s, CAR_FLOOR_A, FLOOR)
        for y in range(FLOOR.y, FLOOR.bottom, 6):
            pygame.draw.line(s, CAR_FLOOR_B, (0, y), (IW, y))
        for y in range(FLOOR.y + 3, FLOOR.bottom, 12):
            pygame.draw.line(s, FLOOR_RIB, (0, y), (IW, y))
        for dx in DOOR_XS:
            mat = pygame.Rect(dx - DOOR_W // 2 - 6, FAR_BENCH.bottom, DOOR_W + 12, 10)
            pygame.draw.rect(s, DOOR_MAT, mat)
            pygame.draw.rect(s, shade(DOOR_MAT, -50), (mat.x, mat.bottom - 2, mat.width, 2))
            for hx in range(mat.x + 2, mat.right - 2, 4):
                pygame.draw.rect(s, shade(DOOR_MAT, -28), (hx, mat.y + 3, 2, 4))

        self._draw_bench(s, FAR_BENCH, far=True)
        self._draw_bench(s, NEAR_BENCH, far=False)

        # Near wall: interior panel, then the car's outside skirt below it.
        pygame.draw.rect(s, INTERIOR_WALL, NEAR_WALL)
        pygame.draw.line(s, INTERIOR_LINE, (0, NEAR_WALL.y), (IW, NEAR_WALL.y))
        for x in range(0, IW, 96):      # panel seams
            pygame.draw.line(s, shade(INTERIOR_WALL, -14), (x, NEAR_WALL.y + 2), (x, NEAR_WALL.bottom - 5))
        pygame.draw.rect(s, shade(INTERIOR_WALL, -24), (0, NEAR_WALL.bottom - 4, IW, 4))
        pygame.draw.rect(s, SILVER, SKIRT_BAND)
        pygame.draw.line(s, SILVER_HI, (0, SKIRT_BAND.y), (IW, SKIRT_BAND.y))
        pygame.draw.rect(s, self.line.color, (0, SKIRT_BAND.y + 6, IW, 2))
        pygame.draw.rect(s, SILVER_LO, (0, SKIRT_BAND.y + 14, IW, 1))
        pygame.draw.rect(s, SKIRT, (0, SKIRT_BAND.y + 16, IW, SKIRT_BAND.height - 16))
        lx, ly = IW // 2 - 3, SKIRT_BAND.y + 9
        pygame.draw.rect(s, ML_RED, (lx, ly, 6, 4))
        for px_, py_ in ((1, 0), (1, 1), (1, 2), (4, 0), (4, 1), (4, 2), (2, 1), (3, 1)):
            s.set_at((lx + px_, ly + py_), (250, 250, 250))
        return s

    def _draw_bench(self, s: pygame.Surface, bench: pygame.Rect, far: bool) -> None:
        """A run of moulded seats along the side of the car: a dark frame, a
        blue pad per seat with a divider between, and priority seats in red
        nearest the doors."""
        pygame.draw.rect(s, shade(INTERIOR_WALL, -46), bench)
        pygame.draw.line(s, shade(INTERIOR_WALL, -70), (0, bench.bottom - 1), (IW, bench.bottom - 1))
        seat_w, gap = 22, 2
        for x in range(6, IW - seat_w, seat_w + gap):
            centre = x + seat_w / 2
            if far and any(abs(centre - d) < DOOR_W / 2 + 10 for d in DOOR_XS):
                continue
            # The seats flanking a doorway are the priority ones.
            near_door = min(abs(centre - d) for d in DOOR_XS) < DOOR_W / 2 + 34
            pad, hi = (PRIORITY, PRIORITY_HI) if near_door else (SEAT, SEAT_HI)
            seat = pygame.Rect(x, bench.y + 2, seat_w, bench.height - 5)
            pygame.draw.rect(s, SEAT_DK, seat.inflate(2, 2), border_radius=2)
            pygame.draw.rect(s, pad, seat, border_radius=2)
            pygame.draw.line(s, hi, (seat.x + 1, seat.y + 1), (seat.right - 2, seat.y + 1))
            pygame.draw.line(s, shade(pad, -40), (seat.x + 1, seat.bottom - 2), (seat.right - 2, seat.bottom - 2))
            # A dip in the middle of the pad, so it reads as a moulded shell.
            pygame.draw.line(s, shade(pad, -22), (seat.centerx, seat.y + 2), (seat.centerx, seat.bottom - 3))
            if near_door:
                pygame.draw.rect(s, (245, 245, 250), (seat.centerx - 3, seat.y + 4, 2, 2))
                pygame.draw.rect(s, (245, 245, 250), (seat.centerx - 3, seat.y + 7, 2, 3))

    # -- outside: tunnel and platforms --------------------------------------------------

    def _draw_outside(self, s: pygame.Surface) -> None:
        distance = self._distance()
        clip = s.get_clip()
        s.set_clip(OUTSIDE)
        s.fill(TUNNEL, OUTSIDE)
        # Concrete rings, pipes and lamps scroll past between stations.
        offset = int(distance) % 48
        for x in range(-offset, IW + 48, 48):
            pygame.draw.line(s, TUNNEL_RING, (x, OUTSIDE.y), (x, OUTSIDE.bottom), 3)
        pygame.draw.line(s, PIPE, (0, OUTSIDE.y + 8), (IW, OUTSIDE.y + 8), 2)
        pygame.draw.line(s, PIPE, (0, OUTSIDE.y + 13), (IW, OUTSIDE.y + 13), 1)
        lamp_offset = int(distance) % 160
        for x in range(-lamp_offset, IW + 160, 160):
            pygame.draw.rect(s, LAMP, (x, OUTSIDE.y + 3, 12, 3))
            glow = pygame.Surface((40, 30), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 236, 180, 26), glow.get_rect())
            s.blit(glow, (x - 14, OUTSIDE.y + 2))

        # The platform we left slides away to the left; the next one arrives
        # from the right. Both are centred on the car when the train stops.
        here = self.metro.current_station
        nxt = self._next_stop()
        centre = IW / 2
        self._draw_platform(s, here, centre - distance)
        if not self._dwelling() and self.metro.destination:
            self._draw_platform(s, nxt, centre + SEGMENT_PX - distance)
        s.set_clip(clip)

    def _draw_platform(self, s: pygame.Surface, name: str, cx: float) -> None:
        left = cx - PLATFORM_W / 2
        if left > IW or left + PLATFORM_W < 0:
            return
        rect = pygame.Rect(round(left), OUTSIDE.y, PLATFORM_W, OUTSIDE.height)
        # Back wall of the station with a band, then floor tiles by the car.
        pygame.draw.rect(s, WALL_C, (rect.x, rect.y, rect.width, 26))
        pygame.draw.rect(s, WALL_BAND, (rect.x, rect.y, rect.width, 3))
        pygame.draw.rect(s, GROUT, (rect.x, rect.y + 26, rect.width, rect.height - 26))
        tile = 8
        for ty in range(rect.y + 26, rect.bottom, tile):
            for tx in range(rect.x, rect.right, tile):
                color = FLOOR_A if ((tx // tile + ty // tile) % 2 == 0) else FLOOR_B
                pygame.draw.rect(s, color, (tx, ty, tile - 1, min(tile - 1, rect.bottom - ty)))
        for x in range(rect.x, rect.right, 12):
            pygame.draw.rect(s, TACTILE, (x + 2, rect.bottom - 5, 8, 3))
            pygame.draw.line(s, TACTILE_DARK, (x + 2, rect.bottom - 2), (x + 9, rect.bottom - 2))
        for px in range(rect.x + 120, rect.right - 100, 240):
            box(s, pygame.Rect(px, rect.y + 20, 6, 30), PILLAR)
            pygame.draw.line(s, PILLAR_HI, (px, rect.y + 20), (px, rect.y + 49))
            pygame.draw.line(s, PILLAR_DK, (px + 5, rect.y + 20), (px + 5, rect.y + 49))
        sign = pygame.Rect(round(cx) - 70, rect.y + 6, 140, 14)
        box(s, sign, (28, 40, 78), (220, 224, 232))
        pygame.draw.rect(s, self.line.color, (sign.x + 3, sign.y + 3, 5, 8))
        # The name is crisp full-res text, so only show it where the wall
        # actually has an opening for it to be seen through.
        if any(o.collidepoint(sign.centerx + 4, sign.centery) for o in self.openings):
            self.labels.append((sprites.text(self.sign, name.upper(), (220, 224, 232)), (sign.centerx + 4, sign.centery)))
        # A few of the people waiting there, seen through the windows.
        station = self.world.map.stations[name]
        waiting = [p for p in station.waiting if p.next_line == self.line.name][:10]
        for k, passenger in enumerate(waiting):
            rng = random.Random(passenger.id * 13)
            x = cx + (k - len(waiting) / 2) * 34 + rng.uniform(-6, 6)
            draw_character(s, x, rect.bottom - 2 - rng.uniform(0, 6), passenger.id, 1, 0)

    # -- far wall with windows and doors ------------------------------------------------------

    def _draw_far_wall(self, s: pygame.Surface) -> None:
        open_k = self._door_open()
        openings = self.openings[:len(DOOR_XS)]
        windows = self.openings[len(DOOR_XS):]
        # Wall everywhere, then punch the windows back out by redrawing the
        # outside through them.
        outside = s.subsurface(OUTSIDE).copy()
        pygame.draw.rect(s, INTERIOR_WALL, FAR_WALL)
        pygame.draw.rect(s, shade(INTERIOR_WALL, 16), (0, FAR_WALL.y, IW, 3))
        pygame.draw.rect(s, shade(INTERIOR_WALL, -20), (0, FAR_WALL.bottom - 3, IW, 3))
        for win in windows:
            s.blit(outside, win.topleft, pygame.Rect(win.x, win.y - OUTSIDE.y, win.width, win.height))
            # A rubber gasket, a silver frame and a sill, so the glass reads as
            # glass rather than a hole cut in the wall.
            pygame.draw.rect(s, SILVER_LO, win.inflate(4, 4), 2, border_radius=2)
            pygame.draw.rect(s, OUTLINE, win.inflate(2, 2), 1, border_radius=2)
            pygame.draw.rect(s, shade(INTERIOR_WALL, -30), (win.x - 2, win.bottom + 2, win.width + 4, 2))
            pygame.draw.line(s, shade(GLASS_PANE, 70), (win.x + 2, win.y + 2), (win.x + 14, win.y + 2))
            pygame.draw.line(s, shade(GLASS_PANE, 40), (win.x + 2, win.y + 4), (win.x + 9, win.y + 4))
        for door in openings:
            slide = round(open_k * (DOOR_W / 2 - 1))
            s.blit(outside, door.topleft, pygame.Rect(door.x, door.y - OUTSIDE.y, door.width, door.height))
            leaf_w = DOOR_W // 2
            for leaf_x in (door.x - slide, door.centerx + slide):
                leaf = pygame.Rect(leaf_x, door.y, leaf_w, door.height)
                leaf.clamp_ip(pygame.Rect(door.x - leaf_w, door.y, DOOR_W + 2 * leaf_w, door.height))
                pygame.draw.rect(s, SILVER_LO, leaf)
                glass = pygame.Rect(leaf.x + 2, leaf.y + 8, leaf_w - 4, 22)
                s.blit(outside, glass.topleft, pygame.Rect(glass.x, glass.y - OUTSIDE.y, glass.width, glass.height))
                pygame.draw.rect(s, OUTLINE, glass, 1)
                pygame.draw.rect(s, self.line.color, (leaf.x, leaf.bottom - 6, leaf_w, 2))
                pygame.draw.line(s, OUTLINE, (leaf.x, leaf.y), (leaf.x, leaf.bottom - 1))
                pygame.draw.line(s, OUTLINE, (leaf.right - 1, leaf.y), (leaf.right - 1, leaf.bottom - 1))
            pygame.draw.rect(s, OUTLINE, door.inflate(2, 0), 1)
            # Door call button and the red emergency intercom beside it.
            lit = (120, 230, 140) if open_k > 0.5 else (60, 110, 74)
            bx = door.right + 4
            pygame.draw.rect(s, OUTLINE, (bx - 1, door.y + 15, 6, 8))
            pygame.draw.rect(s, shade(INTERIOR_WALL, -30), (bx, door.y + 16, 4, 6))
            pygame.draw.rect(s, lit, (bx + 1, door.y + 17, 2, 2))
            pygame.draw.rect(s, OUTLINE, (bx - 1, door.y + 26, 6, 7))
            pygame.draw.rect(s, ML_RED, (bx, door.y + 27, 4, 5))
        # Advertising panels and the route strip above the windows, which is
        # what fills the band between the glass and the ceiling in a real car.
        band = pygame.Rect(0, FAR_WALL.y, IW, 9)
        pygame.draw.rect(s, shade(INTERIOR_WALL, 10), band)
        pygame.draw.line(s, self.line.color, (0, band.bottom - 2), (IW, band.bottom - 2), 2)
        stops = self.line.stations
        here = stops.index(self.metro.current_station)
        for i, x in enumerate(range(24, IW - 20, 58)):
            panel = pygame.Rect(x, band.y + 1, 46, 5)
            pygame.draw.rect(s, AD_PANEL, panel)
            pygame.draw.rect(s, shade(AD_PANEL, -34), panel, 1)
            # Dots along the strip stand for the stops, the current one filled.
            stop = i - len(range(24, IW - 20, 58)) // 2 + here
            if 0 <= stop < len(stops):
                dot = (panel.centerx, band.bottom - 2)
                pygame.draw.circle(s, (250, 250, 252), dot, 2)
                if stop == here:
                    pygame.draw.circle(s, ML_RED, dot, 2)

        # Ceiling: pale panels with a warm light running down the middle.
        pygame.draw.rect(s, CEILING, ROOF)
        pygame.draw.rect(s, shade(CEILING, -26), (0, ROOF.bottom - 2, IW, 2))
        pygame.draw.rect(s, CEILING_LIGHT, (0, ROOF.y + 3, IW, 5))
        pygame.draw.line(s, (255, 255, 244), (0, ROOF.y + 4), (IW, ROOF.y + 4))
        for x in range(0, IW, 74):      # seams between ceiling panels
            pygame.draw.line(s, shade(CEILING, -20), (x, ROOF.y), (x, ROOF.y + 2))
            pygame.draw.line(s, shade(CEILING, -20), (x, ROOF.y + 8), (x, ROOF.bottom - 2))

    def _draw_fittings(self, s: pygame.Surface) -> None:
        """Grab rails and hanging straps, in front of the wall and behind the
        people. Every Lisbon car has a rail down the length with straps on it
        and floor-to-ceiling poles by the doors."""
        rail_y = ROOF.bottom + 3
        pygame.draw.line(s, POLE_DK, (0, rail_y + 1), (IW, rail_y + 1), 2)
        pygame.draw.line(s, POLE, (0, rail_y), (IW, rail_y), 1)
        # Straps: a short hanger and a loop, swaying with the car.
        swing = math.sin(self.time * 2.2) * 1.6 if not self._dwelling() else 0.0
        for i, x in enumerate(range(34, IW - 20, 46)):
            lean = round(swing * (1 if i % 2 else -1))
            top = (x, rail_y + 2)
            bottom = (x + lean, rail_y + 13)
            pygame.draw.line(s, OUTLINE, (top[0] + 1, top[1]), (bottom[0] + 1, bottom[1]), 1)
            pygame.draw.line(s, STRAP, top, bottom, 1)
            loop = pygame.Rect(bottom[0] - 3, bottom[1], 6, 7)
            pygame.draw.ellipse(s, OUTLINE, loop.inflate(2, 2))
            pygame.draw.ellipse(s, STRAP, loop)
            pygame.draw.ellipse(s, shade(INTERIOR_WALL, -30), loop.inflate(-2, -2))
        # Vertical poles, floor to ceiling, with a foot at the bottom.
        for px in POLE_XS:
            pygame.draw.line(s, OUTLINE, (px + 2, ROOF.bottom), (px + 2, NEAR_BENCH.y), 3)
            pygame.draw.line(s, POLE, (px + 1, ROOF.bottom), (px + 1, NEAR_BENCH.y), 1)
            pygame.draw.line(s, POLE_DK, (px + 2, ROOF.bottom), (px + 2, NEAR_BENCH.y), 1)
            pygame.draw.rect(s, POLE_DK, (px - 1, NEAR_BENCH.y - 2, 7, 3))

    # -- people --------------------------------------------------------------------------------

    def _draw_people(self, s: pygame.Surface) -> None:
        mouse = self._mouse_world()
        walking = {w["passenger"].id for w in self.walkers}
        drawables = []
        for passenger in self.metro.riders:
            spot = self.seats.get(passenger.id)
            if spot is None or passenger.id in walking:
                continue
            x, y, facing = self.spots[spot]
            drawables.append((y, x, passenger, facing, 0, 255))
        for w in self.walkers:
            k = min(max((self.time - w["t0"]) / max(w["t1"] - w["t0"], 1e-6), 0.0), 1.0)
            if self.time < w["t0"] and w["fade"]:
                x, y = w["start"]
                drawables.append((y, x, w["passenger"], -1, 0, 255))
                continue
            if self.time < w["t0"]:
                continue
            (x1, y1), (x2, y2) = w["start"], w["end"]
            x, y = x1 + (x2 - x1) * k, y1 + (y2 - y1) * k
            alpha = 255
            step = int(self.time * 9) % 2 + 1 if k < 1.0 else 0
            facing = w["facing"] if k < 1 else 1
            if w["fade"] and k >= 1.0:
                # Through the doorway: keep walking away, up into the door, and fade.
                out = min((self.time - w["t1"]) / max(w["exit"], 1e-6), 1.0)
                y -= 10 * out
                alpha = max(0, round(255 * (1 - out)))
                step = int(self.time * 9) % 2 + 1
                facing = -1
            drawables.append((y, x, w["passenger"], facing, step, alpha))
        for y, x, passenger, facing, step, alpha in sorted(drawables, key=lambda d: d[0]):
            draw_character(s, x, y, passenger.id, facing, step, alpha)
            if alpha == 255 and pygame.Rect(x - 8, y - 30, 16, 32).collidepoint(mouse):
                self.hover = ("passenger", passenger, (x, y - 34))

    def _mouse_world(self) -> tuple[float, float]:
        return (self.mouse[0] / PIX, (self.mouse[1] - VIEW.y) / PIX)

    # -- drawing -------------------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, paused: bool, speed: float = 1.0) -> None:
        self.speed = speed
        self.labels = []
        self.hover = None
        s = self.world_surface
        s.blit(self.interior, (0, 0))
        self._draw_outside(s)
        self._draw_far_wall(s)
        self._draw_fittings(s)
        self._draw_people(s)
        moving = not self._dwelling() and self.metro.stalled == 0 and not self.metro.held
        sway = 1 if moving and int(self.time * 5) % 2 else 0
        scaled = pygame.transform.scale(s, VIEW.size)
        screen.fill((20, 22, 27))
        screen.blit(scaled, (VIEW.x, VIEW.y + sway * PIX))
        for text, (x, y) in self.labels:
            screen.blit(text, text.get_rect(center=(x * PIX, VIEW.y + y * PIX + sway * PIX)))
        self._draw_header(screen, paused)
        self._draw_board(screen)
        self._draw_tooltip(screen)

    def _draw_header(self, screen, paused: bool) -> None:
        pygame.draw.rect(screen, (20, 22, 27), (0, 0, WINDOW_W, HEADER_H))
        pygame.draw.line(screen, PANEL_EDGE, (0, HEADER_H), (WINDOW_W, HEADER_H), 2)
        hovering = self.back_rect.collidepoint(self.mouse)
        pygame.draw.rect(screen, (58, 64, 76) if hovering else (40, 44, 52), self.back_rect, border_radius=8)
        pygame.draw.polygon(screen, TEXT, [(34, 37), (44, 29), (44, 45)])
        screen.blit(sprites.text(self.head, "MAP", TEXT), (52, 28))
        pygame.draw.circle(screen, self.line.color, (150, 37), 8)
        title = sprites.text(self.title, f"Train #{self.metro.id}", TEXT)
        screen.blit(title, (168, 22))
        sub = sprites.text(self.body, self.line.name, MUTED)
        screen.blit(sub, (168 + title.get_width() + 14, 30))
        flags = " ".join(f for f in ("PAUSED" if paused else "", f"{self.speed:g}x" if self.speed != 1.0 else "") if f)
        if flags:
            screen.blit(sprites.text(self.head, flags, HIGHLIGHT), (168 + title.get_width() + 34 + sub.get_width(), 30))

        # In-car LED display, top right.
        led = pygame.Rect(WINDOW_W - 380, 20, 356, 34)
        pygame.draw.rect(screen, LED_BG, led, border_radius=4)
        pygame.draw.rect(screen, (90, 70, 40), led, 1, border_radius=4)
        if self.metro.stalled > 0:
            status = "DELAYED   we apologise for the wait"
        elif self.metro.held:
            status = "HOLDING   waiting for the line ahead"
        elif self._dwelling():
            status = f"NOW AT   {self.metro.current_station}"
        else:
            status = f"NEXT STOP   {self._next_stop()}"
        text = sprites.text(self.head, status.upper(), LED)
        screen.blit(text, text.get_rect(midleft=(led.x + 14, led.centery)))

    def _draw_board(self, screen) -> None:
        pygame.draw.rect(screen, PANEL_BG, BOARD)
        pygame.draw.line(screen, PANEL_EDGE, BOARD.topleft, BOARD.topright, 2)
        x = 24
        y = BOARD.y + 18
        riders = len(self.metro.riders)
        shown = sum(1 for p in self.metro.riders if p.id in self.seats)
        screen.blit(sprites.text(self.head, f"{riders} aboard", TEXT), (x, y))
        note = f"{shown} in this car" if shown < riders else "everyone in this car"
        screen.blit(sprites.text(self.small, note, MUTED), (x + 100, y + 2))
        if self._dwelling():
            hovering = self.leave_rect.collidepoint(self.mouse)
            pygame.draw.rect(screen, (70, 150, 96) if hovering else (52, 118, 76), self.leave_rect, border_radius=8)
            label = sprites.text(self.head, f"LEAVE AT {self.metro.current_station.upper()}"[:34], TEXT)
            screen.blit(label, label.get_rect(center=self.leave_rect.center))
        else:
            hint = sprites.text(self.small, "doors open at the next stop", MUTED)
            screen.blit(hint, hint.get_rect(midright=(self.leave_rect.right, self.leave_rect.centery)))

        # Line diagram: every stop as a dot, the train as a marker.
        stops = self.line.stations
        left, right = 70, WINDOW_W - 70
        ly = BOARD.y + 120
        step = (right - left) / max(len(stops) - 1, 1)
        pygame.draw.line(screen, shade(self.line.color, -60), (left, ly), (right, ly), 6)
        pygame.draw.line(screen, self.line.color, (left, ly), (right, ly), 4)
        for i, name in enumerate(stops):
            sx = round(left + i * step)
            served = len(self.world.map.lines_at(name)) > 1
            pygame.draw.circle(screen, OUTLINE, (sx, ly), 7 if served else 5)
            pygame.draw.circle(screen, (255, 255, 255), (sx, ly), 5 if served else 3)
            label = sprites.text(self.tiny, name, TEXT if name in (self.metro.current_station, self._next_stop()) else MUTED)
            if i % 2 == 0:
                screen.blit(label, label.get_rect(midtop=(sx, ly + 14)))
            else:
                screen.blit(label, label.get_rect(midbottom=(sx, ly - 14)))
        here = stops.index(self.metro.current_station)
        if self._dwelling() or self.metro.destination is None:
            pos = here
        else:
            pos = here + (stops.index(self.metro.destination) - here) * smoothstep(self.metro.progress)
        mx = round(left + pos * step)
        marker = pygame.Rect(0, 0, 22, 12)
        marker.center = (mx, ly)
        pygame.draw.rect(screen, OUTLINE, marker.inflate(2, 2), border_radius=4)
        pygame.draw.rect(screen, SILVER, marker, border_radius=4)
        pygame.draw.rect(screen, BAND, (marker.x + 3, marker.y + 3, marker.width - 6, 4))
        hint = sprites.text(self.small, "Esc or MAP leaves the ride.   E or the button gets off at a stop.   Hover a rider for their destination.", MUTED)
        screen.blit(hint, (24, WINDOW_H - 28))

    def _draw_tooltip(self, screen) -> None:
        if self.hover is None:
            return
        _, passenger, (wx, wy) = self.hover
        lines = [f"to {passenger.destination}"]
        if passenger.changes:
            lines.append(f"changes at {passenger.alight_at}")
        rendered = [sprites.text(self.small, t, TEXT) for t in lines]
        rect = pygame.Rect(0, 0, max(r.get_width() for r in rendered) + 16, sum(r.get_height() for r in rendered) + 12)
        rect.midbottom = (round(wx * PIX), round(VIEW.y + wy * PIX))
        rect.clamp_ip(screen.get_rect())
        pygame.draw.rect(screen, (20, 22, 27), rect, border_radius=6)
        pygame.draw.rect(screen, PANEL_EDGE, rect, 1, border_radius=6)
        ty = rect.y + 6
        for r in rendered:
            screen.blit(r, (rect.x + 8, ty))
            ty += r.get_height()
