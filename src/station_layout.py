"""Station scene layout: screen regions, palette, timing constants, and the
static backdrop (walls, floors, pits, furniture) drawn once per station."""

import random

import pygame

from src.route import WINDOW_H, WINDOW_W
from src.sprites import OUTLINE, shade

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
# The pits are deep enough for a car that stands taller than the people on
# the platform, the way a real one does.
PLATFORM_1 = pygame.Rect(0, 44, IW, 49)
EDGE_1 = pygame.Rect(0, 93, IW, 6)
PIT_A = pygame.Rect(0, 99, IW, 38)
KERB = pygame.Rect(0, 137, IW, 6)
PIT_B = pygame.Rect(0, 143, IW, 38)
LIP_2 = pygame.Rect(0, 181, IW, 4)
PLATFORM_2 = pygame.Rect(0, 185, IW, 54)
FRONT_CAP = pygame.Rect(0, 239, IW, IH - 239)

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
CAR_LEN = 144
CAR_GAP = 6
ROOF_H = 16
SIDE_H = 22
TRAIN_LEN = CARS * CAR_LEN + (CARS - 1) * CAR_GAP
DOOR_W = 14
DOOR_FRACTIONS = [0.24, 0.76]

WANDER_SPEED = 13.0
WANDER_RANGE = (44.0, 9.0)
CROWD_LIMIT = 44         # people drawn standing on each platform at once
ENTRY_FADE = 0.45        # seconds to come up out of the stairwell
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


def exits(platform: pygame.Rect) -> list[pygame.Rect]:
    y = platform.y + 6 if platform is PLATFORM_1 else platform.bottom - 28
    return [pygame.Rect(6, y, 26, 22), pygame.Rect(IW - 32, y, 26, 22)]


def render_backdrop(station_name: str, line_color, network_lines) -> tuple[pygame.Surface, pygame.Rect, dict[int, pygame.Rect]]:
    s = pygame.Surface((IW, IH), 0, 24)
    rng = random.Random(hash(station_name) & 0xFFFF)

    # Back wall: a light cap on top, then the face with a darker band.
    pygame.draw.rect(s, WALL_CAP_C, WALL_CAP)
    pygame.draw.line(s, shade(WALL_CAP_C, 30), (0, 0), (IW, 0))
    pygame.draw.rect(s, WALL_C, WALL_FACE)
    pygame.draw.rect(s, WALL_BAND, (0, WALL_FACE.y, IW, 3))
    pygame.draw.rect(s, WALL_DARK, (0, WALL_FACE.bottom - 5, IW, 5))
    for x in range(0, IW, 16):  # brick courses
        pygame.draw.line(s, shade(WALL_C, -10), (x, WALL_FACE.y + 10), (x, WALL_FACE.bottom - 6))
    pygame.draw.line(s, shade(WALL_C, -10), (0, WALL_FACE.y + 20), (IW, WALL_FACE.y + 20))

    _floor(s, PLATFORM_1, rng)
    _floor(s, PLATFORM_2, rng)
    _tactile(s, PLATFORM_1.bottom - 8)
    _tactile(s, PLATFORM_2.top + 4)

    # Platform 1 drops into the pit, so we see its front face.
    pygame.draw.rect(s, EDGE_FACE, EDGE_1)
    pygame.draw.line(s, shade(EDGE_FACE, 24), (0, EDGE_1.y), (IW, EDGE_1.y))
    _pit(s, PIT_A, rng)
    pygame.draw.rect(s, KERB_C, KERB)
    pygame.draw.line(s, KERB_HI, (0, KERB.y), (IW, KERB.y))
    _pit(s, PIT_B, rng)
    pygame.draw.rect(s, shade(FLOOR_A, 30), LIP_2)
    pygame.draw.line(s, OUTLINE, (0, LIP_2.y), (IW, LIP_2.y))

    pygame.draw.rect(s, FRONT_C, FRONT_CAP)
    pygame.draw.line(s, FRONT_HI, (0, FRONT_CAP.y), (IW, FRONT_CAP.y))
    pygame.draw.line(s, OUTLINE, (0, FRONT_CAP.y - 1), (IW, FRONT_CAP.y - 1))

    sign_rect, led_rects = _furniture(s, station_name, line_color, network_lines)
    return s, sign_rect, led_rects

