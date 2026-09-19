import pytest

from src.sim import FAULTS, FUMBLE_SECONDS, RELEASE_SECONDS, Simulation, spread_trains
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


def stall_one(sim):
    """Bring on an incident and hand back the train it happened to."""
    sim._next_incident = 0.1
    for _ in range(int(60 / FRAME)):
        sim.update(FRAME)
        stalled = next((m for m in sim.metros if m.stalled > 0), None)
        if stalled:
            return stalled
    raise AssertionError("no train ever stalled")


def test_a_stopped_train_waits_for_the_controller(metro_map, sim):
    """It used to clear itself in under twenty seconds. Now it sits there
    with a fault on it until somebody goes and deals with it."""
    stalled = stall_one(sim)
    assert stalled.fault in FAULTS
    progress = stalled.progress
    run_for(sim, 20)
    assert stalled.stalled > 0, "it cleared itself, so there was nothing to attend to"
    assert stalled.progress == progress, "a stopped train must not move"
    assert any("stopped" in text for _, text in sim.log)


def test_the_controller_can_release_it(metro_map, sim):
    stalled = stall_one(sim)
    progress = stalled.progress
    assert sim.release(stalled) is True
    assert stalled.fault == "" and sim.released == 1
    assert stalled.stalled <= RELEASE_SECONDS
    run_for(sim, 3)
    assert stalled.stalled == 0
    assert stalled.progress != progress or stalled.current_station != stalled.destination
    assert any("released" in text for _, text in sim.log)


def test_releasing_a_train_with_nothing_wrong_does_nothing(sim):
    fine = sim.metros[0]
    assert fine.stalled == 0
    assert sim.release(fine) is False
    assert sim.released == 0


def test_the_wrong_control_costs_a_few_seconds(metro_map, sim):
    stalled = stall_one(sim)
    before = stalled.stalled
    sim.fumble(stalled)
    assert stalled.stalled == pytest.approx(before + FUMBLE_SECONDS)
    assert stalled.fault, "fumbling does not fix it either"


def test_score_is_computed(sim):
    run_for(sim, 120)
    assert sim.boardings > 0
    assert 0 < sim.average_wait() < 300
    assert sim.delivered_per_minute() > 0


def test_step_transition_zooms_through_the_door_and_swaps_in_the_dark(display):
    from src.route import StepTransition, Transition

    tr = StepTransition(("ride", None), (240, 178, 24), "Train #1", "mind the gap", (300, 400), lambda scene: (scene, 20))
    assert isinstance(tr, Transition)
    display.fill((90, 120, 150))
    swapped_at = None
    t = 0.0
    while True:
        done = tr.update(1 / 60)
        t += 1 / 60
        if tr.wants_swap():
            tr.swapped = True
            tr.scene = 640
            swapped_at = tr.phase
        tr.draw(display)
        if tr.phase == "hold":
            # The doors are shut while the scene is swapped underneath.
            assert display.get_at((100, 30))[:3] == tr.LEAF
            assert display.get_at((640, 30))[:3] == tr.RUBBER
        if done:
            break
    assert swapped_at == "hold"
    assert tr._resolved_focus_in() == (640, 20)
    assert abs(t - (tr.CLOSE + tr.HOLD + tr.OPEN)) < 0.05
