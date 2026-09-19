import pygame
import pytest

from src.route import SettingsMenu, StationTransition, Transition, World
from src.settings import OPTIONS, SETTINGS, choice_index
from src.sim import Simulation, spread_trains
from src.station_view import StationView
from tests.conftest import FRAME, run_for


def key(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode="", scancode=0)


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


@pytest.fixture
def menu(display):
    return SettingsMenu()


def test_s_opens_and_closes_the_menu(menu):
    assert not menu.open
    assert menu.handle(key(pygame.K_s)) is True
    assert menu.open
    assert menu.handle(key(pygame.K_ESCAPE)) is True
    assert not menu.open


def test_a_closed_menu_lets_events_through(menu):
    assert menu.handle(key(pygame.K_SPACE)) is False
    assert menu.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1)) is False
    # Tab still belongs to the station scene, for switching line.
    assert menu.handle(key(pygame.K_TAB)) is False


def test_an_open_menu_swallows_everything(menu):
    menu.handle(key(pygame.K_s))
    assert menu.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5))) is True
    assert menu.handle(key(pygame.K_SPACE)) is True


def test_arrows_move_between_rows_and_change_the_value(menu):
    menu.handle(key(pygame.K_s))
    assert menu.row == 0
    menu.handle(key(pygame.K_DOWN))
    assert menu.row == 1
    menu.handle(key(pygame.K_UP))
    assert menu.row == 0

    field, _, choices, _ = OPTIONS[0]
    before = choice_index(field)
    menu.handle(key(pygame.K_RIGHT))
    assert choice_index(field) == (before + 1) % len(choices)
    menu.handle(key(pygame.K_LEFT))
    assert choice_index(field) == before


def test_clicking_a_chip_selects_that_value(menu, display):
    menu.handle(key(pygame.K_s))
    menu.draw(display)          # drawing is what lays the chips out
    assert menu.chips
    rect, field, value = next(c for c in menu.chips if getattr(SETTINGS, c[1]) != c[2])
    assert menu.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)) is True
    assert getattr(SETTINGS, field) == value


def test_clicking_outside_closes_it(menu, display):
    menu.handle(key(pygame.K_s))
    menu.draw(display)
    menu.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(4, 4), button=1))
    assert not menu.open


def test_demand_changes_how_fast_people_arrive(metro_map):
    counts = {}
    for name, demand in (("quiet", 0.5), ("rush", 1.8)):
        SETTINGS.reset()
        SETTINGS.demand = demand
        sim = Simulation(metro_map, spread_trains(metro_map, 4), seed=5)
        run_for(sim, 60)
        counts[name] = sim._next_id - 1
        for station in metro_map.stations.values():
            station.waiting = []
    assert counts["rush"] > counts["quiet"] * 1.5, counts


def test_patience_changes_when_people_give_up(metro_map):
    SETTINGS.patience = 40.0
    sim = Simulation(metro_map, spread_trains(metro_map, 4), seed=5)
    run_for(sim, 120)
    assert sim.gave_up > 0
    for station in metro_map.stations.values():
        for passenger in station.waiting:
            assert sim.clock - passenger.waited_since <= SETTINGS.patience + 2


def test_incidents_can_be_turned_off(metro_map):
    SETTINGS.incidents = False
    sim = Simulation(metro_map, spread_trains(metro_map, 4), seed=5)
    run_for(sim, 400)
    assert all(m.stalled == 0 for m in sim.metros)
    assert all(not m.fault for m in sim.metros)
    assert not any("stopped" in text for _, text in sim.log)


def test_crowd_setting_changes_how_many_are_drawn(world, sim, metro_map):
    run_for(sim, 240)
    busiest = max(metro_map.stations.values(), key=lambda s: len(s.waiting))
    SETTINGS.crowd = 24
    sparse = len(StationView(world, sim, busiest.name)._crowd())
    SETTINGS.crowd = 64
    packed = len(StationView(world, sim, busiest.name)._crowd())
    assert packed > sparse
    assert sparse <= 24 * 2 and packed <= 64 * 2


def test_entering_a_station_shows_the_entrance_loader(display, world, metro_map):
    name = "Alameda"
    serving = world.serving[name]
    assert len(serving) == 2
    tr = StationTransition(("station", name), serving[0].color, name, "walking down", serving)
    assert isinstance(tr, Transition)
    phases, swapped_in = [], None
    while True:
        if tr.wants_swap():
            tr.swapped = True
            swapped_in = tr.phase
        tr.draw(display)
        phases.append(tr.phase)
        if tr.update(FRAME):
            break
    assert set(phases) == {"close", "hold", "open"}
    assert swapped_in == "hold", "the scene must be swapped while the walls are shut"
    # Fully covered during the hold, so the swap is never visible.
    assert tr.phase == "open"


def test_leaving_a_station_uses_the_same_loader_running_upwards(display, world, metro_map):
    """Going out should look like coming in, not like a different game."""
    def frame(ascending):
        tr = StationTransition(("map",), (255, 214, 90), "Metro de Lisboa",
                               "back up to the network", metro_map.lines, ascending=ascending)
        tr.phase, tr.t = "hold", 0.5
        display.fill((0, 0, 0))
        tr.draw(display)
        band = pygame.Rect(display.get_width() // 2 - 200, display.get_height() // 2 - 130, 380, 70)
        return pygame.image.tostring(display.subsurface(band), "RGB")

    up, down = frame(True), frame(False)
    assert up != down, "the steps run the same way in and out"

    # Same furniture either way: walls fully shut, name plate and a chip per line.
    tr = StationTransition(("map",), (255, 214, 90), "Metro de Lisboa",
                           "back up to the network", metro_map.lines, ascending=True)
    assert (tr.CLOSE, tr.HOLD, tr.OPEN) == (StationTransition.CLOSE, StationTransition.HOLD, StationTransition.OPEN)
    assert len(tr.lines) == len(metro_map.lines) == 4
    tr.phase, tr.t = "hold", 0.5
    assert tr._coverage() == 1.0
