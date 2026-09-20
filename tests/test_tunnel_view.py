"""Looking down the tunnel at a train that has stopped, and getting it going."""

import pygame
import pytest

from src.route import World
from src.sim import FAULTS, FUMBLE_SECONDS, RELEASE_SECONDS
from src.tunnel_view import CONTROLS, ROLL_AWAY, TunnelView
from tests.conftest import FRAME, run_for


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


@pytest.fixture
def stopped(display, world, sim):
    """A train stopped in the tunnel, and the view of it."""
    run_for(sim, 30)
    metro = sim.metros[0]
    metro.progress = 0.5
    metro.stalled = 40.0
    metro.fault = "brake fault"
    return TunnelView(world, sim, metro), metro


def click(rect):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1)


def key(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, unicode="", scancode=0)


def control_for(view, fault: str) -> pygame.Rect:
    return next(rect for rect, _, answers in view.control_rects if fault in answers)


def test_there_is_exactly_one_control_for_every_fault():
    """A fault nothing on the desk clears would leave the train there, and
    one that two controls clear would make the desk a coin toss."""
    covered = [fault for _, faults in CONTROLS for fault in faults]
    assert sorted(covered) == sorted(FAULTS)
    assert len(set(covered)) == len(covered)
    assert len({label for label, _ in CONTROLS}) == len(CONTROLS)


def test_the_right_control_gets_the_train_moving(stopped, display):
    view, metro = stopped
    view.draw(display, False)
    assert view.stopped() and metro.stalled > RELEASE_SECONDS
    view.handle(click(control_for(view, "brake fault")))
    assert metro.fault == ""
    assert metro.stalled <= RELEASE_SECONDS
    assert view.sim.released == 1
    assert not view.stopped(), "cleared, so it is pulling away rather than held"


def test_the_wrong_control_costs_time_and_says_so(stopped, display):
    view, metro = stopped
    view.draw(display, False)
    before = metro.stalled
    view.handle(click(control_for(view, "door interlock")))
    assert metro.stalled == pytest.approx(before + FUMBLE_SECONDS)
    assert metro.fault == "brake fault", "still broken"
    assert view.wrong is not None and view.wrong[0] == "DOOR OVERRIDE"
    assert view.sim.released == 0


def test_the_desk_goes_dead_once_the_fault_is_cleared(stopped, display):
    view, metro = stopped
    view.draw(display, False)
    view.handle(click(control_for(view, "brake fault")))
    view.draw(display, False)
    assert view.control_rects == [], "nothing left to press"
    released = view.sim.released
    view.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(640, 700), button=1))
    assert view.sim.released == released


def test_it_hands_the_desk_back_once_the_train_is_away(stopped):
    view, metro = stopped
    assert view.update(FRAME, []) is None
    view.sim.release(metro)
    # It stays put while the train pulls away, so you see it go.
    for _ in range(int(ROLL_AWAY / FRAME) - 10):
        assert view.update(FRAME, []) is None
    result = None
    for _ in range(30):
        result = view.update(FRAME, [])
        if result is not None:
            break
    assert result == ("control",)


def test_a_train_taken_out_of_service_hands_the_desk_back(stopped):
    view, metro = stopped
    view.sim.metros.remove(metro)
    assert view.update(FRAME, []) == ("control",)


def test_escape_and_the_button_go_back_to_the_desk(stopped):
    view, _ = stopped
    assert view.handle(key(pygame.K_ESCAPE)) == ("control",)
    assert view.handle(click(view.back_rect)) == ("control",)


def test_it_sounds_like_a_tunnel(stopped):
    view, metro = stopped
    held = view.ambience()["roll"]
    view.sim.release(metro)
    assert view.ambience()["roll"] > held, "it should get louder once it moves"


def test_it_draws_stopped_and_moving_without_stray_alpha(stopped, display):
    view, metro = stopped
    view.draw(display, False)
    assert view.world_surface.get_bitsize() == 24
    assert view.control_rects, "the controls are there while it is held"
    view.sim.release(metro)
    for _ in range(30):
        view.update(FRAME, [])
    view.draw(display, False, 4.0)
    assert view.world_surface.get_bitsize() == 24


def test_the_tunnel_only_flows_once_the_train_is_moving(stopped):
    view, metro = stopped
    for _ in range(30):
        view.update(FRAME, [])
    assert view.travelled == 0.0, "a stopped train is not going anywhere"
    view.sim.release(metro)
    for _ in range(30):
        view.update(FRAME, [])
    assert view.travelled > 0.0
    assert view._signal_ahead() < 9.0, "the signal should be coming towards us"
