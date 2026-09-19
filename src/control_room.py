"""The control room: the whole network on one desk.

Which lines are struggling, which platforms are filling up, what the day is
about to do, and what has broken down. Everything here is read off the
simulation every frame, and the only things you can do are the things a
controller could do: put a train into service, take one out, look down the
tunnel at a train that has stopped, or go and stand on a platform yourself.
"""

import math

import pygame

from src import sprites
from src.audio import AUDIO
from src.daytime import DEMAND, clock_text, demand_at, hour_of, next_peak, period_at
from src.metro import Metro
from src.network import Line
from src.route import (
    BUTTON, BUTTON_HOVER, HIGHLIGHT, LOAD_COLORS, MUTED, PANEL_BG, PANEL_EDGE, TEXT,
    WINDOW_H, WINDOW_W, World, draw_day_clock, lines_serving,
)
from src.sim import Simulation
from src.sprites import OUTLINE, shade
from src.station_layout import HEADER_BG, HEADER_H

SCREEN = (16, 20, 24)          # the glass of a desk monitor
SCREEN_EDGE = (44, 54, 62)
LIVE = (126, 226, 158)         # the colour live figures are shown in
GRID = (26, 32, 38)
BAR_BED = (32, 38, 44)
STALL = (255, 110, 96)

GUTTER = 22
COLUMN = (WINDOW_W - GUTTER * 3) // 2

# How many people waiting is bad enough to show red. Bar lengths are
# relative to the worst on the desk, so the busiest is always full and the
# rest can be read against it; the colour is what says how bad it really is.
LINE_HEAVY = 700
STATION_HEAVY = 260
STATIONS_LISTED = 11


def heat(fraction: float):
    """Green, amber, red, by how close to full something is."""
    if fraction < 0.4:
        return LOAD_COLORS[0]
    return LOAD_COLORS[1] if fraction < 0.75 else LOAD_COLORS[2]


class Desk:
    """One panel on the desk: a titled screen with a frame round it."""

    def __init__(self, title: str, rect: pygame.Rect):
        self.title = title
        self.rect = rect
        self.body = pygame.Rect(rect.x + 14, rect.y + 40, rect.width - 28, rect.height - 54)

    def draw(self, screen, font, small) -> None:
        pygame.draw.rect(screen, SCREEN, self.rect, border_radius=10)
        pygame.draw.rect(screen, SCREEN_EDGE, self.rect, 1, border_radius=10)
        for y in range(self.rect.y + 4, self.rect.bottom - 2, 4):
            pygame.draw.line(screen, GRID, (self.rect.x + 2, y), (self.rect.right - 3, y))
        screen.blit(sprites.text(font, self.title, TEXT), (self.rect.x + 16, self.rect.y + 14))
        pygame.draw.line(screen, SCREEN_EDGE, (self.rect.x + 14, self.rect.y + 36),
                         (self.rect.right - 15, self.rect.y + 36))


