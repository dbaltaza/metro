from src.routing import plan
from tests.conftest import FRAME


def test_same_line_is_one_leg(metro_map):
    assert plan(metro_map, "Odivelas", "Rato") == [("Linha Amarela", "Rato")]


def test_changing_lines_goes_through_an_interchange(metro_map):
    legs = plan(metro_map, "Reboleira", "Aeroporto")
    assert [line for line, _ in legs] == ["Linha Azul", "Linha Vermelha"]
    assert legs[0][1] == "São Sebastião"
    assert legs[-1][1] == "Aeroporto"


def test_every_pair_of_stations_is_reachable(metro_map):
    names = list(metro_map.stations)
    for origin in names:
        for destination in names:
            legs = plan(metro_map, origin, destination)
            if origin == destination:
                assert legs == []
            else:
                assert legs and legs[-1][1] == destination
                assert len(legs) <= 3


def test_legs_are_consistent_with_the_lines(metro_map):
    legs = plan(metro_map, "Telheiras", "Santa Apolónia")
    for line_name, stop in legs:
        assert stop in metro_map.line_named(line_name).stations


def test_passengers_change_lines_and_still_arrive(metro_map, sim):
    for _ in range(int(400 / FRAME)):
        sim.update(FRAME)
        for kind, passenger, metro in sim.drain_events():
            if kind == "alight" and passenger.legs:
                # A transfer: the next line must actually stop where they got off.
                assert metro.current_station in metro_map.line_named(passenger.next_line).stations
                assert passenger.next_line != metro.line
    assert sim.transfers > 0
    assert sim.delivered > sim.transfers
