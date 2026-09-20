"""Who is travelling, and what difference it makes."""

import collections

from src.daytime import START_HOUR, clock_text, hour_of
from src.network import build_demo_map
from src.settings import SETTINGS
from src.sim import KINDS, PATIENCE_BY_KIND, VISITOR_STOPS, Simulation
from tests.conftest import run_for


def at_hour(hour: float, seconds: float = 20.0) -> Simulation:
    sim = Simulation(build_demo_map(), [], seed=3)
    sim.clock = (hour - START_HOUR) % 24 * 60
    run_for(sim, seconds)
    return sim


def travellers(sim):
    return [p for station in sim.map.stations.values() for p in station.waiting]


def mix_at(hour: float) -> collections.Counter:
    return collections.Counter(p.kind for p in travellers(at_hour(hour)))


def test_everybody_is_travelling_for_some_reason(sim):
    run_for(sim, 90)
    people = [p for s in sim.map.stations.values() for p in s.waiting]
    assert people
    assert all(p.kind in KINDS for p in people)


def test_the_peak_is_commuters_and_the_middle_of_the_day_is_visitors():
    peak, midday = mix_at(8.5), mix_at(13.0)
    assert peak["commuter"] / sum(peak.values()) > 0.5
    assert midday["visitor"] > peak["visitor"], (peak, midday)
    assert midday["visitor"] / sum(midday.values()) > 0.25


def test_the_small_hours_belong_to_people_going_to_work():
    night = mix_at(2.0)
    assert night["shift worker"] / sum(night.values()) > 0.4, night
    assert night["visitor"] / sum(night.values()) < 0.25, night
    assert clock_text(hour_of(0.0)) == "07:00", "and the day still opens at seven"


def test_a_visitor_is_mostly_going_somewhere_worth_visiting():
    visitors = [p for p in travellers(at_hour(13.0, 40.0)) if p.kind == "visitor"]
    assert len(visitors) > 30, "not enough of them to say anything"
    going = sum(1 for p in visitors if p.destination in VISITOR_STOPS)
    assert going / len(visitors) > 0.55, "visitors should favour the places people visit"
    assert going < len(visitors), "but not every one of them"


def test_a_commuter_gives_up_before_a_visitor_does():
    assert PATIENCE_BY_KIND["commuter"] < 1.0 < PATIENCE_BY_KIND["visitor"]
    assert set(PATIENCE_BY_KIND) == set(KINDS), "a kind with no patience set would fall back silently"

    SETTINGS.patience = 60.0
    sim = Simulation(build_demo_map(), [], seed=3)   # no trains, so everyone waits
    run_for(sim, 200)
    waited = {kind: max((sim.clock - p.waited_since for p in travellers(sim) if p.kind == kind), default=0.0)
              for kind in KINDS}
    commuter_limit = SETTINGS.patience * PATIENCE_BY_KIND["commuter"]
    assert waited["commuter"] <= commuter_limit + 2, waited
    assert waited["visitor"] > commuter_limit + 2, "a visitor outlasts a commuter's limit"
    assert waited["visitor"] <= SETTINGS.patience * PATIENCE_BY_KIND["visitor"] + 2


def test_who_is_travelling_does_not_change_what_a_journey_is(sim):
    """A kind is a reason to travel, not a different kind of passenger: the
    routing, the boarding and the books all treat them the same."""
    run_for(sim, 120)
    riders = [p for m in sim.metros for p in m.riders]
    assert riders
    assert {p.kind for p in riders} & set(KINDS)
    for passenger in riders:
        assert passenger.legs, "everyone aboard is on their way somewhere"
