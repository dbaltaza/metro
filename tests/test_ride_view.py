import pygame
import pytest

from src.ride_view import DOOR_XS, RideView
from src.route import World
from src.sim import DWELL_SECONDS
from src.station_view import StationView
from tests.conftest import FRAME, run_for


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


def _yellow_train(sim):
    return next(m for m in sim.metros if m.line == "Linha Amarela")


def test_boarding_a_dwelling_train_from_the_platform(world, sim):
    view = StationView(world, sim, "Campo Pequeno")
    for _ in range(int(600 / FRAME)):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        train = next((m for m in sim.metros if m.line == view.line.name and m.current_station == view.name and m.cooldown > 0), None)
        if train:
            view.hover = ("train", train, (0, 0))
            result = view.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=1))
            assert result == ("ride", train)
            return
    pytest.fail("no train stopped at the platform")


def test_ride_follows_the_train_and_renders(display, world, sim):
    run_for(sim, 30)
    train = _yellow_train(sim)
    ride = RideView(world, sim, train)
    start = train.current_station
    stations_seen = {start}
    for _ in range(int(120 / FRAME)):
        sim.update(FRAME)
        assert ride.update(FRAME, sim.drain_events()) is None
        stations_seen.add(train.current_station)
    assert len(stations_seen) >= 3
    ride.draw(display, False, 1.0)
    assert ride.world_surface.get_bitsize() == 24
    # Riders in this car all have a seat or standing spot, nobody twice.
    spots = list(ride.seats.values())
    assert len(spots) == len(set(spots))
    assert set(ride.seats) <= {p.id for p in train.riders}


def test_you_can_only_get_off_while_the_doors_are_open(world, sim):
    run_for(sim, 10)
    train = _yellow_train(sim)
    ride = RideView(world, sim, train)
    press_e = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, mod=0, unicode="e", scancode=0)
    for _ in range(int(120 / FRAME)):
        sim.update(FRAME)
        ride.update(FRAME, sim.drain_events())
        result = ride.handle(press_e)
        if train.cooldown > 0:
            assert result == ("station", train.current_station)
            return
        assert result is None
    pytest.fail("train never stopped")


def test_ride_ends_at_the_platform_if_the_train_retires(world, sim):
    run_for(sim, 10)
    train = _yellow_train(sim)
    ride = RideView(world, sim, train)
    train.retiring = True
    for _ in range(int(60 / FRAME)):
        sim.update(FRAME)
        forced = ride.update(FRAME, sim.drain_events())
        if forced:
            assert forced == ("station", train.current_station)
            assert train not in sim.metros
            return
    pytest.fail("retiring train never left service")


def test_outside_scrolls_a_full_segment_between_stops(world, sim):
    run_for(sim, 10)
    train = _yellow_train(sim)
    ride = RideView(world, sim, train)
    seen_zero = seen_far = False
    for _ in range(int(60 / FRAME)):
        sim.update(FRAME)
        ride.update(FRAME, sim.drain_events())
        d = ride._distance()
        seen_zero = seen_zero or d == 0.0
        seen_far = seen_far or d > 1000
        assert 0.0 <= d <= 1500.0
    assert seen_zero and seen_far
    assert DWELL_SECONDS > 0


def test_people_getting_off_walk_out_through_the_door(display, world, sim):
    run_for(sim, 10)
    train = _yellow_train(sim)
    ride = RideView(world, sim, train)
    for _ in range(int(180 / FRAME)):
        sim.update(FRAME)
        events = sim.drain_events()
        ride.update(FRAME, events)
        leavers = [p for kind, p, m in events if kind == "alight" and m is train]
        if not leavers:
            continue
        walking = {w["passenger"].id: w for w in ride.walkers if w["fade"]}
        assert all(p.id in walking for p in leavers), "someone got off without walking out"
        w = walking[leavers[0].id]
        assert w["end"][0] in DOOR_XS
        # They are still drawn (standing up, then walking) until they are through the door.
        while ride.time < w["t1"] + 0.1:
            ride.draw(display, False, 1.0)
            ride.update(FRAME, [])
            assert w in ride.walkers
        return
    pytest.fail("nobody got off the train")
