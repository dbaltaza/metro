
import math
from typing import Callable

import pygame

from src import sprites
from src.metro import Metro
from src.network import Line, Map, Station
from src.paths import resource
from src.sim import Simulation
from src.sprites import OUTLINE, shade

WINDOW_W, WINDOW_H = 1280, 840
PANEL_W = 290
MAP_RECT = pygame.Rect(0, 0, WINDOW_W - PANEL_W, WINDOW_H)
MARGIN = 84
FPS = 60

# The map world is drawn at half size and scaled up with no smoothing, the
# same trick as the station scene, so both share one pixel look.
PIX = 2
MAP_IW, MAP_IH = MAP_RECT.width // PIX, MAP_RECT.height // PIX

GROUND_A = (41, 43, 50)
GROUND_B = (37, 39, 46)
GROUT = (31, 33, 39)
BLOCK = (34, 36, 43)
BLOCK_EDGE = (48, 50, 58)
TRACK_BED = (22, 22, 27)
TRACK_BED_W = 6
RAIL_W = 3

ROOF = (156, 152, 146)
FRONT = (98, 94, 88)
DOOR = (30, 30, 36)
SIGN_LIT = (255, 226, 140)
BUILDING = (12, 10)
INTERCHANGE_BUILDING = (16, 12)

LABEL_COLOR = (208, 212, 222)
LABEL_SIZE = 12
LABEL_GAP = 6.0
METER_GAP = 3.0
# Waiting counts at which the three load pips light up, and their colours.
LOAD_STEPS = (6, 16, 30)
LOAD_COLORS = ((92, 190, 110), (236, 182, 62), (226, 84, 72))
PIP_OFF = (52, 54, 62)

PANEL_BG = (24, 26, 31)
PANEL_EDGE = (58, 62, 72)
TEXT = (228, 231, 237)
MUTED = (138, 144, 156)
HIGHLIGHT = (255, 214, 90)

TRAIN_L, TRAIN_H = 20, 9

# Label placement searches these eight directions around a station and scores
# each. Bigger penalties beat smaller ones, so the weights matter, not order.
CANDIDATE_DIRECTIONS = [
    (1.0, 0.0), (-1.0, 0.0), (0.0, -1.0), (0.0, 1.0),
    (0.7071, -0.7071), (0.7071, 0.7071), (-0.7071, -0.7071), (-0.7071, 0.7071),
]
CANDIDATE_DISTANCES = [1.0, 1.7, 2.6, 3.8]
PENALTY_OFFSCREEN = 10000.0
PENALTY_LABEL_OVERLAP = 420.0
PENALTY_STOP_OVERLAP = 360.0
PENALTY_TRACK_TOUCH = 22.0
PENALTY_OFF_PREFERRED = 34.0
PENALTY_PER_STEP = 26.0
LABEL_PADDING = 2
TRACK_SAMPLE_STEP = 5.0

Projection = Callable[[Station], tuple[float, float]]
Vector = tuple[float, float]


# --- geometry ------------------------------------------------------------------

