"""The books: what the service earns, what the fleet costs, and the balance."""

import pytest

from src.route import money
from src.sim import (
    COST_PER_HOUR, FARE, GIVE_UP_COST, OPENING_BALANCE, PUT_INTO_SERVICE,
    Simulation, spread_trains,
)
from tests.conftest import FRAME, run_for


def test_you_start_with_something_to_run_it_on(sim):
    assert sim.balance == OPENING_BALANCE
    assert sim.earned == 0 and sim.run_cost == 0 and sim.lost == 0


def test_every_journey_finished_is_a_fare(sim):
    run_for(sim, 120)
    assert sim.delivered > 0
    assert sim.earned == pytest.approx(sim.delivered * FARE)


def test_a_train_costs_by_the_hour_whether_it_is_busy_or_not(metro_map):
    """Sixty seconds of clock is an hour of the day, and every train in
    service is charged for it."""
    sim = Simulation(metro_map, spread_trains(metro_map, 2), seed=3)
    trains = len(sim.metros)
    run_for(sim, 60)
    assert sim.run_cost == pytest.approx(trains * COST_PER_HOUR, rel=0.02)


def test_somebody_walking_out_costs_you(metro_map):
    sim = Simulation(metro_map, [], seed=3)      # no trains: everyone gives up
    from src.settings import SETTINGS
    SETTINGS.patience = 30.0
    run_for(sim, 120)
    assert sim.gave_up > 0
    assert sim.lost == pytest.approx(sim.gave_up * GIVE_UP_COST)


def test_the_balance_is_what_came_in_less_what_went_out(sim):
    run_for(sim, 200)
    assert sim.balance == pytest.approx(OPENING_BALANCE + sim.earned - sim.run_cost - sim.lost)


def test_putting_a_train_into_service_costs_a_one_off(sim):
    before = sim.run_cost
    added = sim.add_train("Linha Verde")
    assert added is not None
    assert sim.run_cost == pytest.approx(before + PUT_INTO_SERVICE)


def test_you_cannot_put_a_train_into_service_with_no_money(sim):
    sim.lost = OPENING_BALANCE          # spent it all
    assert not sim.can_afford_a_train()
    before = len(sim.metros)
    assert sim.add_train("Linha Verde") is None
    assert len(sim.metros) == before, "a train appeared that nobody paid for"


def test_taking_a_train_out_is_free(sim):
    before = sim.run_cost
    assert sim.remove_train("Linha Verde") is not None
    assert sim.run_cost == before


def test_running_more_trains_than_the_fares_carry_loses_money(metro_map):
    """The point of the books: a fleet has a best size, and it is not the
    biggest one you can put on the rails."""
    profits = {}
    for per_line in (4, 6, 14):
        sim = Simulation(build := metro_map.model_copy(deep=True), spread_trains(build, per_line), seed=7)
        while sim.clock < 1200:
            sim.update(FRAME)
            sim.drain_events()
        day = sim.take_finished_day()
        profits[per_line * 4] = day.profit
    assert profits[24] > profits[16], "too thin a service should not be the best you can do"
    assert profits[24] > profits[56], "nor should putting every train you own on the rails"


def test_the_day_is_billed_on_its_own(metro_map):
    sim = Simulation(metro_map, spread_trains(metro_map, 3), seed=7)
    days = []
    while sim.clock < 2700:
        sim.update(FRAME)
        sim.drain_events()
        done = sim.take_finished_day()
        if done is not None:
            days.append(done)
    assert len(days) == 2
    for day in days:
        assert day.earned > 0 and day.spent > 0
        assert day.profit == pytest.approx(day.earned - day.spent)
    assert sum(d.earned for d in days) <= sim.earned + 1e-6
    assert days[-1].balance == pytest.approx(sim.balance, rel=0.05)


def test_money_reads_like_money():
    assert money(0) == "€0"
    assert money(1234.6) == "€1,235"
    assert money(-980) == "-€980"
