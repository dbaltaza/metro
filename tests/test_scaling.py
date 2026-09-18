"""Regressions for the bugs that only showed up after a long session:
unbounded platform queues, frame-long boarding scans, a station view that
drew thousands of people, and caches keyed on an ever-growing passenger id.
"""

import time

import pygame
import pytest

from src import sprites
from src.metro import Metro
from src.passenger import Passenger
from src.route import World
from src.sim import PATIENCE_SECONDS, Simulation, spread_trains
from src.station_layout import CROWD_LIMIT
from src.station_view import StationView
from tests.conftest import FRAME, run_for


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


def test_the_network_empties_overnight_and_does_not_ratchet_up(metro_map):
    """São Sebastião used to reach thousands of people and never come down,
    because MAX_WAITING only stopped new arrivals being invented.

    With a day over it the queue is supposed to rise into the peaks, so the
    question is no longer whether it grows: it is whether the small hours
    clear it out, and whether the same hour a day later is any worse."""
    sim = Simulation(metro_map, spread_trains(metro_map, 4), seed=7)
    marks = {}
    for label, target in (("afternoon", 480), ("dawn", 1320), ("afternoon again", 1920)):
        while sim.clock < target:
            sim.update(FRAME)
            sim.drain_events()
        marks[label] = max(len(s.waiting) for s in metro_map.stations.values())
    assert marks["dawn"] < marks["afternoon"] / 3, f"the night never cleared: {marks}"
    assert marks["afternoon again"] <= marks["afternoon"] * 2, f"climbing day on day: {marks}"
    assert sim.gave_up > 0, "nobody ever gives up, so nothing bounds the queue"
    # Everyone left waiting is within the patience window.
    for station in metro_map.stations.values():
        for passenger in station.waiting:
            assert sim.clock - passenger.waited_since <= PATIENCE_SECONDS + 2


def test_boarding_removes_only_the_people_who_boarded(metro_map):
    """Passenger is a pydantic model, so `p not in boarding` compares by value.
    Two riders with identical fields would take each other off the platform."""
    sim = Simulation(metro_map, [], seed=1)
    line = metro_map.lines[0]
    here, ahead = line.stations[0], line.stations[1]
    station = metro_map.stations[here]
    twin_a = Passenger(id=1, origin=here, destination=ahead, legs=[(line.name, ahead)], created=0.0, waited_since=0.0)
    twin_b = Passenger(id=1, origin=here, destination=ahead, legs=[(line.name, ahead)], created=0.0, waited_since=0.0)
    assert twin_a == twin_b and twin_a is not twin_b
    station.waiting = [twin_a, twin_b]

    metro = spread_trains(metro_map, 1)[0]
    metro.capacity = 1
    sim.metros = [metro]
    sim._plan(metro)
    sim._board(metro)

    assert len(metro.riders) == 1
    assert len(station.waiting) == 1, "the identical twin was removed too"
    assert station.waiting[0] is twin_b


def test_boarding_a_busy_platform_does_not_cost_a_frame(metro_map):
    """Run until a train is actually standing at a packed platform, rather
    than hoping one is at the busiest station on the frame we stop at."""
    sim = Simulation(metro_map, spread_trains(metro_map, 4), seed=7)
    metro = None
    while metro is None and sim.clock < 600:
        sim.update(FRAME)
        sim.drain_events()
        for candidate in sim.metros:
            if candidate.cooldown > 0 and len(metro_map.stations[candidate.current_station].waiting) > 100:
                metro = candidate
                break
    assert metro is not None, "no train ever stood at a platform with a hundred people on it"
    start = time.perf_counter()
    sim._board(metro)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 16.0, f"_board took {elapsed:.0f} ms, a dropped frame"