def _floor(s, rect: pygame.Rect, rng: random.Random) -> None:
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

def _tactile(s, y: int) -> None:
    for x in range(0, IW, 12):
        pygame.draw.rect(s, TACTILE, (x + 2, y, 8, 3))
        pygame.draw.line(s, TACTILE_DARK, (x + 2, y + 3), (x + 9, y + 3))

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

def _pillar(s, x: int, top: int, bottom: int) -> None:
    shadow = pygame.Surface((14, bottom - top), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 50))
    s.blit(shadow, (x + 6, top + 4))
    box(s, pygame.Rect(x, top, 8, bottom - top), PILLAR)
    pygame.draw.line(s, PILLAR_HI, (x, top), (x, bottom - 1))
    pygame.draw.line(s, PILLAR_DK, (x + 7, top), (x + 7, bottom - 1))

def _furniture(s, station_name: str, line_color, network_lines) -> tuple[pygame.Rect, dict[int, pygame.Rect]]:
    # Station sign on the wall, text drawn later at full resolution.
    sign_rect = pygame.Rect(IW // 2 - 78, WALL_FACE.y + 8, 156, 16)
    box(s, sign_rect, SIGN_BG, SIGN_EDGE)
    pygame.draw.rect(s, line_color, (sign_rect.x + 3, sign_rect.y + 3, 5, 10))

    # Posters, a network map board, a clock, a ticket machine, a vending machine.
    for i, color in enumerate([(200, 80, 70), (70, 130, 200), (230, 190, 80)]):
        box(s, pygame.Rect(118 + i * 22, WALL_FACE.y + 9, 16, 18), color)
        pygame.draw.rect(s, shade(color, 60), (121 + i * 22, WALL_FACE.y + 12, 10, 4))
    board = pygame.Rect(196, WALL_FACE.y + 8, 44, 24)
    box(s, board, (236, 232, 222))
    for i, line in enumerate(network_lines):
        pygame.draw.line(s, line.color, (board.x + 4 + i * 3, board.y + 4 + i * 5), (board.right - 5 - i * 4, board.bottom - 4 - i * 2), 2)
    box(s, pygame.Rect(256, WALL_FACE.y + 10, 12, 12), (236, 236, 240))
    pygame.draw.line(s, OUTLINE, (262, WALL_FACE.y + 16), (262, WALL_FACE.y + 12))
    pygame.draw.line(s, OUTLINE, (262, WALL_FACE.y + 16), (265, WALL_FACE.y + 16))

    # Live LED boards: one on the wall for platform 1, one on the front for 2.
    led_rects = {
        -1: pygame.Rect(IW // 2 + 82, WALL_FACE.y + 10, 108, 14),
        1: pygame.Rect(IW // 2 + 82, FRONT_CAP.y + 5, 108, 14),
    }
    for rect in led_rects.values():
        box(s, rect, LED_BG, (90, 70, 40))

    # Exit stairs at both ends of each platform, with a green sign.
    for platform in (PLATFORM_1, PLATFORM_2):
        for stairs in exits(platform):
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
        _pillar(s, px, PLATFORM_1.y + 4, PLATFORM_1.y + 40)
        _pillar(s, px, PLATFORM_2.y + 14, PLATFORM_2.bottom - 4)
    # Yellow wet-floor signs like in the reference, just for flavour.
    for wx in (IW - 60, IW - 44):
        pygame.draw.polygon(s, TACTILE, [(wx, PLATFORM_1.y + 30), (wx + 5, PLATFORM_1.y + 20), (wx + 10, PLATFORM_1.y + 30)])
        pygame.draw.polygon(s, OUTLINE, [(wx, PLATFORM_1.y + 30), (wx + 5, PLATFORM_1.y + 20), (wx + 10, PLATFORM_1.y + 30)], 1)
    return sign_rect, led_rects
