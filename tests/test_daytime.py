"""The day over the network: the hour, how busy it is, and which way the
city is travelling at it."""

from src.daytime import (
    DEMAND, MINUTES_PER_SECOND, PERIODS, PULL, START_HOUR, clock_text, demand_at,
    hour_of, period_at, pull_at,
)
from src.network import build_demo_map
from src.sim import Simulation
from tests.conftest import run_for

HOURS = [h / 10 for h in range(240)]


def at_hour(hour: float, seconds: float = 10.0) -> Simulation:
    """A network with nobody running it, left to fill for a few minutes of a
    given hour. No trains, so everyone who turns up stays where they are."""
    sim = Simulation(build_demo_map(), [], seed=3)
    sim.clock = (hour - START_HOUR) % 24 * 60 / MINUTES_PER_SECOND
    run_for(sim, seconds)
    return sim


def waiting(sim):
    return [p for station in sim.map.stations.values() for p in station.waiting]


def mean_centrality(sim, pick) -> float:
    people = waiting(sim)
    return sum(sim._centrality[pick(p)] for p in people) / len(people)


def test_the_day_opens_with_the_service():
    assert hour_of(0.0) == START_HOUR
    assert 6.0 <= START_HOUR <= 8.0, "the game should open on the way into the morning peak"


def test_a_day_is_a_day_long():
    day = 24 * 60 / MINUTES_PER_SECOND
    assert hour_of(day) == hour_of(0.0)
    assert hour_of(day / 2) == (START_HOUR + 12) % 24
    assert 0.0 <= hour_of(day * 3.7) < 24.0


def test_the_curves_stay_in_their_range():
    ceiling = max(v for _, v in DEMAND)
    for hour in HOURS:
        assert 0.0 < demand_at(hour) <= ceiling, hour
        assert -1.0 <= pull_at(hour) <= 1.0, hour


def test_the_curves_meet_at_midnight():
    """They are read by the hour and the hour wraps, so the ends have to
    agree or the network would lurch as the day turns over."""
    for curve, read in ((DEMAND, demand_at), (PULL, pull_at)):
        assert curve[0][0] == 0.0 and curve[-1][0] == 24.0
        assert read(0.0) == read(24.0) == curve[0][1]


def test_there_are_two_peaks_and_a_quiet_night():
    morning, evening, midday, night = demand_at(8.5), demand_at(18.5), demand_at(13.0), demand_at(3.0)
    assert morning > midday * 1.8 and evening > midday * 1.8
    assert night < midday / 5
    assert morning >= evening, "the morning peak is the sharper of the two"


def test_every_hour_of_the_day_has_a_name():
    names = {period_at(hour) for hour in HOURS}
    assert names == {p.name for p in PERIODS}
    assert all(period_at(hour) for hour in HOURS)
    assert period_at(8.0) == "morning peak" and period_at(3.0) == "night"


def test_the_clock_reads_as_a_clock():
    assert clock_text(7.0) == "07:00"
    assert clock_text(8.5) == "08:30"
    assert clock_text(0.0) == clock_text(24.0) == "00:00"
    assert clock_text(23.99) == "23:59"


def test_far_more_people_travel_at_the_peak_than_at_night():
    peak, night = at_hour(8.5), at_hour(3.0)
    assert len(waiting(peak)) > len(waiting(night)) * 10, (len(waiting(peak)), len(waiting(night)))


def test_the_morning_goes_into_the_city_and_the_evening_comes_back_out():
    """The tide is the point of the day: outskirts to middle and back."""
    morning, evening = at_hour(8.5), at_hour(18.5)
    assert mean_centrality(morning, lambda p: p.destination) > mean_centrality(evening, lambda p: p.destination)
    assert mean_centrality(morning, lambda p: p.origin) < mean_centrality(evening, lambda p: p.origin)


def test_the_tide_turns_rather_than_emptying_half_the_network():
    """Every station has to keep working at every hour, or the outskirts
    would be dead all evening."""
    for hour in (8.5, 18.5):
        sim = at_hour(hour, seconds=40)
        busy = {station.name for station in sim.map.stations.values() if station.waiting}
        assert len(busy) >= len(sim.map.stations) * 0.9, (hour, len(busy))
