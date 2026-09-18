"""Every station is clad differently, and always the same way."""

import os
import subprocess
import sys

import pygame
import pytest

from src.station_layout import PANELS, WALL_FACE, render_backdrop
from src.station_style import (
    MOTIFS, PALETTES, PATTERNS, SIGNATURES, SIGNATURE_ONLY, style_for, underground,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bytes_of(surface, rect=None):
    return pygame.image.tostring(surface.subsurface(rect) if rect else surface, "RGB")


def backdrop(metro_map, name):
    line = next(line for line in metro_map.lines if name in line.stations)
    return render_backdrop(name, line.color, metro_map.lines)[0]


def test_every_station_is_clad_in_something(metro_map):
    for name in metro_map.stations:
        style = style_for(name)
        assert style.palette.name in PALETTES
        assert style.pattern in PATTERNS
        assert style.motif in MOTIFS


def test_a_station_looks_the_same_in_a_fresh_process():
    """This used to be hash(), which python salts per process, so a station
    was a different colour every time the game was started."""
    code = ("import sys; sys.path.insert(0, %r);"
            "from src.station_style import style_for;"
            "s = style_for('Anjos');"
            "print(s.palette.name, s.pattern, s.motif)" % ROOT)
    runs = []
    for seed in ("1", "2", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        runs.append(subprocess.run([sys.executable, "-c", code], capture_output=True,
                                   text=True, env=env, cwd=ROOT).stdout.strip())
    assert len(set(runs)) == 1, runs
    assert runs[0] == " ".join([style_for("Anjos").palette.name, style_for("Anjos").pattern,
                                style_for("Anjos").motif])


def test_the_ones_with_a_look_of_their_own_keep_it(metro_map):
    for name, (palette, pattern, motif) in SIGNATURES.items():
        assert name in metro_map.stations, f"{name} is not on this network"
        style = style_for(name)
        assert (style.palette.name, style.pattern, style.motif) == (palette, pattern, motif)
    assert style_for("Rossio").motif == "waves", "the wave calçada is the whole point"


def test_a_one_off_palette_turns_up_once(metro_map):
    for palette in SIGNATURE_ONLY:
        wearing = [n for n in metro_map.stations if style_for(n).palette.name == palette]
        assert len(wearing) == 1, wearing


def test_the_network_does_not_all_look_alike(metro_map):
    looks = {n: (style_for(n).palette.name, style_for(n).pattern, style_for(n).motif)
             for n in metro_map.stations}
    assert len(set(looks.values())) >= len(looks) - 6, "too many stations wearing the same thing"
    # Two stops in a row looking identical is the one repeat you would notice.
    for line in metro_map.lines:
        for a, b in zip(line.stations, line.stations[1:]):
            assert looks[a] != looks[b], f"{a} and {b} are next to each other and identical"


def test_people_still_show_up_against_every_floor():
    """Walls can be as light as they like. Floors cannot: people stand on
    them, and a floor as pale as the walls would swallow them."""
    for palette in PALETTES.values():
        for floor in (palette.floor_a, palette.floor_b):
            brightness = sum(floor) / 3
            assert 60 <= brightness <= 150, (palette.name, floor, brightness)


def test_two_stations_are_not_drawn_the_same(display, metro_map):
    wall = pygame.Rect(0, 0, WALL_FACE.width, WALL_FACE.bottom)
    seen = {}
    for name in ("Rossio", "Olaias", "Campo Pequeno", "Anjos", "Telheiras"):
        seen[name] = bytes_of(backdrop(metro_map, name), wall)
    assert len(set(seen.values())) == len(seen)


def test_a_station_is_drawn_the_same_way_every_time(display, metro_map):
    """The stains and the gravel are random, so they have to be seeded from
    something that does not move between one visit and the next."""
    assert bytes_of(backdrop(metro_map, "Anjos")) == bytes_of(backdrop(metro_map, "Anjos"))


def test_the_tile_panels_sit_where_nothing_covers_them(display, metro_map):
    """They went on the left of the wall first, where the platform caption
    is painted straight over them."""
    caption = pygame.Rect(0, 0, 115, WALL_FACE.bottom)   # the PLATFORM 1 plate
    for panel in PANELS:
        assert not panel.colliderect(caption), panel
        assert WALL_FACE.contains(panel), panel


def test_walking_in_shows_that_station_s_tiles(display, metro_map):
    from src.route import StationTransition, World
    world = World(metro_map)
    plain = StationTransition(("map",), (255, 214, 90), "Metro de Lisboa", "back", metro_map.lines)
    assert plain.tile == StationTransition.TILE, "leaving is not any station's passage"
    for name in ("Rossio", "Olaias"):
        palette = style_for(name).palette
        tr = StationTransition(("station", name), world.serving[name][0].color, name, "down",
                               world.serving[name], palette=palette)
        assert tr.tile == underground(palette.wall)
        assert sum(tr.tile) < sum(palette.wall), "the passage is darker than the platform"


@pytest.mark.parametrize("palette", list(PALETTES.values()), ids=lambda p: p.name)
def test_the_underground_cut_of_a_palette_stays_in_the_dark(palette):
    """Whatever the cladding, the passage has to read as underground: taking
    a fixed amount off every palette left half of them black."""
    dim = underground(palette.wall)
    assert 20 <= sum(dim) / 3 <= 95, (palette.name, dim)
