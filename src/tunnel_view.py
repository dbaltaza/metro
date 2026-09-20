"""Looking down the tunnel from the cab of a train that has stopped.

The control room lists what has broken down; this is what the driver can see
while it is. The tunnel is drawn as arches receding to a vanishing point,
each one a little darker than the one in front of it, with the rails running
away between them and a signal up ahead holding the train where it is.

When the fault clears the signal goes green and the arches start to flow past,
and after a moment you are handed back to the control room.
"""

import math
import random

import pygame

from src import sprites
from src.audio import AUDIO
from src.metro import Metro
from src.route import (
    BUTTON, BUTTON_HOVER, HIGHLIGHT, MUTED, PANEL_BG, PANEL_EDGE, TEXT, WINDOW_H,
    WINDOW_W, World, draw_day_clock,
)
from src.sim import Simulation
from src.sprites import shade
from src.station_layout import BOARD, HEADER_BG, HEADER_H, IH, IW, VIEW

# The bore, in world pixels at the mouth of the tunnel, and how far apart the
# arches are in depth. Anything past the last one is the dark at the end.
ARCHES = 26
NEAR_W, NEAR_H = 380.0, 176.0
STEP = 1.0
HORIZON = 0.44          # where the vanishing point sits down the screen
# The track and the cable runs are laid out from the vanishing point rather
# than off the arches, so they keep their perspective whatever the bore does.
FLOOR = 132.0
RAIL_HALF = 62.0
CABLE_X = 300.0
CABLE_Y = 104.0

WALL = (104, 95, 82)
WALL_WET = (118, 107, 92)
CABLE = (44, 40, 38)
RAIL = (150, 152, 160)
SLEEPER = (56, 50, 46)
BALLAST = (40, 38, 40)
LAMP = (255, 228, 150)
SIGNAL_RED = (236, 64, 58)
SIGNAL_GREEN = (86, 226, 120)

CAB = (46, 48, 56)
CAB_HI = (78, 82, 92)
CAB_DARK = (30, 32, 38)
DASH = (34, 36, 42)
GLASS = (150, 190, 210)

SIGNAL_DEPTH = 9.0       # how far ahead the signal that is holding us sits
ROLL_AWAY = 2.6          # seconds of pulling away before the room takes over
SHAKE = 0.35             # how much the idling train trembles, in world pixels
FLASH = 0.5              # how long the wrong control stays lit up red

# The driver's desk. Each control answers for two of the faults, and the
# order never changes, so you learn where they are rather than reading them
# every time.
CONTROLS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("RESET TRACTION", ("traction cut-out", "power supply dip")),
    ("DOOR OVERRIDE", ("door interlock", "passenger alarm")),
    ("RELEASE BRAKES", ("brake fault", "wheel slide")),
    ("CALL SIGNALLER", ("signal at danger", "points failure")),
)


def _lit(color, brightness: float):
    return tuple(max(0, min(255, round(c * brightness))) for c in color)


