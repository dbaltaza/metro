"""Regenerates the README screenshots in docs/.

    .venv/bin/python tools/screenshots.py

Runs on the real display driver in a hidden window, because the dummy one
has hidden alpha bugs from us before.
"""

import os
import sys

import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.network import build_demo_map          # noqa: E402
from src.ride_view import RideView              # noqa: E402
from src.route import WINDOW_H, WINDOW_W, MapScene, World   # noqa: E402
from src.sim import Simulation, spread_trains   # noqa: E402
from src.station_view import StationView        # noqa: E402

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
FRAME = 1 / 60


def settle(sim, seconds, view=None):
    for _ in range(int(seconds / FRAME)):
        sim.update(FRAME)
        events = sim.drain_events()
        if view is not None:
            view.update(FRAME, events)


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.HIDDEN)
    metro_map = build_demo_map()
    sim = Simulation(metro_map, spread_trains(metro_map, 4), seed=7)
    world = World(metro_map)
    settle(sim, 150)

    MapScene(world, sim).draw(screen, False, 1.0)
    pygame.image.save(screen, os.path.join(DOCS, "map.png"))

    # A station with a train in, doors open.
    view = StationView(world, sim, "Anjos")
    for _ in range(int(400 / FRAME)):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        if any(m.line == view.line.name and m.current_station == view.name and 1.0 < m.cooldown < 2.6
               for m in sim.metros):
            break
    view.draw(screen, False, 1.0)
    pygame.image.save(screen, os.path.join(DOCS, "station.png"))

    # Inside the busiest train, between stops.
    train = max(sim.metros, key=lambda m: len(m.riders))
    ride = RideView(world, sim, train)
    for _ in range(int(120 / FRAME)):
        sim.update(FRAME)
        ride.update(FRAME, sim.drain_events())
        if not ride._dwelling() and 0.3 < train.progress < 0.7:
            break
    ride.draw(screen, False, 1.0)
    pygame.image.save(screen, os.path.join(DOCS, "ride.png"))
    print("wrote docs/map.png, docs/station.png, docs/ride.png")


if __name__ == "__main__":
    main()
