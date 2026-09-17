from src.sim import Simulation, spread_trains
from tests.conftest import FRAME, run_for


def test_fleet_lever_adds_and_removes_trains(metro_map, sim):
    run_for(sim, 20)
    before = len(sim.trains_on("Linha Verde"))
    added = sim.add_train("Linha Verde")
    assert added is not None and len(sim.trains_on("Linha Verde")) == before + 1
    # The new train stands on a free platform: nobody shares its spot.
    standing = [(m.current_station, sim.departing_direction(m)) for m in sim.metros if m.progress == 0]
    assert len(standing) == len(set(standing))

    removed = sim.remove_train("Linha Verde")
    assert removed is not None
    run_for(sim, 30)  # a retiring train leaves at its next stop
    assert len(sim.trains_on("Linha Verde")) == before
    assert removed not in sim.metros
    assert any("service" in text for _, text in sim.log)


def test_removed_train_returns_its_riders_to_the_platform(metro_map):
    sim = Simulation(metro_map, spread_trains(metro_map, 2), seed=5)
    run_for(sim, 60)
    metro = max(sim.metros, key=lambda m: len(m.riders))
    riders = list(metro.riders)
    metro.retiring = True
    for _ in range(int(30 / FRAME)):
        sim.update(FRAME)
        if metro not in sim.metros:
            break
    assert metro not in sim.metros
    station = sim.map.stations[metro.current_station]
    assert all(p in station.waiting or p.destination == metro.current_station for p in riders)


def test_stalls_stop_a_train_and_then_clear(metro_map, sim):
    sim._next_incident = 0.1
    stalled = None
    for _ in range(int(60 / FRAME)):
        sim.update(FRAME)
        stalled = next((m for m in sim.metros if m.stalled > 0), None)
        if stalled:
            break
    assert stalled is not None
    progress = stalled.progress
    run_for(sim, 2)
    assert stalled.progress == progress, "a stalled train must not move"
    run_for(sim, 20)
    assert stalled.stalled == 0 and stalled.progress != progress or stalled.current_station != stalled.destination
    assert any("stalled" in text for _, text in sim.log)


def test_score_is_computed(sim):
    run_for(sim, 120)
    assert sim.boardings > 0
    assert 0 < sim.average_wait() < 300
    assert sim.delivered_per_minute() > 0