class ControlRoom:
    """The network as a controller sees it. A scene like any other: it takes
    events, is updated, and draws itself."""

    def __init__(self, world: World, sim: Simulation):
        self.world = world
        self.sim = sim
        self.mouse = (0, 0)
        self.speed = 1.0
        self.title = pygame.font.SysFont("helvetica,arial", 26, bold=True)
        self.head = pygame.font.SysFont("helvetica,arial", 15, bold=True)
        self.body = pygame.font.SysFont("helvetica,arial", 14)
        self.small = pygame.font.SysFont("helvetica,arial", 12)
        self.tiny = pygame.font.SysFont("helvetica,arial", 11, bold=True)

        self.back_rect = pygame.Rect(18, 19, 92, 36)
        top = HEADER_H + GUTTER
        self.lines_desk = Desk("LINES", pygame.Rect(GUTTER, top, COLUMN, 250))
        self.stations_desk = Desk("BUSIEST PLATFORMS", pygame.Rect(
            GUTTER, self.lines_desk.rect.bottom + GUTTER, COLUMN,
            WINDOW_H - self.lines_desk.rect.bottom - GUTTER * 2))
        right = GUTTER * 2 + COLUMN
        self.day_desk = Desk("THE DAY", pygame.Rect(right, top, COLUMN, 250))
        self.incidents_desk = Desk("INCIDENTS", pygame.Rect(
            right, self.day_desk.rect.bottom + GUTTER, COLUMN,
            WINDOW_H - self.day_desk.rect.bottom - GUTTER * 2))

        # Filled in as they are drawn, so clicking uses what is on screen.
        self.fleet_buttons: list[tuple[pygame.Rect, str, str]] = []
        self.station_rows: list[tuple[pygame.Rect, str]] = []
        self.look_buttons: list[tuple[pygame.Rect, Metro]] = []

    # -- what the desk is looking at ---------------------------------------------

    def _line_load(self) -> list[tuple[Line, int, int, int]]:
        """Per line: people waiting for it, people on it, and trains running.
        Sorted by how many are waiting, worst first."""
        waiting = {line.name: 0 for line in self.world.map.lines}
        for station in self.world.map.stations.values():
            for passenger in station.waiting:
                if passenger.next_line in waiting:
                    waiting[passenger.next_line] += 1
        rows = []
        for line in self.world.map.lines:
            trains = [m for m in self.sim.metros if m.line == line.name]
            riders = sum(len(m.riders) for m in trains)
            rows.append((line, waiting[line.name], riders, len(trains)))
        return sorted(rows, key=lambda row: -row[1])

    def _busiest(self):
        stations = sorted(self.world.map.stations.values(), key=lambda s: -len(s.waiting))
        return stations[:STATIONS_LISTED]

    def _stalled(self) -> list[Metro]:
        return sorted((m for m in self.sim.metros if m.stalled > 0), key=lambda m: -m.stalled)

    # -- input ---------------------------------------------------------------------

    def handle(self, event: pygame.event.Event) -> str | tuple | None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_c):
            return "back"
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                return "back"
            for rect, action, line in self.fleet_buttons:
                if rect.collidepoint(event.pos):
                    AUDIO.play("click", 0.6)
                    if action == "add":
                        self.sim.add_train(line)
                    else:
                        self.sim.remove_train(line)
                    return None
            for rect, metro in self.look_buttons:
                if rect.collidepoint(event.pos):
                    AUDIO.play("click", 0.6)
                    return ("tunnel", metro)
            for rect, name in self.station_rows:
                if rect.collidepoint(event.pos):
                    AUDIO.play("click", 0.6)
                    return ("station", name)
        return None

    def update(self, dt: float, events) -> None:
        return None

    def ambience(self) -> dict[str, float]:
        """A room away from the trains, with the network humming quietly."""
        return {"murmur": 0.18}

    # -- drawing ---------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, paused: bool, speed: float = 1.0) -> None:
        self.speed = speed
        screen.fill(PANEL_BG)
        self.fleet_buttons, self.station_rows, self.look_buttons = [], [], []
        self._draw_lines(screen)
        self._draw_stations(screen)
        self._draw_day(screen)
        self._draw_incidents(screen)
        self._draw_header(screen, paused)

    def _draw_header(self, screen, paused: bool) -> None:
        pygame.draw.rect(screen, HEADER_BG, (0, 0, WINDOW_W, HEADER_H))
        pygame.draw.line(screen, PANEL_EDGE, (0, HEADER_H), (WINDOW_W, HEADER_H), 2)
        hovering = self.back_rect.collidepoint(self.mouse)
        pygame.draw.rect(screen, BUTTON_HOVER if hovering else BUTTON, self.back_rect, border_radius=8)
        pygame.draw.polygon(screen, TEXT, [(34, 37), (44, 29), (44, 45)])
        screen.blit(sprites.text(self.head, "MAP", TEXT), (52, 28))
        screen.blit(sprites.text(self.title, "Control room", TEXT), (136, 22))
        draw_day_clock(screen, self.head, self.small, self.sim.clock, (WINDOW_W // 2 + 120, 37))
        note = "PAUSED" if paused else (f"{len(self.sim.metros)} trains in service"
                                        f"    {self.sim.released} faults cleared")
        text = sprites.text(self.small, note, HIGHLIGHT if paused else MUTED)
        screen.blit(text, (WINDOW_W - 24 - text.get_width(), 30))

    def _bar(self, screen, rect: pygame.Rect, length: float, badness: float) -> None:
        """How long, against the worst thing on the desk, and how bad, against
        the count that counts as heavy."""
        pygame.draw.rect(screen, BAR_BED, rect, border_radius=3)
        filled = max(int(rect.width * min(length, 1.0)), 2 if length > 0 else 0)
        if filled:
            pygame.draw.rect(screen, heat(badness), (rect.x, rect.y, filled, rect.height), border_radius=3)

    def _button(self, screen, x: int, y: int, label: str, action: str, line: str) -> pygame.Rect:
        rect = pygame.Rect(x, y, 26, 24)
        hovering = rect.collidepoint(self.mouse)
        pygame.draw.rect(screen, BUTTON_HOVER if hovering else BUTTON, rect, border_radius=6)
        text = sprites.text(self.head, label, TEXT)
        screen.blit(text, text.get_rect(center=rect.center))
        self.fleet_buttons.append((rect, action, line))
        return rect

    def _draw_lines(self, screen) -> None:
        desk = self.lines_desk
        desk.draw(screen, self.head, self.small)
        body = desk.body
        rows = self._line_load()
        step = body.height // max(len(rows), 1)
        worst = max((row[1] for row in rows), default=0)
        for i, (line, waiting, riders, trains) in enumerate(rows):
            y = body.y + i * step
            pygame.draw.circle(screen, line.color, (body.x + 8, y + 12), 6)
            screen.blit(sprites.text(self.body, line.name, TEXT), (body.x + 22, y + 4))
            self._bar(screen, pygame.Rect(body.x + 22, y + 26, body.width - 130, 7),
                      waiting / worst if worst else 0.0, waiting / LINE_HEAVY)
            figures = f"{waiting} waiting   {riders} aboard"
            screen.blit(sprites.text(self.small, figures, LIVE), (body.x + 22, y + 36))
            count = sprites.text(self.head, str(trains), TEXT)
            screen.blit(count, (body.right - 96, y + 6))
            screen.blit(sprites.text(self.small, "trains", MUTED), (body.right - 96, y + 26))
            self._button(screen, body.right - 58, y + 4, "-", "remove", line.name)
            self._button(screen, body.right - 28, y + 4, "+", "add", line.name)

    def _draw_stations(self, screen) -> None:
        desk = self.stations_desk
        desk.draw(screen, self.head, self.small)
        body = desk.body
        stations = self._busiest()
        step = min(body.height // max(len(stations), 1), 34)
        worst = max((len(s.waiting) for s in stations), default=0)
        for i, station in enumerate(stations):
            y = body.y + i * step
            row = pygame.Rect(body.x - 6, y - 2, body.width + 12, step - 2)
            if row.collidepoint(self.mouse):
                pygame.draw.rect(screen, (28, 34, 40), row, border_radius=6)
            self.station_rows.append((row, station.name))
            for k, line in enumerate(lines_serving(self.world.map, station.name)):
                pygame.draw.rect(screen, line.color, (body.x + k * 6, y + 4, 4, 12))
            screen.blit(sprites.text(self.body, station.name, TEXT), (body.x + 28, y))
            count = len(station.waiting)
            number = sprites.text(self.small, str(count), LIVE)
            screen.blit(number, (body.right - number.get_width(), y + 2))
            self._bar(screen, pygame.Rect(body.x + 28, y + 19, body.width - 60, 5),
                      count / worst if worst else 0.0, count / STATION_HEAVY)
        hint = sprites.text(self.small, "click a platform to go and stand on it", MUTED)
        screen.blit(hint, (body.x, desk.rect.bottom - 24))

    def _draw_day(self, screen) -> None:
        desk = self.day_desk
        desk.draw(screen, self.head, self.small)
        body = desk.body
        hour = hour_of(self.sim.clock)
        graph = pygame.Rect(body.x, body.y + 34, body.width, body.height - 62)
        ceiling = max(v for _, v in DEMAND)

        def point(h: float) -> tuple[int, int]:
            return (round(graph.x + graph.width * h / 24.0),
                    round(graph.bottom - graph.height * demand_at(h) / ceiling))

        curve = [point(h / 4) for h in range(97)]
        pygame.draw.polygon(screen, (24, 36, 44), curve + [(graph.right, graph.bottom), (graph.x, graph.bottom)])
        pygame.draw.lines(screen, LIVE, False, curve, 2)
        for h in range(0, 25, 6):
            x = graph.x + graph.width * h / 24.0
            pygame.draw.line(screen, GRID, (x, graph.y), (x, graph.bottom))
            label = sprites.text(self.small, f"{h % 24:02d}", MUTED)
            screen.blit(label, (x - label.get_width() // 2, graph.bottom + 6))
        # Where we are now, and what it is called.
        x, _ = point(hour)
        pygame.draw.line(screen, HIGHLIGHT, (x, graph.y - 6), (x, graph.bottom), 1)
        pygame.draw.circle(screen, HIGHLIGHT, point(hour), 4)
        screen.blit(sprites.text(self.head, f"{clock_text(hour)}  {period_at(hour)}", TEXT), (body.x, body.y))
        away, peak = next_peak(hour)
        if away < 0.05:
            ahead = "the peak is now"
        else:
            minutes = round(away * 60)
            ahead = f"{clock_text(peak)} peak in {minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 \
                else f"{clock_text(peak)} peak in {minutes}m"
        text = sprites.text(self.small, ahead, HIGHLIGHT if away < 0.5 else MUTED)
        screen.blit(text, (body.right - text.get_width(), body.y + 4))

    def _draw_incidents(self, screen) -> None:
        desk = self.incidents_desk
        desk.draw(screen, self.head, self.small)
        body = desk.body
        stalled = self._stalled()
        if not stalled:
            screen.blit(sprites.text(self.body, "Nothing broken down.", MUTED), (body.x, body.y))
            screen.blit(sprites.text(self.small, "Trains that stop between stations show up here.",
                                     shade(MUTED, -30)), (body.x, body.y + 28))
            screen.blit(sprites.text(self.small, "Attend to one and you can clear the fault yourself;",
                                     shade(MUTED, -30)), (body.x, body.y + 46))
            screen.blit(sprites.text(self.small, "left alone they sit there for minutes.",
                                     shade(MUTED, -30)), (body.x, body.y + 64))
        for i, metro in enumerate(stalled[:6]):
            y = body.y + i * 58
            line = self.world.map.line_named(metro.line)
            pygame.draw.rect(screen, OUTLINE, (body.x - 2, y - 2, body.width + 4, 50), border_radius=6)
            pygame.draw.rect(screen, (30, 22, 24), (body.x - 2, y - 2, body.width + 4, 50), border_radius=6)
            pygame.draw.rect(screen, line.color, (body.x + 2, y + 2, 4, 42))
            headline = f"Train #{metro.id}: {metro.fault}" if metro.fault else f"Train #{metro.id} stopped"
            screen.blit(sprites.text(self.head, headline, STALL), (body.x + 16, y + 2))
            where = f"between {metro.current_station} and {metro.destination}"
            screen.blit(sprites.text(self.small, where, MUTED), (body.x + 16, y + 22))
            # Rounded up: a fault with half a second left is not "0s".
            held = sprites.text(self.small, f"{math.ceil(metro.stalled)}s   {len(metro.riders)} aboard", LIVE)
            screen.blit(held, (body.x + 16, y + 36))
            look = pygame.Rect(body.right - 96, y + 10, 90, 28)
            hovering = look.collidepoint(self.mouse)
            pygame.draw.rect(screen, BUTTON_HOVER if hovering else BUTTON, look, border_radius=6)
            label = sprites.text(self.head, "ATTEND", HIGHLIGHT if hovering else TEXT)
            screen.blit(label, label.get_rect(center=look.center))
            self.look_buttons.append((look, metro))
