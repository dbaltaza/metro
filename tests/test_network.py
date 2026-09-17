import pytest

from src.error import MetroError, StationError
from src.network import Line, Map, Station


def test_demo_map_is_consistent(metro_map):
    for line in metro_map.lines:
        for name in line.stations:
            assert name in metro_map.stations, f"{line.name} references unknown {name}"
    interchanges = [n for n in metro_map.stations if len(metro_map.lines_at(n)) > 1]
    assert sorted(interchanges) == sorted([
        "Alameda", "Baixa-Chiado", "Campo Grande", "Marquês de Pombal", "Saldanha", "São Sebastião",
    ])


def test_next_station_walks_the_line_and_stops_at_the_end(metro_map):
    assert metro_map.next_station("Linha Amarela", "Saldanha") == "Picoas"
    assert metro_map.next_station("Linha Amarela", "Rato") is None


def test_lookups_fail_loudly(metro_map):
    with pytest.raises(MetroError):
        metro_map.next_station("Linha Roxa", "Saldanha")
    with pytest.raises(StationError):
        metro_map.next_station("Linha Amarela", "Aeroporto")


def test_add_line_rejects_unknown_stations():
    m = Map()
    m.add_station(Station(name="a", x=0, y=0))
    with pytest.raises(StationError):
        m.add_line(Line(name="x", color=(1, 2, 3), stations=["a", "ghost"]))


def test_station_coordinates_are_validated():
    with pytest.raises(Exception):
        Station(name="bad", x=5000, y=0)


def test_map_loads_from_json_and_round_trips(tmp_path, metro_map):
    import json
    from src.network import load_map
    data = {
        "stations": [{"name": s.name, "x": s.x, "y": s.y} for s in metro_map.stations.values()],
        "lines": [{"name": l.name, "color": list(l.color), "stations": l.stations} for l in metro_map.lines],
    }
    path = tmp_path / "city.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    again = load_map(path)
    assert list(again.stations) == list(metro_map.stations)
    assert [l.stations for l in again.lines] == [l.stations for l in metro_map.lines]
    assert again.lines[0].color == metro_map.lines[0].color
