"""Moving around the network map: panning, zooming and the corner minimap."""

import collections

import pygame
import pytest

from src.route import (
    DRAG_SLOP, HIGHLIGHT, LABEL_COLOR, LABEL_SHADOW, MAP_IH, MAP_IW, MAP_RECT,
    PIX, ZOOMS, Camera, MapScene, World, station_label,
)
from tests.conftest import FRAME, run_for


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


@pytest.fixture
def scene(display, world, sim):
    return MapScene(world, sim)


def press(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def release(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)


def move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0))


def drag(scene, start, end):
    """A press, a move and a release: what a hand on a mouse actually sends."""
    scene.handle(press(start))
    scene.handle(move(end))
    return scene.handle(release(end))


def central(world):
    """A station in the middle of the map, so the camera has room to move
    around it in every direction."""
    return min(world.ipositions,
               key=lambda n: abs(world.ipositions[n][0] - MAP_IW / 2) + abs(world.ipositions[n][1] - MAP_IH / 2))


def screen_pos(scene, name):
    return tuple(round(v) for v in scene.camera.to_screen(scene.world.ipositions[name]))


def test_the_map_opens_with_the_whole_network_in_view(scene):
    assert scene.camera.step == 0
    assert scene.camera.source() == pygame.Rect(0, 0, MAP_IW, MAP_IH)


def test_every_zoom_step_scales_by_a_whole_number_of_pixels(scene):
    """Fractional scaling makes some pixels bigger than others, which is very
    visible on art this chunky."""
    camera = scene.camera
    for step in range(len(ZOOMS)):
        camera.step = step
        assert camera.scale == PIX * camera.zoom
        assert camera.scale == int(camera.scale)


def test_zooming_holds_the_map_still_under_the_cursor(scene):
    camera = scene.camera
    focus = (MAP_RECT.centerx + 180, MAP_RECT.centery - 120)
    before = camera.to_world(focus)
    for step in (1, 2, 3, 4, 2, 0):
        camera.zoom_to(step, focus)
        after = camera.to_world(focus)
        # A world pixel of slack: the view corner is snapped to whole pixels.
        assert abs(after[0] - before[0]) <= 1.5 and abs(after[1] - before[1]) <= 1.5, (step, before, after)


def test_the_view_never_leaves_the_map(scene):
    camera = scene.camera
    for step in range(len(ZOOMS)):
        camera.zoom_to(step)
        for dx, dy in ((-9000, 0), (9000, 0), (0, -9000), (0, 9000)):
            camera.pan(dx, dy)
            src = camera.source()
            assert src.x >= 0 and src.y >= 0
            assert src.right <= MAP_IW and src.bottom <= MAP_IH


def test_zooming_out_all_the_way_refits_the_whole_network(scene):
    scene.camera.zoom_to(3, (MAP_RECT.x + 40, MAP_RECT.y + 40))
    scene.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_0, mod=0, unicode="0", scancode=0))
    assert scene.camera.source() == pygame.Rect(0, 0, MAP_IW, MAP_IH)


def test_the_wheel_zooms_in_and_out(scene):
    scene.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, flipped=False, which=0))
    assert scene.camera.step == 1
    scene.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False, which=0))
    assert scene.camera.step == 0
    # Already fitted: another notch out changes nothing.
    scene.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False, which=0))
    assert scene.camera.step == 0


def test_clicking_a_station_still_walks_into_it(scene):
    scene.camera.zoom_to(2)
    name = central(scene.world)
    scene.camera.centre_on(scene.world.ipositions[name])
    spot = screen_pos(scene, name)
    assert drag(scene, spot, spot) == name


def test_dragging_moves_the_map_instead_of_entering_a_station(scene):
    """A drag that starts on a station must not drop you onto its platform."""
    scene.camera.zoom_to(2)
    name = central(scene.world)
    scene.camera.centre_on(scene.world.ipositions[name])
    start = screen_pos(scene, name)
    before = scene.camera.source().topleft

    assert drag(scene, start, (start[0] - 90, start[1] + 40)) is None
    after = scene.camera.source().topleft
    assert after != before
    # The map followed the hand: dragging left shows what was to the right.
    assert after[0] > before[0] and after[1] < before[1]


def test_a_wobble_of_a_few_pixels_is_still_a_click(scene):
    scene.camera.zoom_to(1)
    name = central(scene.world)
    scene.camera.centre_on(scene.world.ipositions[name])
    start = screen_pos(scene, name)
    assert drag(scene, start, (start[0] + DRAG_SLOP - 1, start[1])) == name


def test_panning_does_not_arm_a_click_on_the_next_press(scene):
    scene.camera.zoom_to(2)
    drag(scene, MAP_RECT.center, (MAP_RECT.centerx - 120, MAP_RECT.centery))
    assert scene.grab is None and not scene.dragged


def test_arrow_keys_pan_the_map(scene, monkeypatch):
    scene.camera.zoom_to(3)
    scene.camera.centre_on((MAP_IW / 2, MAP_IH / 2))
    before = scene.camera.source().topleft
    held = collections.defaultdict(int, {pygame.K_RIGHT: 1, pygame.K_UP: 1})
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: held)
    for _ in range(12):
        scene.update(FRAME)
    after = scene.camera.source().topleft
    assert after[0] > before[0] and after[1] < before[1]


