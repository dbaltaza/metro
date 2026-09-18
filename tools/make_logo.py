"""Draws the game logo and window icon as pixel art, in the palette of the scenes.

    .venv/bin/python tools/make_logo.py

Writes docs/logo.png (the wordmark over a train on the route) and
docs/icon.png (the red M badge used as the window icon).

The lockup is the one the stations use: the red M badge standing in for the
first letter of METRO, LISBOA tracked out underneath to the width of the
letters above it, and below that the train running along a route bar carrying
the four line colours.
"""

import os
import sys

import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.network import build_demo_map  # noqa: E402
from src.sprites import OUTLINE, shade  # noqa: E402
from src.station_layout import (  # noqa: E402
    BAND, BOARD_AMBER, GLASS_PANE, HEADLIGHT, ML_RED, ROOF_GREY, SILVER, SILVER_HI,
    SILVER_LO, SKIRT,
)

SCALE = 4
W, H = 200, 124
PLATE = (24, 26, 31)
PLATE_TILE = (26, 28, 33)
PLATE_EDGE = (44, 47, 55)
RAIL_BED = (18, 19, 23)
STOP_DOT = (236, 239, 245)
DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")

# 5x7 capitals, "X" is ink. I is 3 wide. Stroke weight is one cell throughout,
# so every letter has the same colour on the page.
GLYPHS = {
    "M": ["X...X", "XX.XX", "X.X.X", "X.X.X", "X...X", "X...X", "X...X"],
    "E": ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"],
    "T": ["XXXXX", "..X..", "..X..", "..X..", "..X..", "..X..", "..X.."],
    "R": ["XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"],
    "O": [".XXX.", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."],
    "L": ["X....", "X....", "X....", "X....", "X....", "X....", "XXXXX"],
    "I": ["XXX", ".X.", ".X.", ".X.", ".X.", ".X.", "XXX"],
    "S": [".XXXX", "X....", "X....", ".XXX.", "....X", "....X", "XXXX."],
    "B": ["XXXX.", "X...X", "X...X", "XXXX.", "X...X", "X...X", "XXXX."],
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    # The badge M is square, with a deep middle so it does not read as a
    # dented pi. The narrow one is for the icon, where five cells is all the
    # room there is.
    "M7": ["X.....X", "XX...XX", "X.X.X.X", "X..X..X", "X.....X", "X.....X", "X.....X"],
    "M6": ["X...X", "XX.XX", "X.X.X", "X...X", "X...X", "X...X"],
}


def glyph_size(ch: str, px: int) -> tuple[int, int]:
    rows = GLYPHS[ch]
    return len(rows[0]) * px, len(rows) * px


def word_width(word: str, px: int, tracking: int) -> int:
    return sum(glyph_size(ch, px)[0] for ch in word) + tracking * (len(word) - 1)


def glyph(s: pygame.Surface, ch: str, x: int, y: int, px: int, color, shadow: int = 0, bevel: bool = True) -> int:
    """One glyph at pixel size px, lit from above. Returns its width."""
    rows = GLYPHS[ch]
    if shadow:
        for r, row in enumerate(rows):
            for c, ink in enumerate(row):
                if ink == "X":
                    pygame.draw.rect(s, OUTLINE, (x + c * px + shadow, y + r * px + shadow, px, px))
    edge = max(1, px // 4)
    for r, row in enumerate(rows):
        for c, ink in enumerate(row):
            if ink != "X":
                continue
            cell = pygame.Rect(x + c * px, y + r * px, px, px)
            pygame.draw.rect(s, color, cell)
            if not bevel:
                continue
            if r == 0 or rows[r - 1][c] != "X":
                pygame.draw.rect(s, shade(color, 44), (cell.x, cell.y, px, edge))
            if r == len(rows) - 1 or rows[r + 1][c] != "X":
                pygame.draw.rect(s, shade(color, -42), (cell.x, cell.bottom - edge, px, edge))
    return len(rows[0]) * px


def word(s: pygame.Surface, text: str, x: int, y: int, px: int, color, tracking: int, shadow: int = 0) -> None:
    for ch in text:
        x += glyph(s, ch, x, y, px, color, shadow) + tracking


def m_badge(s: pygame.Surface, rect: pygame.Rect) -> None:
    """The red rounded badge with a white M, like the station entrance signs.

    The M is sized from both axes and centred, so it keeps its air however
    big the badge is: at the old size it grew until it touched the edges."""
    radius = max(2, rect.width // 5)
    pygame.draw.rect(s, OUTLINE, rect.inflate(2, 2), border_radius=radius + 1)
    pygame.draw.rect(s, ML_RED, rect, border_radius=radius)
    pygame.draw.rect(s, shade(ML_RED, 30), (rect.x + radius // 2, rect.y + 1, rect.width - radius, 1))
    pygame.draw.rect(s, shade(ML_RED, -46), (rect.x + radius // 2, rect.bottom - 2, rect.width - radius, 1))
    # Two cuts of the same mark: the wide one wherever there is room for it,
    # the narrow one at icon size, where seven cells would leave it tiny.
    mark = "M7" if (rect.width - 6) // 7 >= 3 else "M6"
    rows, cols = len(GLYPHS[mark]), len(GLYPHS[mark][0])
    px = max(1, min((rect.width - 6) // cols, (rect.height - 6) // rows))
    gw, gh = glyph_size(mark, px)
    glyph(s, mark, rect.centerx - gw // 2, rect.centery - gh // 2, px, (252, 252, 252), bevel=False)


def train(s: pygame.Surface, x: int, y: int, length: int, stripe) -> None:
    """A Lisbon Metro car, side on, cab at the right, in the station-view style."""
    roof_h, side_h = 5, 12
    body = pygame.Rect(x, y, length, roof_h + side_h)
    shadow = pygame.Surface((length + 6, 3), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 70))
    s.blit(shadow, (x - 3, y + roof_h + side_h + 1))
    pygame.draw.rect(s, OUTLINE, body.inflate(2, 2), border_radius=3)
    pygame.draw.rect(s, ROOF_GREY, (x, y, length, roof_h), border_top_left_radius=3, border_top_right_radius=3)
    pygame.draw.line(s, shade(ROOF_GREY, 30), (x + 2, y + 1), (x + length - 3, y + 1))
    pygame.draw.line(s, shade(ROOF_GREY, -40), (x, y + roof_h - 1), (x + length - 1, y + roof_h - 1))
    for ax in (x + 12, x + length - 30):
        pygame.draw.rect(s, shade(ROOF_GREY, -24), (ax, y + 1, 12, 3))
    sy = y + roof_h
    pygame.draw.rect(s, SILVER, (x, sy, length, side_h))
    pygame.draw.line(s, SILVER_HI, (x, sy), (x + length - 1, sy))
    pygame.draw.rect(s, BAND, (x, sy + 2, length, 5))
    pygame.draw.rect(s, stripe, (x, sy + 7, length, 1))
    pygame.draw.rect(s, SILVER_LO, (x, sy + 9, length, 1))
    pygame.draw.rect(s, SKIRT, (x, sy + 10, length, 2))
    doors = [x + 14, x + length // 2 - 8, x + length - 32]
    for wx in range(x + 4, x + length - 14, 7):
        if any(abs(wx + 2 - d) < 8 for d in doors):
            continue
        pygame.draw.rect(s, GLASS_PANE, (wx, sy + 3, 5, 3))
        pygame.draw.line(s, shade(GLASS_PANE, 50), (wx, sy + 3), (wx + 4, sy + 3))
    for d in doors:
        door = pygame.Rect(d - 4, sy + 1, 8, side_h - 3)
        pygame.draw.rect(s, OUTLINE, door.inflate(2, 0))
        for lx in (door.x, door.centerx):
            pygame.draw.rect(s, SILVER_LO, (lx, door.y, 4, door.height))
            pygame.draw.rect(s, BAND, (lx + 1, sy + 2, 2, 5))
            pygame.draw.rect(s, GLASS_PANE, (lx + 1, sy + 3, 2, 2))
            pygame.draw.rect(s, stripe, (lx, sy + 7, 4, 1))
        pygame.draw.line(s, OUTLINE, (door.centerx, door.y), (door.centerx, door.bottom - 1))
    # Cab at the right end: windshield, amber board, headlight and its spill.
    fx = x + length - 7
    pygame.draw.rect(s, BAND, (fx, sy + 1, 6, 7))
    pygame.draw.rect(s, GLASS_PANE, (fx + 1, sy + 2, 4, 4))
    pygame.draw.rect(s, HEADLIGHT, (x + length - 4, sy + 9, 3, 2))
    pygame.draw.rect(s, OUTLINE, (x + length - 34, y + 1, 22, 3))
    pygame.draw.rect(s, BOARD_AMBER, (x + length - 33, y + 2, 20, 1))
    # Red M between the doors.
    lx, ly = x + length // 2 + 10, sy + 8
    pygame.draw.rect(s, ML_RED, (lx, ly - 1, 5, 3))
    for px_, py_ in ((1, 0), (1, 1), (3, 0), (3, 1), (2, 0)):
        s.set_at((lx + px_, ly + py_ - 1), (250, 250, 250))
    # Bogies.
    for bx in (x + 8, x + length - 22):
        pygame.draw.rect(s, OUTLINE, (bx, y + roof_h + side_h, 12, 2))
        pygame.draw.rect(s, (28, 28, 32), (bx + 2, y + roof_h + side_h + 1, 3, 1))
        pygame.draw.rect(s, (28, 28, 32), (bx + 7, y + roof_h + side_h + 1, 3, 1))


def plate(s: pygame.Surface) -> None:
    """The dark backing, faintly tiled like a station wall so it reads on a
    white README as well as a black one."""
    rect = pygame.Rect(0, 0, W, H)
    pygame.draw.rect(s, OUTLINE, rect, border_radius=9)
    pygame.draw.rect(s, PLATE, rect.inflate(-2, -2), border_radius=8)
    tiles = pygame.Surface((W - 4, H - 4), pygame.SRCALPHA)
    for ty in range(0, H, 9):
        for tx in range((ty // 9 % 2) * 8, W, 16):
            pygame.draw.rect(tiles, PLATE_TILE, (tx, ty, 15, 8))
    mask = pygame.Surface(tiles.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=7)
    tiles.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(tiles, (2, 2))
    pygame.draw.rect(s, PLATE_EDGE, (9, 2, W - 18, 1))


def route(s: pygame.Surface, y: int, colors: list[tuple[int, int, int]]) -> None:
    """One route bar carrying the four line colours, with stops on it, instead
    of four separate rules stacked up like a barcode."""
    left, right = 14, W - 14
    pygame.draw.rect(s, RAIL_BED, (left - 2, y - 2, right - left + 4, 7), border_radius=3)
    span = (right - left) / len(colors)
    for i, color in enumerate(colors):
        start = round(left + i * span)
        pygame.draw.rect(s, color, (start, y, round(left + (i + 1) * span) - start, 3))
    for i in range(len(colors) + 1):
        cx = round(left + i * span)
        cx = min(max(cx, left + 1), right - 2)
        pygame.draw.rect(s, OUTLINE, (cx - 2, y - 2, 5, 7))
        pygame.draw.rect(s, STOP_DOT, (cx - 1, y - 1, 3, 5))


def logo(colors: list[tuple[int, int, int]]) -> pygame.Surface:
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    plate(s)

    # METRO: the badge is the M, so the letters have to line up with it.
    badge = pygame.Rect(14, 13, 46, 46)
    m_badge(s, badge)
    cap = 5
    letters_x = badge.right + 9
    letters_y = badge.centery - glyph_size("E", cap)[1] // 2
    word(s, "ETRO", letters_x, letters_y, cap, SILVER, tracking=6, shadow=2)

    # LISBOA tracked out to exactly the width of the letters above it.
    sub, width = 2, word_width("ETRO", cap, 6)
    tracking = round((width - word_width("LISBOA", sub, 0)) / 5)
    word(s, "LISBOA", letters_x, badge.bottom + 5, sub, BOARD_AMBER, tracking=tracking)

    train(s, 24, 86, W - 48, colors[1])
    route(s, 110, colors)
    return s


def icon() -> pygame.Surface:
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    m_badge(s, pygame.Rect(2, 2, 28, 28))
    return s


def main() -> None:
    pygame.init()
    colors = [line.color for line in build_demo_map().lines]
    os.makedirs(DOCS, exist_ok=True)
    art = logo(colors)
    pygame.image.save(pygame.transform.scale(art, (W * SCALE, H * SCALE)), os.path.join(DOCS, "logo.png"))
    pygame.image.save(pygame.transform.scale(icon(), (64, 64)), os.path.join(DOCS, "icon.png"))
    print("wrote docs/logo.png and docs/icon.png")


if __name__ == "__main__":
    main()
