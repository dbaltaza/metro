import pytest

from src.route import World
from src.sim import DWELL_SECONDS
from src.station_layout import DOOR_CLOSE_SECONDS, PLATFORM_1, PLATFORM_2
from src.station_view import StationView
from tests.conftest import FRAME, run_for


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


def test_countdown_never_jumps(world, sim):
    """The departures estimate shrinks by exactly one frame per frame, except
    when a train has just served this platform and the estimate resets."""
    view = StationView(world, sim, "Campo Pequeno")
    previous = {}
    worst = 0.0
    for _ in range(int(200 / FRAME)):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        for metro in sim.metros:
            if metro.line != view.line.name:
                continue
            for direction in (-1, 1):
                eta = view._eta(metro, direction)
                key = (metro.id, direction)
                if eta is not None and previous.get(key) is not None and not (previous[key] == 0 and eta > 0):
                    worst = max(worst, abs((eta - previous[key]) + FRAME))
                previous[key] = eta
    assert worst <= FRAME + 1e-6


def test_boarders_are_inside_before_doors_close(world, sim):
    view = StationView(world, sim, "Campo Pequeno")
    seen, late, total = set(), 0, 0
    for _ in range(int(400 / FRAME)):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        for walker in view.walkers:
            if walker["kind"] != "board" or id(walker) in seen:
                continue
            seen.add(id(walker))
            total += 1
            arrival = view.arrivals.get(walker["train"])
            if arrival is not None and walker["end"] > arrival + DWELL_SECONDS - DOOR_CLOSE_SECONDS + 0.01:
                late += 1
    assert total > 50
    assert late == 0


def test_boarders_never_cross_to_the_other_track(world, sim):
    view = StationView(world, sim, "Campo Pequeno")
    checked = 0
    for _ in range(int(300 / FRAME)):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        for walker in view.walkers:
            if walker["kind"] != "board" or walker.get("_checked"):
                continue
            walker["_checked"] = True
            checked += 1
            start_y = walker["segments"][0][1][1]
            end_y = walker["segments"][-1][2][1]
            on_platform_1 = PLATFORM_1.top <= start_y <= PLATFORM_1.bottom
            to_track_a = end_y < PLATFORM_2.top - 40
            assert on_platform_1 == to_track_a
    assert checked > 50


def test_terminus_train_boards_from_its_departure_side(world, sim):
    view = StationView(world, sim, "Odivelas")
    for _ in range(int(600 / FRAME)):
        sim.update(FRAME)
        events = sim.drain_events()
        view.update(FRAME, events)
        boards = [m for k, _, m in events if k == "board" and m.current_station == "Odivelas"]
        if boards:
            assert view._side(boards[0]) == 1
            assert "BOARDING" in view._platform_status(1)
            return
    pytest.fail("no train boarded at the terminus")


def test_scenes_render_without_stray_alpha(display, world, sim):
    """Sprites blitted onto the world must not leave alpha-zero pixels, which
    corrupt later blends on a real display. The world surfaces are 24-bit."""
    from src.route import MapScene
    run_for(sim, 30)
    scene = MapScene(world, sim)
    scene.draw(display, False)
    assert world.world.get_bitsize() == 24
    view = StationView(world, sim, "Saldanha")
    run_for(sim, 5, view)
    view.draw(display, False)
    assert view.world_surface.get_bitsize() == 24