def test_station_view_draws_a_plateful_of_people_not_the_whole_queue(world, sim, metro_map):
    run_for(sim, 240)
    busiest = max(metro_map.stations.values(), key=lambda s: len(s.waiting))
    view = StationView(world, sim, busiest.name)
    run_for(sim, 2, view)
    per_platform = {-1: 0, 1: 0}
    for _, direction in view._crowd():
        per_platform[direction] += 1
    # A platform is 640 world pixels of floor: a hundred people cannot stand
    # on it, however many are queued.
    assert max(per_platform.values()) <= 60
    assert max(per_platform.values()) <= CROWD_LIMIT
    assert len(view.people) <= 120
    # The departures board still reports the real number, not the drawn one.
    queued = len(view._waiting_here())
    assert queued > len(view._crowd()), "platform not busy enough to be a fair test"
    counted = sum(1 for _, d in view._waiting_here() if d == -1)
    assert counted >= per_platform[-1]


def test_station_view_stays_fast_on_a_crowded_platform(display, world, sim, metro_map):
    run_for(sim, 400)
    busiest = max(metro_map.stations.values(), key=lambda s: len(s.waiting))
    assert len(busiest.waiting) > 300, "not a crowded enough platform to be a fair test"
    view = StationView(world, sim, busiest.name)
    for _ in range(20):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        view.draw(display, False, 1.0)
    start = time.perf_counter()
    for _ in range(20):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        view.draw(display, False, 1.0)
    per_frame = (time.perf_counter() - start) / 20 * 1000
    # Well inside a 16 ms frame, with the rest of the game still to draw.
    assert per_frame < 8.0, f"{per_frame:.1f} ms per frame on a busy platform"


def test_character_cache_does_not_grow_with_passenger_ids():
    """Ids climb into the tens of thousands; the sprite cache used to key on
    them, blow past its limit and wipe itself wholesale every few frames."""
    pygame.init()
    sprites._char_cache.clear()
    for pid in range(50_000, 50_000 + 4_000):
        sprites.character(pid, 1, 0, "stand")
    assert len(sprites._char_cache) <= sprites.LOOK_POOL
    assert len(sprites._looks) <= sprites.LOOK_POOL + 1
    # Staff keep their own uniform look, separate from passengers.
    assert sprites.look_key(-1) == sprites.look_key(-99) == -1
    assert sprites.look_for(-1).shirt == sprites.STAFF_BLUE


def test_evicting_a_full_cache_keeps_most_of_it():
    cache = {i: i for i in range(100)}
    sprites._evict(cache, 200)
    assert len(cache) == 100, "evicted below the limit"
    sprites._evict(cache, 50)
    assert 50 <= len(cache) < 100, "a full wipe instead of an eviction"


def test_a_train_on_one_line_does_not_block_a_platform_on_another(metro_map):
    """Different lines have different platforms. add_train used to treat any
    standing train as occupying the station for every line."""
    interchange = next(
        s for s in metro_map.stations
        if len([l for l in metro_map.lines if s in l.stations]) > 1
    )
    blue, red = [l for l in metro_map.lines if interchange in l.stations][:2]
    sim = Simulation(metro_map, [], seed=1)
    # Fill every platform on the red line except the interchange.
    for station in red.stations:
        if station == interchange:
            continue
        for direction in (1, -1):
            index = red.stations.index(station)
            if 0 <= index + direction < len(red.stations):
                sim.metros.append(Metro(id=len(sim.metros) + 1, line=red.name,
                                        current_station=station, direction=direction))
    # Blue trains stand at the interchange in both directions, on blue's own
    # platforms. Red's platforms there are the only ones left free.
    for direction in (1, -1):
        sim.metros.append(Metro(id=900 + direction, line=blue.name,
                                current_station=interchange, direction=direction))
    added = sim.add_train(red.name)
    assert added is not None, "the other line's trains blocked the platform"
    assert added.current_station == interchange


def test_stepping_off_a_train_opens_that_line_at_the_station(world, metro_map, sim):
    interchange = next(
        s for s in metro_map.stations
        if len([l for l in metro_map.lines if s in l.stations]) > 1
    )
    serving = [l for l in metro_map.lines if interchange in l.stations]
    second = serving[1]
    view = StationView(world, sim, interchange, second.name)
    assert view.line is second, "opened on the wrong line's platform"
    # Unknown or missing line falls back to the first one, as before.
    assert StationView(world, sim, interchange).line is serving[0]
    assert StationView(world, sim, interchange, "Linha Fantasma").line is serving[0]
