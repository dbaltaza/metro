"""Shared fixtures. Pygame runs on the dummy video driver so tests need no window."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.network import build_demo_map  # noqa: E402
from src.sim import Simulation, spread_trains  # noqa: E402

FRAME = 1 / 60


@pytest.fixture
def metro_map():
    return build_demo_map()


@pytest.fixture
def sim(metro_map):
    return Simulation(metro_map, spread_trains(metro_map, 4), seed=11)


@pytest.fixture(scope="session")
def display():
    pygame.init()
    from src.route import WINDOW_H, WINDOW_W
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    yield screen
    pygame.quit()


def run_for(sim, seconds: float, view=None) -> None:
    """Advance the simulation, and a station view if given, frame by frame."""
    for _ in range(int(seconds / FRAME)):
        sim.update(FRAME)
        events = sim.drain_events()
        if view is not None:
            view.update(FRAME, events)
