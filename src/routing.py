"""Journey planning over the network.

A journey is a list of legs, each one "ride this line and get off here".
Planning runs a shortest-path search over (station, line) states so that a
change of line costs a few stops' worth of time, which is how people actually
choose: they accept a slightly longer ride to avoid a transfer.
"""

import heapq

from src.network import Map

Leg = tuple[str, str]  # (line name, station to get off at)

TRANSFER_COST = 3.0
HOP_COST = 1.0


def plan(metro_map: Map, origin: str, destination: str) -> list[Leg]:
    """Legs from origin to destination, or an empty list if they are the same
    station or no line connects them."""
    if origin == destination:
        return []

    # Adjacency along every line: station -> [(neighbour, line name)]
    neighbours: dict[str, list[tuple[str, str]]] = {}
    for line in metro_map.lines:
        for a, b in zip(line.stations, line.stations[1:]):
            neighbours.setdefault(a, []).append((b, line.name))
            neighbours.setdefault(b, []).append((a, line.name))

    # State = (station, line we are currently riding). Starting with no line
    # lets the first boarding be free of a transfer penalty.
    start = (origin, "")
    best: dict[tuple[str, str], float] = {start: 0.0}
    came_from: dict[tuple[str, str], tuple[str, str]] = {}
    frontier: list[tuple[float, int, tuple[str, str]]] = [(0.0, 0, start)]
    counter = 1
    goal = None
    while frontier:
        cost, _, state = heapq.heappop(frontier)
        if cost > best.get(state, float("inf")):
            continue
        station, riding = state
        if station == destination:
            goal = state
            break
        for other, line_name in neighbours.get(station, []):
            step = HOP_COST + (TRANSFER_COST if riding and line_name != riding else 0.0)
            nxt = (other, line_name)
            new_cost = cost + step
            if new_cost < best.get(nxt, float("inf")):
                best[nxt] = new_cost
                came_from[nxt] = state
                heapq.heappush(frontier, (new_cost, counter, nxt))
                counter += 1
    if goal is None:
        return []

    # Walk back to the origin, then compress the state path into legs.
    states = [goal]
    while states[-1] in came_from:
        states.append(came_from[states[-1]])
    states.reverse()
    legs: list[Leg] = []
    for (_, prev_line), (station, line_name) in zip(states, states[1:]):
        if legs and legs[-1][0] == line_name:
            legs[-1] = (line_name, station)
        else:
            legs.append((line_name, station))
    return legs
