"""The control room: what it shows, and what you can do from it."""

import pygame
import pytest

from src.control_room import STATIONS_LISTED, ControlRoom, heat
from src.route import LOAD_COLORS, MapScene, World
from tests.conftest import run_for


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


@pytest.fixture
def room(display, world, sim):
    room = ControlRoom(world, sim)
    run_for(sim, 150)
    return room


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def key(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode="", scancode=0)


def test_it_opens_from_the_map_by_key_and_by_button(display, world, sim):
    scene = MapScene(world, sim)
    assert scene.handle(key(pygame.K_c)) == ("control",)
    scene.draw(display, False)
    spot = scene.panel.control_rect.center
    scene.handle(click(spot))
    assert scene.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=spot, button=1)) is None
    # The press itself is what asks for the room, since it is on the panel.
    assert scene.pending is None or scene.pending == ("control",)


def test_escape_and_c_and_the_map_button_all_leave(room, display):
    assert room.handle(key(pygame.K_ESCAPE)) == "back"
    assert room.handle(key(pygame.K_c)) == "back"
    assert room.handle(click(room.back_rect.center)) == "back"


def test_the_lines_are_worst_first_and_add_up(room, metro_map):
    rows = room._line_load()
    assert [row[0].name for row in rows] == [row[0].name for row in sorted(rows, key=lambda r: -r[1])]
    counted = sum(row[1] for row in rows)
    waiting = sum(1 for s in metro_map.stations.values() for p in s.waiting if p.next_line)
    assert counted == waiting
    for line, _, riders, trains in rows:
        assert trains == len([m for m in room.sim.metros if m.line == line.name])
        assert riders == sum(len(m.riders) for m in room.sim.metros if m.line == line.name)


def test_the_busiest_platforms_really_are_the_busiest(room, metro_map):
    listed = room._busiest()
    assert len(listed) == STATIONS_LISTED
    counts = [len(s.waiting) for s in listed]
    assert counts == sorted(counts, reverse=True)
    rest = [len(s.waiting) for s in metro_map.stations.values() if s not in listed]
    assert min(counts) >= max(rest, default=0)


def test_the_fleet_can_be_changed_from_the_desk(room, display):
    room.draw(display, False)
    rect, action, line = next(b for b in room.fleet_buttons if b[1] == "add")
    before = len([m for m in room.sim.metros if m.line == line])
    assert room.handle(click(rect.center)) is None
    assert len([m for m in room.sim.metros if m.line == line]) == before + 1

    rect, action, line = next(b for b in room.fleet_buttons if b[1] == "remove" and b[2] == line)
    before = len([m for m in room.sim.metros if m.line == line])
    room.handle(click(rect.center))
    assert len([m for m in room.sim.metros if m.line == line]) == before - 1


def test_clicking_a_platform_goes_and_stands_on_it(room, display):
    room.draw(display, False)
    rect, name = room.station_rows[0]
    assert room.handle(click(rect.center)) == ("station", name)


def test_a_stopped_train_can_be_looked_at(room, display):
    for other in room.sim.metros:
        other.stalled, other.fault = 0.0, ""
    metro = room.sim.metros[0]
    metro.stalled, metro.fault = 9.0, "brake fault"
    room.draw(display, False)
    assert room.look_buttons, "a stopped train should be listed"
    rect, listed = room.look_buttons[0]
    assert listed is metro
    assert room.handle(click(rect.center)) == ("tunnel", metro)


def test_the_worst_incident_is_at_the_top(room, display):
    first, second = room.sim.metros[0], room.sim.metros[1]
    first.stalled, second.stalled = 4.0, 12.0
    room.draw(display, False)
    assert [m.id for _, m in room.look_buttons][:2] == [second.id, first.id]


def test_it_draws_with_nothing_wrong_and_with_everything_wrong(room, display):
    for metro in room.sim.metros:
        metro.stalled = 0.0
    room.draw(display, False)
    assert not room.look_buttons
    for metro in room.sim.metros:
        metro.stalled = 10.0
    room.draw(display, False)
    assert len(room.look_buttons) <= 6, "the panel only has room for so many"
    room.draw(display, True, 4.0)


def test_the_heat_goes_green_amber_red():
    assert heat(0.1) == LOAD_COLORS[0]
    assert heat(0.5) == LOAD_COLORS[1]
    assert heat(0.9) == LOAD_COLORS[2]
    assert heat(3.0) == LOAD_COLORS[2], "past full is still red, not an error"


def test_nothing_is_clickable_until_it_has_been_drawn(display, world, sim):
    """The rows are laid out while drawing, so a click before the first frame
    must not reach into last frame's positions."""
    fresh = ControlRoom(world, sim)
    assert fresh.station_rows == [] and fresh.fleet_buttons == [] and fresh.look_buttons == []
    assert fresh.handle(click((640, 500))) is None


def test_the_fault_bar_follows_you_into_a_station(display, world, sim, metro_map):
    """A fault you can only see at the desk is one you will not deal with."""
    from src.route import draw_fault_alert, stopped_trains
    from src.station_view import StationView

    run_for(sim, 60)
    for metro in sim.metros:
        metro.stalled, metro.fault = 0.0, ""
    view = StationView(world, sim, "Alameda")
    view.draw(display, False)
    assert view.alert is None, "nothing wrong, nothing to say"

    broken = sim.metros[0]
    broken.stalled, broken.fault = 20.0, "brake fault"
    assert stopped_trains(sim) == [broken]
    view.draw(display, False)
    assert view.alert is not None
    rect, target = view.alert
    assert target == ("tunnel", broken), "one fault, so it takes you straight there"
    assert view.handle(click(rect.center)) == ("tunnel", broken)

    # More than one and it cannot choose for you, so it opens the desk.
    sim.metros[1].stalled, sim.metros[1].fault = 12.0, "door interlock"
    view.draw(display, False)
    assert view.alert[1] == ("control",)
    assert draw_fault_alert(display, view.head, view.small, sim, (0, 0), 0) is not None


def test_a_train_pulling_away_is_no_longer_an_alert(display, world, sim):
    from src.route import stopped_trains

    run_for(sim, 30)
    for metro in sim.metros:
        metro.stalled, metro.fault = 0.0, ""
    broken = sim.metros[0]
    broken.stalled, broken.fault = 20.0, "brake fault"
    sim.release(broken)
    assert broken.stalled > 0, "it is still standing still for a moment"
    assert stopped_trains(sim) == [], "but it is dealt with, so stop shouting about it"