def test_the_minimap_only_shows_when_you_are_zoomed_in(scene, display):
    scene.draw(display, False)
    assert not scene.camera.step
    # Fitted, the corner is free, so a press there is an ordinary map press.
    corner = scene.minimap_rect().center
    scene.handle(press(corner))
    assert scene.grab is not None and not scene.on_minimap


def test_the_minimap_jumps_the_camera_where_you_click(scene):
    scene.camera.zoom_to(4)
    rect = scene.minimap_rect()
    scene.handle(press((rect.x + 3, rect.y + 3)))
    assert scene.on_minimap
    assert scene.camera.source().topleft == (0, 0)

    scene.handle(move((rect.right - 3, rect.bottom - 3)))
    src = scene.camera.source()
    assert (src.right, src.bottom) == (MAP_IW, MAP_IH)
    assert scene.handle(release((rect.right - 3, rect.bottom - 3))) is None


def test_hovering_reads_the_station_under_the_camera(scene):
    scene.camera.zoom_to(3)
    name = central(scene.world)
    scene.camera.centre_on(scene.world.ipositions[name])
    scene.handle(move(screen_pos(scene, name)))
    assert scene.hovered == name
    scene.handle(move((MAP_RECT.right + 40, 20)))
    assert scene.hovered is None


def test_the_panel_buttons_still_work(scene, display):
    scene.draw(display, False)
    rect, action, line = next(b for b in scene.panel.buttons if b[1] == "add")
    before = len([m for m in scene.sim.metros if m.line == line])
    scene.handle(press(rect.center))
    assert len([m for m in scene.sim.metros if m.line == line]) == before + 1


def test_the_map_draws_at_every_zoom(scene, display, sim):
    run_for(sim, 20)
    scene.handle(move(screen_pos(scene, central(scene.world))))
    for step in range(len(ZOOMS)):
        scene.camera.zoom_to(step, MAP_RECT.center)
        scene.draw(display, False)
        assert scene.world.world.get_bitsize() == 24
        assert display.get_clip() == display.get_rect(), "the clip has to be handed back"


def test_labels_travel_with_the_map(scene, display):
    """Names are drawn live now, not baked into a layer, so they have to end up
    under the station they belong to at any zoom."""
    camera = scene.camera
    name = central(scene.world)
    at_fit = camera.to_screen(scene.world.label_spots[name])
    camera.zoom_to(2)
    camera.centre_on(scene.world.ipositions[name])
    zoomed = camera.to_screen(scene.world.label_spots[name])
    assert at_fit != zoomed
    # Still beside its own station, only further away in screen pixels.
    station = camera.to_screen(scene.world.ipositions[name])
    assert abs(zoomed[0] - station[0]) < 200 and abs(zoomed[1] - station[1]) < 200


def test_a_camera_of_its_own_per_scene(display, world, sim):
    """Nothing process-wide: two map scenes must not share a viewpoint."""
    first, second = MapScene(world, sim), MapScene(world, sim)
    first.camera.zoom_to(3)
    assert isinstance(second.camera, Camera)
    assert second.camera.step == 0


def test_every_station_gets_a_name_on_the_map(world):
    assert set(world.label_spots) == set(world.map.stations)


def test_names_grow_with_the_zoom_but_stay_readable(world):
    sizes = [world.label_font(step, False).size("Alameda")[1] for step in range(len(ZOOMS))]
    assert sizes == sorted(sizes) and sizes[-1] > sizes[0]
    # Bold for interchanges, so they stand out from ordinary stops.
    assert world.label_font(0, True).size("Alameda") > world.label_font(0, False).size("Alameda")


def test_a_name_is_composed_once_and_reused(world):
    """Fifty names are blitted every frame; building them each time is waste."""
    font = world.label_font(0, False)
    first = station_label(font, "Anjos", LABEL_COLOR)
    assert station_label(font, "Anjos", LABEL_COLOR) is first
    assert station_label(font, "Anjos", HIGHLIGHT) is not first


def test_a_name_is_cut_out_against_a_dark_stroke(world):
    """Names sit on top of track and buildings, so they need their own edge."""
    label = station_label(world.label_font(0, True), "Alameda", LABEL_COLOR)
    colors = [label.get_at((x, y)) for x in range(label.get_width()) for y in range(label.get_height())]
    assert any(c[:3] == LABEL_SHADOW and c[3] > 200 for c in colors)
    assert any(c[3] == 0 for c in colors), "and it must not be a solid block"


def test_the_hovered_name_lights_up(scene, display):
    name = central(scene.world)
    scene.handle(move(screen_pos(scene, name)))
    assert scene.hovered == name
    scene.draw(display, False)
    label = station_label(scene.world.label_font(0, scene.world.interchange[name]), name, HIGHLIGHT)
    rect = label.get_rect(center=tuple(round(v) for v in scene.camera.to_screen(scene.world.label_spots[name])))
    lit = sum(display.get_at((x, y))[:3] == HIGHLIGHT
              for x in range(rect.left, rect.right) for y in range(rect.top, rect.bottom))
    assert lit > 20, "the name of the station under the cursor should pick up the highlight"