class TunnelView:
    """A scene like the others: it takes events, updates, and draws itself."""

    def __init__(self, world: World, sim: Simulation, metro: Metro):
        self.world = world
        self.sim = sim
        self.metro = metro
        self.line = world.map.line_named(metro.line)
        self.time = 0.0
        self.speed = 1.0
        self.mouse = (0, 0)
        self.travelled = 0.0            # how far the arches have flowed past
        self.moving_for = 0.0
        self.held_for = max(metro.stalled, 0.1)   # the longest it has to wait
        self.rng = random.Random(metro.id * 7717)

        self.title = pygame.font.SysFont("helvetica,arial", 26, bold=True)
        self.head = pygame.font.SysFont("helvetica,arial", 15, bold=True)
        self.body = pygame.font.SysFont("helvetica,arial", 14)
        self.small = pygame.font.SysFont("helvetica,arial", 12)
        self.big = pygame.font.SysFont("helvetica,arial", 22, bold=True)

        self.back_rect = pygame.Rect(18, 19, 132, 36)
        self.control_rects: list[tuple[pygame.Rect, str, tuple[str, ...]]] = []
        self.wrong: tuple[str, float] | None = None    # which control, and when
        # 24-bit on purpose, like the other scenes: a surface with an alpha
        # channel picks up stray alpha from sprite blits and turns to blocks.
        self.world_surface = pygame.Surface((IW, IH), 0, 24)
        self.aperture = pygame.Rect(46, 8, IW - 92, IH - 74)

    # -- state ---------------------------------------------------------------------

    def stopped(self) -> bool:
        """Still held by the fault. Once it is cleared the train is pulling
        away, even though it has a second of standing still left in it."""
        return self.metro.stalled > 0 and bool(self.metro.fault)

    def _vanishing(self) -> tuple[float, float]:
        """Where the tunnel runs to. It trembles while the train idles."""
        shake = 0.0 if not self.stopped() else SHAKE * math.sin(self.time * 11.0)
        return IW / 2, IH * HORIZON + shake

    def _signal_ahead(self) -> float:
        return SIGNAL_DEPTH - self.travelled

    # -- input ---------------------------------------------------------------------

    def handle(self, event: pygame.event.Event) -> tuple | None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_c):
            return ("control",)
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                return ("control",)
            for rect, label, faults in self.control_rects:
                if rect.collidepoint(event.pos):
                    self._press(label, faults)
                    return None
        return None

    def _press(self, label: str, faults: tuple[str, ...]) -> None:
        """A control on the desk. The right one for what is wrong with the
        train clears it; the wrong one costs a few seconds."""
        if not self.stopped():
            return
        if self.metro.fault in faults:
            self.sim.release(self.metro)
            self.wrong = None
            AUDIO.play("chime", 0.9)
        else:
            self.sim.fumble(self.metro)
            self.wrong = (label, self.time)
            AUDIO.play("buzz", 0.8)

    def update(self, dt: float, events) -> tuple | None:
        self.time += dt
        if self.metro not in self.sim.metros:
            return ("control",)
        if self.stopped():
            self.held_for = max(self.held_for, self.metro.stalled)
            return None
        # Under way again: let the tunnel run past for a moment, then hand
        # the desk back, since there is nothing more to watch down here.
        if self.moving_for == 0.0:
            AUDIO.play("depart", 0.9)
        self.moving_for += dt
        self.travelled += dt * 3.2
        return ("control",) if self.moving_for > ROLL_AWAY else None

    def ambience(self) -> dict[str, float]:
        return {"roll": 0.9 if not self.stopped() else 0.14}

    # -- drawing ---------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, paused: bool, speed: float = 1.0) -> None:
        self.speed = speed
        s = self.world_surface
        self._draw_tunnel(s)
        self._draw_cab(s)
        screen.blit(pygame.transform.scale(s, VIEW.size), VIEW.topleft)
        self._draw_header(screen)
        self._draw_board(screen)

    def _glow(self, depth: float) -> float:
        """How much of the headlight lands on something that far down the
        tunnel. A headlight throws a pool a little way ahead: the walls right
        beside the cab are outside the beam, and nothing far is in it either,
        so the lit part is a ring in the middle distance."""
        entering = min(max((depth - 0.8) / 1.7, 0.0), 1.0)
        leaving = 1.0 / (1.0 + max(depth - 3.0, 0.0) * 1.1)
        return 0.04 + 0.96 * entering * leaving

    def _arch(self, s, cx: float, cy: float, depth: float, color) -> None:
        """One arch, filled. They are painted biggest first, so each one
        covers the stretch of wall between itself and the one in front."""
        half_w = NEAR_W / depth
        half_h = NEAR_H / depth
        rect = pygame.Rect(round(cx - half_w), round(cy - half_h), round(half_w * 2), round(half_h * 2))
        radius = max(1, round(half_w * 0.9))
        pygame.draw.rect(s, color, rect, border_top_left_radius=radius, border_top_right_radius=radius)

    def _draw_tunnel(self, s: pygame.Surface) -> None:
        cx, cy = self._vanishing()
        s.fill((7, 7, 9))
        clip = s.get_clip()
        s.set_clip(self.aperture)
        flow = self.travelled % STEP
        depths = [d for d in (1.0 + (k - flow) * STEP for k in range(ARCHES)) if d >= 0.55]
        for i, depth in enumerate(depths):
            tone = WALL_WET if i % 4 == 1 else WALL
            self._arch(s, cx, cy, depth, _lit(tone, self._glow(depth)))
        self._arch(s, cx, cy, depths[-1] + STEP, (4, 4, 6))
        self._draw_track(s, cx, cy, depths)
        self._draw_walls(s, cx, cy, depths)
        self._draw_signal(s, cx, cy)
        self._draw_headlight(s, cx, cy)
        s.set_clip(clip)

    def _draw_track(self, s, cx: float, cy: float, depths) -> None:
        """Ballast, sleepers and two rails, a segment at a time so each one
        is lit by how far away it is."""
        for near, far in zip(depths, depths[1:]):
            bright = self._glow(far)
            y0, y1 = cy + FLOOR / near, cy + FLOOR / far
            x0, x1 = RAIL_HALF / near, RAIL_HALF / far
            pygame.draw.polygon(s, _lit(BALLAST, bright), [
                (cx - x0 * 2.4, y0), (cx + x0 * 2.4, y0), (cx + x1 * 2.4, y1), (cx - x1 * 2.4, y1)])
            pygame.draw.line(s, _lit(SLEEPER, bright), (cx - x1 * 1.6, y1), (cx + x1 * 1.6, y1),
                             max(1, round(5 / far)))
            for side in (-1, 1):
                pygame.draw.line(s, _lit(RAIL, bright * 0.5), (cx + side * x0, y0), (cx + side * x1, y1),
                                 max(1, round(4 / far)))
                pygame.draw.line(s, _lit(RAIL, bright), (cx + side * x0, y0 - 1), (cx + side * x1, y1 - 1),
                                 max(1, round(2 / far)))

    def _draw_walls(self, s, cx: float, cy: float, depths) -> None:
        """The cable run down each wall, and a lamp every few arches."""
        for near, far in zip(depths, depths[1:]):
            # The nearest stretch runs off past the cab and, drawn, only puts
            # a hard diagonal across the corners of the windscreen.
            if CABLE_X / near > self.aperture.width * 0.62:
                continue
            bright = self._glow(far)
            for side in (-1, 1):
                for height, tone in ((CABLE_Y, CABLE), (CABLE_Y * 0.74, shade(CABLE, 14))):
                    pygame.draw.line(s, _lit(tone, bright),
                                     (cx + side * CABLE_X / near, cy - height / near),
                                     (cx + side * CABLE_X / far, cy - height / far),
                                     max(1, round(4 / far)))
        for i, depth in enumerate(depths):
            if i % 4 or depth > 11:
                continue
            bright = self._glow(depth)
            x = round(cx - (CABLE_X * 0.92) / depth)
            y = round(cy - (CABLE_Y * 1.25) / depth)
            size = max(1, round(9 / depth))
            glow = pygame.Surface((size * 10, size * 8), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*LAMP, round(90 * bright)), glow.get_rect())
            s.blit(glow, (x - size * 5, y - size * 4))
            pygame.draw.rect(s, _lit(LAMP, min(bright * 1.6, 1.0)), (x, y, size, max(1, size // 2)))

    def _draw_headlight(self, s, cx: float, cy: float) -> None:
        """The pool the train's own light throws down the track in front."""
        pool = pygame.Surface((int(NEAR_W * 0.8), int(NEAR_H * 0.5)), pygame.SRCALPHA)
        for i in range(4):
            pygame.draw.ellipse(pool, (255, 236, 196, max(13 - i * 3, 3)),
                                pool.get_rect().inflate(-i * 54, -i * 18))
        s.blit(pool, (cx - pool.get_width() / 2, cy + FLOOR / 3.4 - pool.get_height() / 2))

    def _draw_signal(self, s, cx: float, cy: float) -> None:
        """The signal holding the train, on the right-hand wall."""
        depth = self._signal_ahead()
        if depth < 0.6:
            return
        color = SIGNAL_RED if self.stopped() else SIGNAL_GREEN
        x = cx + (CABLE_X * 0.8) / depth
        y = cy + (FLOOR * 0.1) / depth
        size = max(2, round(22 / depth))
        pygame.draw.rect(s, (14, 14, 16), (round(x - size / 2), round(y - size), size, round(size * 2.2)))
        glow = pygame.Surface((size * 8, size * 8), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*color, 120), glow.get_rect())
        pygame.draw.ellipse(glow, (*color, 90), glow.get_rect().inflate(-size * 3, -size * 3))
        s.blit(glow, (round(x - size * 4), round(y - size * 4)))
        pygame.draw.circle(s, color, (round(x), round(y)), max(1, round(size * 0.45)))
        pygame.draw.line(s, (22, 22, 24), (round(x), round(y + size)),
                         (round(x), round(y + size * 2.6)), max(1, round(size / 4)))

    def _draw_cab(self, s: pygame.Surface) -> None:
        """The windscreen you are looking through, and the desk under it."""
        window = self.aperture
        frame = pygame.Surface((IW, IH), pygame.SRCALPHA)
        frame.fill(CAB)
        pygame.draw.rect(frame, (0, 0, 0, 0), window, border_radius=18)
        s.blit(frame, (0, 0))
        pygame.draw.rect(s, CAB_HI, window.inflate(6, 6), 3, border_radius=20)
        pygame.draw.rect(s, CAB_DARK, window.inflate(12, 12), 2, border_radius=22)
        # A wipe of reflection across the glass, so it reads as glass.
        sheen = pygame.Surface(window.size, pygame.SRCALPHA)
        pygame.draw.polygon(sheen, (*GLASS, 8), [(0, window.height), (window.width * 0.36, 0),
                                                 (window.width * 0.46, 0), (window.width * 0.1, window.height)])
        s.blit(sheen, window.topleft)

        desk = pygame.Rect(0, window.bottom + 12, IW, IH - window.bottom - 12)
        pygame.draw.rect(s, DASH, desk)
        pygame.draw.line(s, CAB_HI, desk.topleft, desk.topright)
        pygame.draw.line(s, CAB_DARK, (desk.x, desk.y + 1), (desk.right, desk.y + 1))

        # A speedometer, reading nothing at all until it pulls away.
        dial_c = (54, desk.y + 26)
        pygame.draw.circle(s, (20, 22, 26), dial_c, 21)
        pygame.draw.circle(s, CAB_HI, dial_c, 21, 2)
        for tick in range(7):
            angle = math.pi * (0.85 + tick * 0.22)
            pygame.draw.line(s, (86, 90, 100),
                             (dial_c[0] + math.cos(angle) * 14, dial_c[1] + math.sin(angle) * 14),
                             (dial_c[0] + math.cos(angle) * 18, dial_c[1] + math.sin(angle) * 18))
        reading = 0.0 if self.stopped() else min(self.moving_for / ROLL_AWAY, 1.0)
        needle = math.pi * (0.85 + reading * 1.3)
        pygame.draw.line(s, SIGNAL_RED if self.stopped() else (236, 236, 240), dial_c,
                         (dial_c[0] + math.cos(needle) * 16, dial_c[1] + math.sin(needle) * 16), 2)

        # The brake handle, over to the left of the desk, pulled right back.
        lever = pygame.Rect(104, desk.y + 10, 10, 34)
        pygame.draw.rect(s, (26, 28, 32), lever.inflate(10, 6), border_radius=6)
        pygame.draw.rect(s, shade(CAB_HI, -10), lever, border_radius=4)
        pygame.draw.circle(s, SIGNAL_RED if self.stopped() else (120, 126, 138),
                           (lever.centerx, lever.y + (4 if self.stopped() else 28)), 6)

        # A row of switches, and the badge of the line it works.
        for i in range(6):
            switch = pygame.Rect(150 + i * 17, desk.y + 14, 11, 22)
            pygame.draw.rect(s, (24, 26, 30), switch, border_radius=3)
            pygame.draw.rect(s, (96, 102, 112), (switch.x + 2, switch.y + (3 if i % 2 else 12), 7, 7),
                             border_radius=2)
        pygame.draw.rect(s, self.line.color, (IW - 168, desk.y + 14, 44, 8), border_radius=3)
        pygame.draw.rect(s, (18, 20, 24), (IW - 168, desk.y + 26, 44, 12), border_radius=3)

        # The signal repeater: the whole of the driver's problem in one lamp.
        lamp = SIGNAL_RED if self.stopped() else SIGNAL_GREEN
        centre = (IW - 74, desk.y + 26)
        glow = pygame.Surface((46, 46), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*lamp, 70), glow.get_rect())
        s.blit(glow, (centre[0] - 23, centre[1] - 23))
        pygame.draw.circle(s, (16, 16, 18), centre, 12)
        pygame.draw.circle(s, lamp, centre, 8)
        pygame.draw.circle(s, _lit(lamp, 1.4), centre, 4)

    def _draw_header(self, screen) -> None:
        pygame.draw.rect(screen, HEADER_BG, (0, 0, WINDOW_W, HEADER_H))
        pygame.draw.line(screen, PANEL_EDGE, (0, HEADER_H), (WINDOW_W, HEADER_H), 2)
        hovering = self.back_rect.collidepoint(self.mouse)
        pygame.draw.rect(screen, BUTTON_HOVER if hovering else BUTTON, self.back_rect, border_radius=8)
        pygame.draw.polygon(screen, TEXT, [(34, 37), (44, 29), (44, 45)])
        screen.blit(sprites.text(self.head, "CONTROL", TEXT), (52, 28))
        title = sprites.text(self.title, f"Train #{self.metro.id}", TEXT)
        screen.blit(title, (176, 22))
        pygame.draw.circle(screen, self.line.color, (162, 37), 7)
        draw_day_clock(screen, self.head, self.small, self.sim.clock, (WINDOW_W // 2 + 160, 37))

    def _draw_board(self, screen) -> None:
        pygame.draw.rect(screen, PANEL_BG, BOARD)
        pygame.draw.line(screen, PANEL_EDGE, BOARD.topleft, BOARD.topright, 2)
        x, y = 24, BOARD.y + 18
        if self.stopped():
            headline, color = "STOPPED IN THE TUNNEL", SIGNAL_RED
        else:
            headline, color = "SIGNAL CLEAR, MOVING AGAIN", SIGNAL_GREEN
        screen.blit(sprites.text(self.big, headline, color), (x, y))
        where = f"between {self.metro.current_station} and {self.metro.destination}"
        screen.blit(sprites.text(self.body, where, TEXT), (x, y + 34))
        aboard = f"{len(self.metro.riders)} aboard, waiting with you" if self.stopped() \
            else f"{len(self.metro.riders)} aboard, on the move"
        screen.blit(sprites.text(self.body, aboard, MUTED), (x, y + 56))

        self._draw_controls(screen)
        bar = pygame.Rect(x, y + 88, 420, 10)
        pygame.draw.rect(screen, (38, 40, 48), bar, border_radius=5)
        left = self.metro.stalled / self.held_for if self.held_for and self.stopped() else 0.0
        if left > 0:
            pygame.draw.rect(screen, SIGNAL_RED, (bar.x, bar.y, round(bar.width * min(left, 1.0)), bar.height),
                             border_radius=5)
            screen.blit(sprites.text(self.small, f"{math.ceil(self.metro.stalled)}s until the signal clears",
                                     MUTED), (bar.x, bar.y + 16))
        else:
            pygame.draw.rect(screen, SIGNAL_GREEN, bar, border_radius=5)
            screen.blit(sprites.text(self.small, "back to the control room in a moment", MUTED),
                        (bar.x, bar.y + 16))

        hint = sprites.text(self.small, "Esc or CONTROL returns to the desk.", MUTED)
        screen.blit(hint, (WINDOW_W - 24 - hint.get_width(), WINDOW_H - 30))

    def _draw_controls(self, screen) -> None:
        """The four controls, and what is wrong with the train above them."""
        self.control_rects = []
        top = BOARD.y + 28
        left = WINDOW_W - 24 - (len(CONTROLS) * 196 - 16)
        if self.stopped():
            fault = sprites.text(self.head, f"FAULT: {self.metro.fault.upper()}", HIGHLIGHT)
            screen.blit(fault, (left, top - 2))
            told = "the wrong control, try another" if self.wrong and self.time - self.wrong[1] < FLASH \
                else "clear it from the driver's desk"
            screen.blit(sprites.text(self.small, told, MUTED), (left, top + 22))
        else:
            screen.blit(sprites.text(self.head, "FAULT CLEARED", SIGNAL_GREEN), (left, top - 2))
        for i, (label, faults) in enumerate(CONTROLS):
            rect = pygame.Rect(left + i * 196, top + 50, 180, 46)
            lit = self.wrong is not None and self.wrong[0] == label and self.time - self.wrong[1] < FLASH
            if not self.stopped():
                face, ink = (30, 34, 40), MUTED
            elif lit:
                face, ink = (86, 34, 34), (255, 220, 214)
            elif rect.collidepoint(self.mouse):
                face, ink = BUTTON_HOVER, HIGHLIGHT
            else:
                face, ink = BUTTON, TEXT
            pygame.draw.rect(screen, face, rect, border_radius=8)
            pygame.draw.rect(screen, CAB_HI if self.stopped() else PANEL_EDGE, rect, 1, border_radius=8)
            text = sprites.text(self.head, label, ink)
            screen.blit(text, text.get_rect(center=rect.center))
            if self.stopped():
                self.control_rects.append((rect, label, faults))
