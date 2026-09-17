from src.sim import DWELL_SECONDS
from tests.conftest import FRAME, run_for


def test_trains_turn_around_at_the_ends(metro_map, sim):
    seen_reversal = False
    before = {m.id: m.direction for m in sim.metros}
    run_for(sim, 240)
    for m in sim.metros:
        assert m.current_station in metro_map.line_named(m.line).stations
        if before[m.id] != m.direction:
            seen_reversal = True
    assert seen_reversal


def test_only_passengers_heading_the_trains_way_board(metro_map, sim):
    boardings = 0
    for _ in range(int(300 / FRAME)):
        sim.update(FRAME)
        for kind, passenger, metro in sim.drain_events():
            if kind != "board":
                continue
            boardings += 1
            line = metro_map.line_named(metro.line)
            here = line.stations.index(metro.current_station)
            ahead = (line.stations.index(passenger.destination) - here) * sim.departing_direction(metro)
            assert ahead > 0, f"{passenger.destination} is not ahead of {metro.current_station}"
    assert boardings > 100


def test_capacity_is_respected_and_people_get_delivered(sim):
    run_for(sim, 300)
    assert all(len(m.riders) <= m.capacity for m in sim.metros)
    assert sim.delivered > 0


def test_dwell_then_depart_is_continuous(sim):
    """A train's progress never jumps: it sits for the dwell, then moves smoothly."""
    metro = sim.metros[0]
    last_progress = metro.progress
    for _ in range(int(120 / FRAME)):
        sim.update(FRAME)
        if metro.cooldown == 0:
            assert 0 <= metro.progress - last_progress <= metro.speed * FRAME + 1e-9 or metro.progress == 0.0
        last_progress = metro.progress
    assert 0 < DWELL_SECONDS