def make_projection(metro_map: Map, area: pygame.Rect = MAP_RECT) -> Projection:
    """Fit the network's bounding box into the map area, preserving aspect."""
    xs = [s.x for s in metro_map.stations.values()]
    ys = [s.y for s in metro_map.stations.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width, height = max_x - min_x, max_y - min_y
    scale = min(
        (area.width - 2 * MARGIN) / max(width, 1),
        (area.height - 2 * MARGIN) / max(height, 1),
    )
    offset_x = area.x + (area.width - width * scale) / 2
    offset_y = area.y + (area.height - height * scale) / 2

    def project(station: Station) -> Vector:
        return offset_x + (station.x - min_x) * scale, offset_y + (station.y - min_y) * scale

    return project


def neighbours(metro_map: Map, station_name: str) -> list[str]:
    found: list[str] = []
    for line in metro_map.lines:
        if station_name not in line.stations:
            continue
        i = line.stations.index(station_name)
        if i > 0:
            found.append(line.stations[i - 1])
        if i + 1 < len(line.stations):
            found.append(line.stations[i + 1])
    return found


def lines_serving(metro_map: Map, station_name: str) -> list[Line]:
    return [line for line in metro_map.lines if station_name in line.stations]


def is_interchange(metro_map: Map, station_name: str) -> bool:
    return len(lines_serving(metro_map, station_name)) > 1


def building_size(metro_map: Map, station_name: str) -> tuple[int, int]:
    return INTERCHANGE_BUILDING if is_interchange(metro_map, station_name) else BUILDING


def track_direction(metro_map: Map, station: Station) -> Vector:
    for other_name in neighbours(metro_map, station.name):
        other = metro_map.stations[other_name]
        dx, dy = other.x - station.x, other.y - station.y
        length = math.hypot(dx, dy)
        if length:
            return dx / length, dy / length
    return 1.0, 0.0


def label_direction(metro_map: Map, station: Station) -> Vector:
    vectors: list[Vector] = []
    for other_name in neighbours(metro_map, station.name):
        other = metro_map.stations[other_name]
        dx, dy = other.x - station.x, other.y - station.y
        length = math.hypot(dx, dy)
        if length:
            vectors.append((dx / length, dy / length))
    if not vectors:
        return 1.0, 0.0
    sum_x = sum(v[0] for v in vectors)
    sum_y = sum(v[1] for v in vectors)
    magnitude = math.hypot(sum_x, sum_y)
    if magnitude > 0.4:
        return -sum_x / magnitude, -sum_y / magnitude
    perp = (-vectors[0][1], vectors[0][0])
    away = (station.x - 500, station.y - 500)
    if perp[0] * away[0] + perp[1] * away[1] < 0:
        perp = (-perp[0], -perp[1])
    return perp


# --- labels ---------------------------------------------------------------------

def anchor_rect(label: pygame.Surface, center: Vector, direction: Vector, offset: float) -> pygame.Rect:
    dir_x, dir_y = direction
    anchor_x, anchor_y = center[0] + dir_x * offset, center[1] + dir_y * offset
    rect = label.get_rect()
    if dir_x > 0.3:
        rect.left = round(anchor_x)
    elif dir_x < -0.3:
        rect.right = round(anchor_x)
    else:
        rect.centerx = round(anchor_x)
    if dir_y > 0.3:
        rect.top = round(anchor_y)
    elif dir_y < -0.3:
        rect.bottom = round(anchor_y)
    else:
        rect.centery = round(anchor_y)
    return rect


def track_samples(metro_map: Map, project: Projection) -> list[Vector]:
    points: list[Vector] = []
    for line in metro_map.lines:
        coords = [project(metro_map.stations[n]) for n in line.stations]
        for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
            steps = max(int(math.hypot(x2 - x1, y2 - y1) / TRACK_SAMPLE_STEP), 1)
            for k in range(steps + 1):
                t = k / steps
                points.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return points


def placement_penalty(rect, direction, preferred, bounds, placed, stops, tracks) -> float:
    if not bounds.contains(rect):
        return PENALTY_OFFSCREEN
    padded = rect.inflate(LABEL_PADDING * 2, LABEL_PADDING * 2)
    penalty = 0.0
    penalty += PENALTY_LABEL_OVERLAP * sum(padded.colliderect(r) for r in placed)
    penalty += PENALTY_STOP_OVERLAP * sum(padded.colliderect(r) for r in stops)
    penalty += PENALTY_TRACK_TOUCH * sum(padded.collidepoint(p) for p in tracks)
    alignment = direction[0] * preferred[0] + direction[1] * preferred[1]
    return penalty + (1.0 - alignment) * PENALTY_OFF_PREFERRED


def draw_labels(surface, metro_map: Map, project: Projection, font, bold_font) -> dict[str, Vector]:
    """Place every station name and return the direction each one went."""
    bounds = MAP_RECT
    tracks = track_samples(metro_map, project)
    stops: list[pygame.Rect] = []
    for station in metro_map.stations.values():
        w, h = building_size(metro_map, station.name)
        half = max(w, h) * PIX / 2 + (METER_GAP + 4) * PIX
        rect = pygame.Rect(0, 0, round(half * 2), round(half * 2))
        rect.center = tuple(round(c) for c in project(station))
        stops.append(rect)

    ordered = sorted(metro_map.stations.values(), key=lambda s: -len(lines_serving(metro_map, s.name)))
    placed: list[pygame.Rect] = []
    chosen: dict[str, Vector] = {}
    for station in ordered:
        interchange = is_interchange(metro_map, station.name)
        chosen_font = bold_font if interchange else font
        label = chosen_font.render(station.name, True, LABEL_COLOR)
        center = project(station)
        preferred = label_direction(metro_map, station)
        w, h = building_size(metro_map, station.name)
        offset = max(w, h) * PIX / 2 + LABEL_GAP

        best = None
        for multiplier in CANDIDATE_DISTANCES:
            for direction in CANDIDATE_DIRECTIONS:
                rect = anchor_rect(label, center, direction, offset * multiplier)
                penalty = placement_penalty(rect, direction, preferred, bounds, placed, stops, tracks)
                penalty += (multiplier - 1.0) * PENALTY_PER_STEP
                if best is None or penalty < best[0]:
                    best = (penalty, rect, direction)
        assert best is not None
        _, rect, direction = best
        rect.clamp_ip(bounds)
        placed.append(rect)
        chosen[station.name] = direction
        # A dark halo behind the text keeps it readable over tracks.
        halo = chosen_font.render(station.name, True, OUTLINE)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            surface.blit(halo, rect.move(dx, dy))
        surface.blit(label, rect)
    return chosen


# --- world ------------------------------------------------------------------------

class World:
    """The static map picture, per-station geometry, and sprite caches."""

    def __init__(self, metro_map: Map):
        self.map = metro_map
        self.project = make_projection(metro_map)
        self.font = pygame.font.SysFont("helvetica,arial", LABEL_SIZE)
        self.bold = pygame.font.SysFont("helvetica,arial", LABEL_SIZE, bold=True)
        self.serving = {n: lines_serving(metro_map, n) for n in metro_map.stations}
        self.positions = {n: self.project(s) for n, s in metro_map.stations.items()}
        self.ipositions = {n: (x / PIX, y / PIX) for n, (x, y) in self.positions.items()}
        # 24-bit on purpose: a 32-bit surface without SRCALPHA still carries
        # alpha bytes, and sprite blits leave them at zero, which breaks every
        # later alpha blend over those pixels on a real display.
        self.world = pygame.Surface((MAP_IW, MAP_IH), 0, 24)
        self.base = self._render_base()
        self.labels = pygame.Surface(MAP_RECT.size, pygame.SRCALPHA)
        self.label_dirs = draw_labels(self.labels, metro_map, self.project, self.font, self.bold)
        self.meters = self._meter_layouts()
        self.train_sprites = {line.name: self._train_sprite(line.color) for line in metro_map.lines}

    # -- static picture (world pixels) ------------------------------------------

    def _render_base(self) -> pygame.Surface:
        s = pygame.Surface((MAP_IW, MAP_IH), 0, 24)
        pygame.draw.rect(s, GROUT, s.get_rect())
        tile = 8
        for ty in range(0, MAP_IH, tile):
            for tx in range(0, MAP_IW, tile):
                color = GROUND_A if (tx // tile + ty // tile) % 2 == 0 else GROUND_B
                pygame.draw.rect(s, color, (tx, ty, tile - 1, tile - 1))
        self._draw_tracks(s)
        for name in self.map.stations:
            self._draw_building(s, name)
        return s

    def _draw_tracks(self, s: pygame.Surface) -> None:
        routes = [(line, [self.ipositions[n] for n in line.stations]) for line in self.map.lines]
        for _, points in routes:
            for a, b in zip(points, points[1:]):
                pygame.draw.line(s, TRACK_BED, a, b, TRACK_BED_W)
            for p in points:
                pygame.draw.circle(s, TRACK_BED, p, TRACK_BED_W / 2)
        for _, points in routes:
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                length = math.hypot(x2 - x1, y2 - y1)
                if not length:
                    continue
                ux, uy = (x2 - x1) / length, (y2 - y1) / length
                px, py = -uy, ux
                for k in range(2, int(length / 5)):
                    cx, cy = x1 + ux * k * 5, y1 + uy * k * 5
                    pygame.draw.line(s, shade(TRACK_BED, 22), (cx - px * 2, cy - py * 2), (cx + px * 2, cy + py * 2))
        for line, points in routes:
            for a, b in zip(points, points[1:]):
                pygame.draw.line(s, line.color, a, b, RAIL_W)
            for p in points:
                pygame.draw.circle(s, line.color, p, RAIL_W / 2)

    def building_rect(self, name: str) -> pygame.Rect:
        w, h = building_size(self.map, name)
        rect = pygame.Rect(0, 0, w, h)
        x, y = self.ipositions[name]
        rect.center = (round(x), round(y))
        return rect

    def _draw_building(self, s: pygame.Surface, name: str) -> None:
        rect = self.building_rect(name)
        roof_h = rect.height // 2
        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 90))
        s.blit(shadow, (rect.x + 2, rect.y + 3))
        pygame.draw.rect(s, OUTLINE, rect.inflate(2, 2))
        pygame.draw.rect(s, ROOF, (rect.x, rect.y, rect.width, roof_h))
        pygame.draw.line(s, shade(ROOF, 30), (rect.x, rect.y), (rect.right - 1, rect.y))
        pygame.draw.rect(s, FRONT, (rect.x, rect.y + roof_h, rect.width, rect.height - roof_h))
        pygame.draw.line(s, shade(FRONT, -30), (rect.x, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
        serving = self.serving[name]
        stripe_w = rect.width / len(serving)
        for i, line in enumerate(serving):
            pygame.draw.rect(s, line.color, (round(rect.x + i * stripe_w), rect.y + 1, math.ceil(stripe_w), 2))
        door = pygame.Rect(0, 0, 3, 4)
        door.midbottom = (rect.centerx, rect.bottom - 1)
        pygame.draw.rect(s, DOOR, door)
        pygame.draw.rect(s, SIGN_LIT, (rect.centerx - 2, rect.y + roof_h + 1, 4, 1))

    # -- crowds -------------------------------------------------------------------

    def _meter_layouts(self) -> dict[str, tuple[Vector, Vector]]:
        """Where each station's load meter sits: beside the building, on the
        side the label left free, with the pips laid along the track."""
        layouts = {}
        for name, station in self.map.stations.items():
            tx, ty = track_direction(self.map, station)
            side = (-ty, tx)
            lx, ly = self.label_dirs[name]
            if side[0] * lx + side[1] * ly > 0:
                side = (-side[0], -side[1])
            rect = self.building_rect(name)
            gap = max(rect.width, rect.height) / 2 + METER_GAP
            layouts[name] = ((rect.centerx + side[0] * gap, rect.centery + side[1] * gap), (tx, ty))
        return layouts

    def station_at(self, pos: Vector) -> str | None:
        best, best_d = None, 18.0
        for name, (x, y) in self.positions.items():
            d = math.hypot(pos[0] - x, pos[1] - y)
            if d < best_d:
                best, best_d = name, d
        return best

    # -- trains -------------------------------------------------------------------

    @staticmethod
    def _train_sprite(color) -> pygame.Surface:
        s = pygame.Surface((TRAIN_L, TRAIN_H), pygame.SRCALPHA)
        body = pygame.Rect(1, 1, TRAIN_L - 2, TRAIN_H - 2)
        pygame.draw.rect(s, OUTLINE, body.inflate(2, 2), border_radius=2)
        pygame.draw.rect(s, shade(color, 36), (body.x, body.y, body.width, 3))
        pygame.draw.rect(s, color, (body.x, body.y + 3, body.width, 3))
        pygame.draw.rect(s, shade(color, -60), (body.x, body.y + 6, body.width, 1))
        for wx in range(body.x + 3, body.right - 3, 4):
            pygame.draw.rect(s, (200, 236, 255), (wx, body.y + 3, 2, 2))
        pygame.draw.rect(s, (255, 244, 190), (body.right - 2, body.y + 4, 1, 2))
        return s


# --- per-frame drawing -------------------------------------------------------------

def draw_load(world: World, sim: Simulation) -> None:
    """Three pips beside each station that light up as the crowd grows."""
    s = world.world
    for name, station in world.map.stations.items():
        count = len(station.waiting)
        (ax, ay), (tx, ty) = world.meters[name]
        for k, threshold in enumerate(LOAD_STEPS):
            along = (k - 1) * 4
            x, y = round(ax + tx * along), round(ay + ty * along)
            color = LOAD_COLORS[k] if count >= threshold else PIP_OFF
            pygame.draw.rect(s, OUTLINE, (x - 2, y - 2, 4, 4))
            pygame.draw.rect(s, color, (x - 1, y - 1, 2, 2))


def train_position(world: World, metro: Metro) -> tuple[Vector, float]:
    x1, y1 = world.ipositions[metro.current_station]
    if metro.destination is None or metro.cooldown > 0:
        heading = world.ipositions.get(metro.destination or metro.current_station)
        x2, y2 = heading if heading else (x1 + 1, y1)
        t = 0.0
    else:
        x2, y2 = world.ipositions[metro.destination]
        t = metro.progress
    angle = -math.degrees(math.atan2(y2 - y1, x2 - x1))
    return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t), angle


def draw_trains(world: World, sim: Simulation) -> list[tuple[Metro, Vector]]:
    """Draw trains into the world surface; return screen positions for badges."""
    s = world.world
    placed = []
    for metro in sim.metros:
        (x, y), angle = train_position(world, metro)
        base = world.train_sprites[metro.line]
        sprite = sprites.rotated(id(base), base, angle)
        s.blit(sprite, sprite.get_rect(center=(round(x), round(y))))
        placed.append((metro, (x * PIX, y * PIX)))
    return placed


def draw_hover(world: World, name: str | None, color) -> None:
    if name is None:
        return
    rect = world.building_rect(name).inflate(6, 6)
    pygame.draw.rect(world.world, color, rect, 1)


def draw_haloed(screen, font, string, color, center) -> None:
    """Small text with a dark outline, readable over any background."""
    halo = sprites.text(font, string, OUTLINE)
    body = sprites.text(font, string, color)
    rect = body.get_rect(center=center)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        screen.blit(halo, rect.move(dx, dy))
    screen.blit(body, rect)


# --- side panel -----------------------------------------------------------------

class Panel:
    """Right-hand panel: score, fleet controls, event log, hovered station."""

    def __init__(self):
        self.rect = pygame.Rect(MAP_RECT.right, 0, PANEL_W, WINDOW_H)
        self.title = pygame.font.SysFont("helvetica,arial", 20, bold=True)
        self.head = pygame.font.SysFont("helvetica,arial", 14, bold=True)
        self.body = pygame.font.SysFont("helvetica,arial", 13)
        self.small = pygame.font.SysFont("helvetica,arial", 11)
        self.buttons: list[tuple[pygame.Rect, str, str]] = []  # rect, action, line
        self.mouse = (0, 0)

    def _text(self, surface, font, string, x, y, color=TEXT) -> int:
        rendered = sprites.text(font, string, color)
        surface.blit(rendered, (x, y))
        return y + rendered.get_height()

    def _rule(self, surface, y: int) -> int:
        pygame.draw.line(surface, PANEL_EDGE, (self.rect.x + 18, y), (self.rect.right - 18, y))
        return y + 12

    def _button(self, surface, x: int, y: int, label: str, action: str, line: str) -> pygame.Rect:
        rect = pygame.Rect(x, y, 22, 20)
        hovering = rect.collidepoint(self.mouse)
        pygame.draw.rect(surface, (58, 64, 76) if hovering else (40, 44, 52), rect, border_radius=5)
        text = sprites.text(self.head, label, TEXT)
        surface.blit(text, text.get_rect(center=rect.center))
        self.buttons.append((rect, action, line))
        return rect

    def click(self, pos) -> tuple[str, str] | None:
        for rect, action, line in self.buttons:
            if rect.collidepoint(pos):
                return action, line
        return None

    def draw(self, surface, world: World, sim: Simulation, selected: str | None, paused: bool, speed: float = 1.0) -> None:
        self.buttons = []
        pygame.draw.rect(surface, PANEL_BG, self.rect)
        pygame.draw.line(surface, PANEL_EDGE, self.rect.topleft, self.rect.bottomleft, 2)
        x, y = self.rect.x + 18, 18

        minutes, seconds = divmod(int(sim.clock), 60)
        y = self._text(surface, self.title, "Metro de Lisboa", x, y)
        status = f"{minutes:02d}:{seconds:02d}   {speed:g}x" + ("   PAUSED" if paused else "")
        y = self._text(surface, self.body, status, x, y + 2, MUTED)
        y = self._text(surface, self.small, "1 2 3 set speed   Space pauses", x, y + 2, MUTED) + 10
        y = self._rule(surface, y)

        # Score: what a dispatcher cares about.
        y = self._text(surface, self.head, "Score", x, y)
        y = self._text(surface, self.body, f"Average wait   {sim.average_wait():.0f}s", x, y + 4)
        y = self._text(surface, self.body, f"Delivered      {sim.delivered_per_minute():.0f} per min", x, y + 2)
        y = self._text(surface, self.small, f"waiting {sim.waiting_total()}   delivered {sim.delivered}   changes {sim.transfers}", x, y + 2, MUTED) + 10
        y = self._rule(surface, y)

        # Fleet: one lever per line.
        y = self._text(surface, self.head, "Fleet", x, y) + 6
        for line in world.map.lines:
            pygame.draw.circle(surface, line.color, (x + 5, y + 10), 5)
            count = len(sim.trains_on(line.name))
            self._text(surface, self.body, f"{line.name}", x + 16, y + 2)
            self._text(surface, self.small, f"{count} trains", x + 16, y + 17, MUTED)
            self._button(surface, self.rect.right - 70, y + 4, "-", "remove", line.name)
            self._button(surface, self.rect.right - 42, y + 4, "+", "add", line.name)
            y += 32
        y = self._rule(surface, y + 4)

        # Event log.
        if sim.log:
            y = self._text(surface, self.head, "Events", x, y) + 4
            width = self.rect.right - 18 - x
            for when, text in reversed(sim.log[-4:]):
                m, s_ = divmod(int(when), 60)
                line = f"{m:02d}:{s_:02d}  {text}"
                while self.small.size(line)[0] > width and len(line) > 12:
                    line = line[:-2].rstrip() + "…"
                y = self._text(surface, self.small, line, x, y, MUTED) + 2
            y = self._rule(surface, y + 8)

        if selected is None:
            self._text(surface, self.body, "Hover a station to preview it.", x, y, MUTED)
            self._text(surface, self.body, "Click to walk inside.", x, y + 20, MUTED)
            return

        station = world.map.stations[selected]
        y = self._text(surface, self.title, selected, x, y)
        y = self._text(surface, self.small, "click to enter", x, y + 2, HIGHLIGHT) + 6
        for line in world.serving[selected]:
            pygame.draw.circle(surface, line.color, (x + 5, y + 7), 5)
            y = self._text(surface, self.body, line.name, x + 16, y, MUTED) + 2
        y += 8
        trains = sim.trains_at(selected)
        if trains:
            y = self._text(surface, self.head, "At the platform", x, y)
            y = self._text(surface, self.body, ", ".join(f"#{m.id} ({len(m.riders)} aboard)" for m in trains), x, y + 2, MUTED) + 8
        y = self._text(surface, self.head, f"Waiting  {len(station.waiting)}", x, y) + 6
        if not station.waiting:
            self._text(surface, self.body, "Nobody here right now.", x, y, MUTED)
            return
        shown = station.waiting[:max(1, (WINDOW_H - y - 30) // 19)]
        for passenger in shown:
            surface.blit(pygame.transform.scale(sprites.tiny_person(passenger.id), (10, 16)), (x, y))
            via = f"  via {passenger.alight_at}" if passenger.changes else ""
            self._text(surface, self.body, f"to {passenger.destination}{via}", x + 16, y, TEXT)
            y += 19
        if len(station.waiting) > len(shown):
            self._text(surface, self.small, f"and {len(station.waiting) - len(shown)} more", x, y, MUTED)


# --- scenes and main loop -------------------------------------------------------

class Transition:
    """Metro doors sliding shut over the screen, a beat with the station name
    and a loading bar, then sliding open on the new scene."""

    CLOSE, HOLD, OPEN = 0.32, 0.7, 0.4
    DOOR = (22, 24, 30)
    DOOR_EDGE = (48, 52, 62)
    GLASS = (58, 78, 98)

    def __init__(self, target: str | None, color, title: str, subtitle: str):
        self.target = target
        self.color = color
        self.title = title
        self.subtitle = subtitle
        self.t = 0.0
        self.phase = "close"
        self.swapped = False
        self.big = pygame.font.SysFont("helvetica,arial", 34, bold=True)
        self.small = pygame.font.SysFont("helvetica,arial", 15)

    def update(self, dt: float) -> bool:
        self.t += dt
        if self.phase == "close" and self.t >= self.CLOSE:
            self.phase, self.t = "hold", 0.0
        elif self.phase == "hold" and self.t >= self.HOLD:
            self.phase, self.t = "open", 0.0
        elif self.phase == "open" and self.t >= self.OPEN:
            return True
        return False

    def wants_swap(self) -> bool:
        return self.phase == "hold" and not self.swapped

    def _coverage(self) -> float:
        if self.phase == "close":
            return 1 - (1 - self.t / self.CLOSE) ** 3
        if self.phase == "hold":
            return 1.0
        return (1 - self.t / self.OPEN) ** 3

    def draw(self, screen: pygame.Surface) -> None:
        k = self._coverage()
        width = round(WINDOW_W / 2 * k)
        if width <= 0:
            return
        for rect in (pygame.Rect(0, 0, width, WINDOW_H), pygame.Rect(WINDOW_W - width, 0, width, WINDOW_H)):
            pygame.draw.rect(screen, self.DOOR, rect)
            inner_x = rect.right - 1 if rect.x == 0 else rect.x
            pygame.draw.line(screen, self.DOOR_EDGE, (inner_x, 0), (inner_x, WINDOW_H), 2)
            stripe = pygame.Rect(0, 0, 8, WINDOW_H)
            stripe.x = rect.right - 14 if rect.x == 0 else rect.x + 6
            pygame.draw.rect(screen, self.color, stripe)
            glass = pygame.Rect(0, 0, 120, 260)
            glass.centery = WINDOW_H // 2 - 120
            glass.centerx = rect.right - 120 if rect.x == 0 else rect.x + 120
            if rect.width > 200:
                pygame.draw.rect(screen, self.GLASS, glass, border_radius=8)
                pygame.draw.rect(screen, self.DOOR_EDGE, glass, 2, border_radius=8)
        if k < 0.92:
            return
        cx, cy = WINDOW_W // 2, WINDOW_H // 2 + 60
        title = sprites.text(self.big, self.title, TEXT)
        sub = sprites.text(self.small, self.subtitle, MUTED)
        screen.blit(title, title.get_rect(center=(cx, cy)))
        screen.blit(sub, sub.get_rect(center=(cx, cy + 34)))
        bar = pygame.Rect(0, 0, 240, 6)
        bar.center = (cx, cy + 66)
        pygame.draw.rect(screen, self.DOOR_EDGE, bar, border_radius=3)
        fill = 0.0 if self.phase == "close" else (self.t / self.HOLD if self.phase == "hold" else 1.0)
        pygame.draw.rect(screen, self.color, (bar.x, bar.y, round(bar.width * fill), bar.height), border_radius=3)


class StepTransition(Transition):
    """Stepping through a train door. The view rushes into the door and goes
    dark, a beat with the door chime, then the new scene pulls back from its
    own door. Used between a platform and the inside of a train."""

    CLOSE, HOLD, OPEN = 0.42, 0.5, 0.55
    ZOOM_IN = 2.4      # how far the old view rushes into the door
    ZOOM_OUT = 1.35    # how far the new view starts zoomed before settling
    CHIME = (255, 196, 60)

    def __init__(self, target, color, title: str, subtitle: str, focus_out, focus_in):
        super().__init__(target, color, title, subtitle)
        self.focus_out = focus_out          # screen point of the door being entered
        self.focus_in = focus_in            # screen point, or a callable(scene) -> point
        self.snapshot: pygame.Surface | None = None
        self.scene = None                   # the new scene, set by the loop at swap

    def _coverage(self) -> float:
        # Kept for anything that reads it; the step draws its own phases.
        return 1.0 if self.phase == "hold" else 0.0

    @staticmethod
    def _zoomed(screen: pygame.Surface, frame: pygame.Surface, focus, zoom: float) -> None:
        """Blit frame scaled by zoom so that the focus point stays put."""
        w, h = round(WINDOW_W * zoom), round(WINDOW_H * zoom)
        fx, fy = focus
        screen.blit(pygame.transform.scale(frame, (w, h)), (round(fx - fx * zoom), round(fy - fy * zoom)))

    def _dim(self, screen: pygame.Surface, amount: float) -> None:
        if amount <= 0:
            return
        veil = pygame.Surface((WINDOW_W, WINDOW_H))
        veil.fill((8, 8, 10))
        veil.set_alpha(round(255 * min(amount, 1.0)))
        screen.blit(veil, (0, 0))

    def _resolved_focus_in(self):
        if callable(self.focus_in):
            return self.focus_in(self.scene) if self.scene is not None else (WINDOW_W / 2, WINDOW_H / 2)
        return self.focus_in

    def draw(self, screen: pygame.Surface) -> None:
        if self.phase == "close":
            if self.snapshot is None:
                self.snapshot = screen.copy()
            k = min(self.t / self.CLOSE, 1.0)
            ease = k * k * k
            self._zoomed(screen, self.snapshot, self.focus_out, 1 + (self.ZOOM_IN - 1) * ease)
            self._dim(screen, k * k * 1.15)
            return
        if self.phase == "hold":
            screen.fill((8, 8, 10))
            self._caption(screen, self.t / self.HOLD)
            return
        k = 1 - min(self.t / self.OPEN, 1.0)
        ease = k * k
        frame = screen.copy()
        self._zoomed(screen, frame, self._resolved_focus_in(), 1 + (self.ZOOM_OUT - 1) * ease)
        self._dim(screen, ease * 1.3)
        if k > 0.55:
            self._caption(screen, 1.0, fade=(k - 0.55) / 0.45)

    def _caption(self, screen: pygame.Surface, progress: float, fade: float = 1.0) -> None:
        cx, cy = WINDOW_W // 2, WINDOW_H // 2 + 40
        title = sprites.text(self.big, self.title, TEXT)
        sub = sprites.text(self.small, self.subtitle, MUTED)
        if fade < 1.0:
            title = title.copy(); title.set_alpha(round(255 * fade))
            sub = sub.copy(); sub.set_alpha(round(255 * fade))
        screen.blit(title, title.get_rect(center=(cx, cy)))
        screen.blit(sub, sub.get_rect(center=(cx, cy + 34)))
        # The door chime: three lamps lighting up one after another.
        for i in range(3):
            lit = progress * 3 >= i + 0.5
            color = self.CHIME if lit else self.DOOR_EDGE
            if fade < 1.0 and not lit:
                continue
            pygame.draw.circle(screen, color, (cx - 22 + i * 22, cy - 46), 5)
            if lit:
                pygame.draw.circle(screen, (255, 240, 190), (cx - 22 + i * 22, cy - 46), 2)


class MapScene:
    """The network overview. Hover to preview a station, click to enter it."""

    def __init__(self, world: World, sim: Simulation):
        self.world = world
        self.sim = sim
        self.panel = Panel()
        self.badge_font = pygame.font.SysFont("helvetica,arial", 10, bold=True)
        self.hovered: str | None = None

    def handle(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.MOUSEMOTION:
            self.panel.mouse = event.pos
            self.hovered = self.world.station_at(event.pos) if MAP_RECT.collidepoint(event.pos) else None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if MAP_RECT.collidepoint(event.pos):
                return self.world.station_at(event.pos)
            action = self.panel.click(event.pos)
            if action == None:
                return None
            kind, line = action
            if kind == "add":
                self.sim.add_train(line)
            else:
                self.sim.remove_train(line)
        return None

    def draw(self, screen: pygame.Surface, paused: bool, speed: float = 1.0) -> None:
        world = self.world
        world.world.blit(world.base, (0, 0))
        draw_load(world, self.sim)
        draw_hover(world, self.hovered, HIGHLIGHT)
        trains = draw_trains(world, self.sim)
        screen.blit(pygame.transform.scale(world.world, MAP_RECT.size), MAP_RECT.topleft)
        screen.blit(world.labels, MAP_RECT.topleft)

        # Stalled trains get a warning mark; held ones a small pause bar.
        for metro, (x, y) in trains:
            if metro.stalled > 0:
                draw_haloed(screen, self.badge_font, "!", (255, 110, 96), (round(x), round(y) - 16))
        # The only other number on the map: the waiting count of the hovered station.
        if self.hovered:
            count = len(world.map.stations[self.hovered].waiting)
            rect = world.building_rect(self.hovered)
            draw_haloed(screen, self.badge_font, f"{count} waiting", TEXT, (rect.centerx * PIX, rect.top * PIX - 12))
        self.panel.draw(screen, world, self.sim, self.hovered, paused, speed)


def run(sim: Simulation) -> None:
    # Imported here because the scenes import constants from this file.
    from src.ride_view import RideView
    from src.station_view import StationView

    pygame.init()
    icon = resource("docs", "icon.png")
    if icon.exists():
        pygame.display.set_icon(pygame.image.load(str(icon)))
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Metro Lisboa")
    clock = pygame.time.Clock()
    world = World(sim.map)
    map_scene = MapScene(world, sim)
    scene = None  # None is the map; otherwise a StationView or RideView
    transition: Transition | None = None

    from src.ride_view import DOOR_XS, FAR_WALL
    from src.station_layout import IW, ROOF_H, SIDE_H, VIEW

    def ride_door(near_x: float | None = None) -> tuple[float, float]:
        """Screen point of the car door nearest to near_x in the ride view."""
        xs = [d * PIX for d in DOOR_XS]
        x = min(xs, key=lambda v: abs(v - (WINDOW_W / 2 if near_x is None else near_x)))
        return (x, VIEW.y + FAR_WALL.centery * PIX)

    def platform_door(view, metro) -> tuple[float, float]:
        """Screen point of the train's doors as seen from the platform."""
        x = view._train_x(metro)
        pit = view._pit_for(view._side(metro))
        return ((IW / 2 if x is None else x) * PIX, VIEW.y + (pit.top + ROOF_H + SIDE_H / 2) * PIX)

    def go(target) -> Transition:
        """Start a transition towards a target: ("map",), ("station", name)
        or ("ride", metro). Moves between the map and a station use the
        sliding doors; stepping on or off a train zooms through its door."""
        if target[0] == "map":
            return Transition(target, HIGHLIGHT, "Metro de Lisboa", "back to the network")
        if target[0] == "station":
            color = world.serving[target[1]][0].color
            if isinstance(scene, RideView):
                metro = scene.metro
                return StepTransition(target, color, target[1], "leaving the train",
                                      ride_door(pygame.mouse.get_pos()[0]),
                                      lambda view: platform_door(view, metro))
            return Transition(target, color, target[1], "entering the station")
        metro = target[1]
        color = sim.map.line_named(metro.line).color
        if isinstance(scene, StationView):
            return StepTransition(target, color, f"Train #{metro.id}", "mind the gap",
                                  pygame.mouse.get_pos(), ride_door())
        return Transition(target, color, f"Train #{metro.id}", "mind the gap")

    paused = False
    speed = 1.0
    speeds = {pygame.K_1: 1.0, pygame.K_2: 2.0, pygame.K_3: 4.0}
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.1)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                paused = not paused
            elif event.type == pygame.KEYDOWN and event.key in speeds:
                speed = speeds[event.key]
            elif transition is not None:
                continue
            elif scene is not None:
                result = scene.handle(event)
                if result == "back":
                    transition = go(("map",))
                elif isinstance(result, tuple):
                    transition = go(result)
            else:
                target = map_scene.handle(event)
                if target:
                    transition = go(("station", target))

        # Simulation and the scenes' animations run on scaled time, so the
        # boarding choreography keeps pace with the trains at any speed.
        sim_dt = 0.0 if paused else dt * speed
        sim.update(sim_dt)
        events = sim.drain_events()
        if scene is not None:
            forced = scene.update(sim_dt, events)
            if forced and transition is None:
                transition = go(forced)

        if transition is not None:
            if transition.wants_swap():
                kind = transition.target[0]
                if kind == "map":
                    scene = None
                elif kind == "station":
                    scene = StationView(world, sim, transition.target[1])
                else:
                    scene = RideView(world, sim, transition.target[1])
                transition.swapped = True
                if isinstance(transition, StepTransition):
                    transition.scene = scene
            if transition.update(dt):
                transition = None

        if scene is not None:
            scene.draw(screen, paused, speed)
        else:
            map_scene.draw(screen, paused, speed)
        if transition is not None:
            transition.draw(screen)
        pygame.display.flip()

    pygame.quit()
