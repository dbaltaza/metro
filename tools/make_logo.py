"""Draws the game logo and window icon as pixel art, in the palette of the scenes.

    .venv/bin/python tools/make_logo.py

Writes docs/logo.png (the wordmark over a train on the four lines) and
docs/icon.png (the red M badge used as the window icon).
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
W, H = 176, 104
DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")

# 5x7 glyphs (I is 3 wide). "X" is ink.
GLYPHS = {
    "M": ["X...X", "XX.XX", "X.X.X", "X...X", "X...X", "X...X", "X...X"],
    "E": ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"],
    "T": ["XXXXX", "..X..", "..X..", "..X..", "..X..", "..X..", "..X.."],
    "R": ["XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"],
    "O": [".XXX.", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."],
    "L": ["X....", "X....", "X....", "X....", "X....", "X....", "XXXXX"],
    "I": ["XXX", ".X.", ".X.", ".X.", ".X.", ".X.", "XXX"],
    "S": [".XXXX", "X....", "X....", ".XXX.", "....X", "....X", "XXXX."],
    "B": ["XXXX.", "X...X", "X...X", "XXXX.", "X...X", "X...X", "XXXX."],
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
}


def glyph(s: pygame.Surface, ch: str, x: int, y: int, px: int, color, shadow=True) -> int:
    """Draws one glyph with pixel size px. Returns the advance in pixels."""
    rows = GLYPHS[ch]
    for r, row in enumerate(rows):
        for c, ink in enumerate(row):
            if ink != "X":
                continue
            cell = pygame.Rect(x + c * px, y + r * px, px, px)
            if shadow:
                pygame.draw.rect(s, OUTLINE, cell.move(px // 2 + 1, px // 2 + 1))
            pygame.draw.rect(s, color, cell)
            if r == 0 or rows[r - 1][c] != "X":
                pygame.draw.rect(s, shade(color, 40), (cell.x, cell.y, px, max(1, px // 3)))
    return len(rows[0]) * px + px


def m_badge(s: pygame.Surface, rect: pygame.Rect) -> None:
    """The red rounded badge with a white M, like the station entrance signs."""
    pygame.draw.rect(s, OUTLINE, rect.inflate(2, 2), border_radius=rect.width // 4 + 1)
    pygame.draw.rect(s, ML_RED, rect, border_radius=rect.width // 4)
    pygame.draw.rect(s, shade(ML_RED, 36), (rect.x + 2, rect.y + 1, rect.width - 4, 1))
    pygame.draw.rect(s, shade(ML_RED, -50), (rect.x + 2, rect.bottom - 2, rect.width - 4, 1))
    px = max(1, min((rect.width - 6) // 5, (rect.height - 6) // 7))
    gw, gh = 5 * px, 7 * px
    glyph(s, "M", rect.centerx - gw // 2, rect.centery - gh // 2, px, (250, 250, 250), shadow=False)


def train(s: pygame.Surface, x: int, y: int, length: int, stripe) -> None:
    """A Lisbon Metro car, side on, cab at the right, in the station-view style."""
    roof_h, side_h = 5, 12
    body = pygame.Rect(x, y, length, roof_h + side_h)
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
    # Cab at the right end: windshield, amber board, headlight.
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


def logo(colors: list[tuple[int, int, int]]) -> pygame.Surface:
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    # Dark badge so it reads on light and dark READMEs.
    plate = pygame.Rect(0, 0, W, H)
    pygame.draw.rect(s, OUTLINE, plate, border_radius=8)
    pygame.draw.rect(s, (24, 26, 31), plate.inflate(-2, -2), border_radius=7)
    pygame.draw.rect(s, (36, 39, 46), (2, 2, W - 4, 1))

    # Wordmark: red M badge then E T R O in silver.
    px = 4
    y = 12
    badge = pygame.Rect(14, y - 3, 7 * px + 6, 7 * px + 6)
    m_badge(s, badge)
    x = badge.right + 6
    for ch in "ETRO":
        x += glyph(s, ch, x, y, px, SILVER)
    # "LISBOA" small under the wordmark, right-aligned with it.
    sx = badge.x
    for ch in "LISBOA":
        sx += glyph(s, ch, sx, y + 7 * px + 6, 2, BOARD_AMBER)
    pygame.draw.rect(s, BOARD_AMBER, (sx, y + 7 * px + 6 + 12, x - px - sx, 1))

    # The four lines as tracks, the train on top of them.
    ty = 74
    for i, color in enumerate(colors):
        pygame.draw.rect(s, OUTLINE, (10, ty + 12 + i * 3, W - 20, 3))
        pygame.draw.rect(s, color, (11, ty + 12 + i * 3, W - 22, 2))
    train(s, 30, ty - 6, W - 60, colors[1])
    return s


def icon() -> pygame.Surface:
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
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
