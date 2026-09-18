"""The logo and the window icon.

Only the parts that have gone wrong before are checked here: the M is sized
from the badge it sits in, and it used to be sized from the width alone, so
it grew until it touched the top and bottom of the badge.
"""

import pygame
import pytest

from src.station_layout import ML_RED
from tools.make_logo import H, W, icon, logo, m_badge, word_width

WHITE = (252, 252, 252)


@pytest.fixture
def colors(metro_map):
    return [line.color for line in metro_map.lines]


def ink_bounds(surface, color):
    """The box the pixels of one colour fill, or None if there are none."""
    xs = [(x, y) for x in range(surface.get_width()) for y in range(surface.get_height())
          if surface.get_at((x, y))[:3] == color]
    if not xs:
        return None
    return (min(x for x, _ in xs), min(y for _, y in xs),
            max(x for x, _ in xs), max(y for _, y in xs))


@pytest.mark.parametrize("size", [24, 28, 32, 46, 64, 96])
def test_the_m_is_sized_from_both_sides_of_the_badge(display, size):
    """It used to be sized from the width alone, so on the taller cut of the
    mark it grew until it touched the top and bottom of the badge. The wide
    cut is square, so there the two rules come to the same thing."""
    surface = pygame.Surface((size + 8, size + 8), pygame.SRCALPHA)
    rect = pygame.Rect(4, 4, size, size)
    m_badge(surface, rect)
    left, top, right, bottom = ink_bounds(surface, WHITE)
    assert right - left + 1 <= size - 6, "too wide for its badge"
    assert bottom - top + 1 <= size - 6, "too tall for its badge"
    # Centred, give or take the odd pixel of a whole number of cells.
    margins = (left - rect.left, top - rect.top, rect.right - 1 - right, rect.bottom - 1 - bottom)
    assert abs(margins[0] - margins[2]) <= 2 and abs(margins[1] - margins[3]) <= 2, margins


def test_the_icon_is_a_red_badge_with_a_white_m(display):
    art = icon()
    assert art.get_size() == (32, 32)
    assert ink_bounds(art, WHITE) is not None
    assert ink_bounds(art, ML_RED) is not None
    assert art.get_at((0, 0))[3] == 0, "the corners are rounded, so they have to be clear"


def test_the_subtitle_never_outgrows_the_word_above_it(display):
    """LISBOA is letterspaced to the width of ETRO. If it came out wider the
    lockup would be a stack of two words, not one mark."""
    assert word_width("LISBOA", 2, 12) <= word_width("ETRO", 5, 6)


def test_the_logo_is_drawn_at_the_size_it_is_saved_at(display, colors):
    art = logo(colors)
    assert art.get_size() == (W, H)
    # Every line gets a length of the route bar along the bottom.
    for color in colors:
        assert ink_bounds(art, color) is not None, color
