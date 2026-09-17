from src.metro import Metro
from src.sim import Simulation
from tests.conftest import FRAME


def _sides(sim, metro):
    return sim.departing_direction(metro)


def test_trains_never_share_a_segment_or_a_platform(metro_map):
    """Six trains starting on adjacent stations of the yellow line: the ones
    behind must wait for the platform ahead to clear, and nobody may overlap."""
    line = metro_map.line_named("Linha Amarela")
    metros = [
        Metro(id=i + 1, line=line.name, current_station=line.stations[i], direction=1)
        for i in range(6)
    ]
    sim = Simulation(metro_map, metros, seed=3)
    held_seen = False
    for _ in range(int(600 / FRAME)):
        sim.update(FRAME)
        held_seen = held_seen or any(m.held for m in metros)
        moving = [m for m in metros if m.cooldown == 0 and m.progress > 0]
        segments = [(m.current_station, m.destination) for m in moving]
        assert len(segments) == len(set(segments)), f"two trains on one segment: {segments}"
        standing = [(m.current_station, _sides(sim, m)) for m in metros if m.progress == 0]
        assert len(standing) == len(set(standing)), f"two trains on one platform: {standing}"
    assert held_seen, "trains on adjacent stations must hold for the platform ahead"


def test_a_held_train_does_not_deadlock(metro_map, sim):
    """The regular fleet keeps moving: every train departs its station eventually."""
    departures = {m.id: 0 for m in sim.metros}
    last_station = {m.id: m.current_station for m in sim.metros}
    for _ in range(int(400 / FRAME)):
        sim.update(FRAME)
        for m in sim.metros:
            if m.current_station != last_station[m.id]:
                departures[m.id] += 1
                last_station[m.id] = m.current_station
    assert all(count > 5 for count in departures.values()), departures
