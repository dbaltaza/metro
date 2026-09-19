"""Regenerates the README screenshots in docs/.

    .venv/bin/python tools/screenshots.py

Runs on the real display driver in a hidden window, because the dummy one
has hidden alpha bugs from us before.
"""

import os
import sys

import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.control_room import ControlRoom        # noqa: E402
from src.network import build_demo_map          # noqa: E402
from src.ride_view import RideView              # noqa: E402
from src.route import (                      # noqa: E402
    WINDOW_H, WINDOW_W, MapScene, SettingsMenu, StationTransition, World,
)
from src.sim import Simulation, spread_trains
from src.station_style import style_for   # noqa: E402
from src.station_view import StationView        # noqa: E402
from src.tunnel_view import TunnelView          # noqa: E402

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

    # An interchange, so the line tabs show, caught with a train at the
    # platform, its doors open and people waiting on both sides.
    view = StationView(world, sim, "Alameda")
    best = None
    for _ in range(int(600 / FRAME)):
        sim.update(FRAME)
        view.update(FRAME, sim.drain_events())
        train = next((m for m in sim.metros if m.line == view.line.name
                      and m.current_station == view.name and 1.0 < m.cooldown < 2.6), None)
        if train is None:
            continue
        # Count who is actually out on the platform, not who is queued: people
        # still coming up the stairs are mid-fade and look like ghosts.
        out = {-1: 0, 1: 0}
        for passenger, side in view._crowd():
            state = view.people.get(passenger.id)
            if state is not None and state["alpha"] == 255 and state["act"] != "arriving":
                out[side] += 1
        both = min(out.values())
        if best is None or both > best:
            best = both
            view.draw(screen, False, 1.0)
            pygame.image.save(screen, os.path.join(DOCS, "station.png"))
        if both >= 12:
            break

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

    # The entrance loader, held open at the point where it is fully covered.
    serving = world.serving["Alameda"]
    loader = StationTransition(("station", "Alameda"), serving[0].color, "Alameda",
                               "walking down to the platform", serving,
                               palette=style_for("Alameda").palette)
    loader.phase, loader.t = "hold", loader.HOLD * 0.55
    loader.draw(screen)
    pygame.image.save(screen, os.path.join(DOCS, "loading.png"))

    # The settings menu over the map.
    MapScene(world, sim).draw(screen, False, 1.0)
    menu = SettingsMenu()
    menu.open = True
    menu.row = 0
    menu.draw(screen)
    pygame.image.save(screen, os.path.join(DOCS, "settings.png"))
    # The control room, with something broken to attend to, and the view
    # down the tunnel at it. The fault is set by hand so the picture is the
    # same every time rather than waiting for one to happen.
    hurt = max((m for m in sim.metros if 0.2 < m.progress < 0.8), key=lambda m: len(m.riders))
    hurt.stalled, hurt.fault = 38.0, "traction cut-out"
    ControlRoom(world, sim).draw(screen, False, 1.0)
    pygame.image.save(screen, os.path.join(DOCS, "control.png"))

    tunnel = TunnelView(world, sim, hurt)
    for _ in range(20):
        tunnel.update(FRAME, [])
    tunnel.draw(screen, False)
    pygame.image.save(screen, os.path.join(DOCS, "tunnel.png"))

    print("wrote map, station, ride, loading, settings, control and tunnel pictures in docs/")


if __name__ == "__main__":
    main()
