"""What the game keeps between runs, and the day it keeps it for."""

import json

import pygame
import pytest

from src import store
from src.daytime import DAY_SECONDS, DAY_END_HOUR, clock_text, day_number, hour_of
from src.route import DayReport
from src.settings import SETTINGS
from src.sim import Simulation, spread_trains
from src.store import DaySummary, Save
from tests.conftest import FRAME


@pytest.fixture
def kept(tmp_path, monkeypatch):
    """Somewhere to keep a save that is not the player's real one."""
    monkeypatch.setattr(store, "saves", lambda: tmp_path / "Metro Lisboa")
    return tmp_path / "Metro Lisboa" / store.FILE


def test_nothing_kept_yet_is_not_an_error(kept):
    assert not kept.exists()
    fresh = store.load()
    assert fresh.best is None and fresh.days_run == 0
    assert fresh.settings.demand == SETTINGS.demand


def test_what_is_kept_comes_back(kept):
    SETTINGS.sound = 1.0
    SETTINGS.demand = 1.8
    save = store.capture_settings(Save())
    save.best = DaySummary(day=3, delivered=1234, gave_up=5, average_wait=31.5, released=2, trains=18)
    save.days_run = 3
    assert store.write(save) is True
    assert kept.exists()

    SETTINGS.reset()
    back = store.load()
    assert back.settings.sound == 1.0 and back.settings.demand == 1.8
    assert back.best.delivered == 1234 and back.best.day == 3
    assert back.days_run == 3
    store.apply_settings(back)
    assert SETTINGS.sound == 1.0 and SETTINGS.demand == 1.8


def test_a_save_we_cannot_read_starts_you_fresh(kept):
    """Half a file, or one from some future version, must not stop the game."""
    kept.parent.mkdir(parents=True, exist_ok=True)
    for bad in ("", "{", '{"settings": {"demand": "loads"}}', json.dumps({"best": 7})):
        kept.write_text(bad, encoding="utf-8")
        assert store.load().best is None


def test_a_save_that_cannot_be_written_is_not_fatal(tmp_path, monkeypatch):
    """A read-only home directory should cost you your records, not the game."""
    monkeypatch.setattr(store, "saves", lambda: tmp_path / "nope")

    def refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(store.Path, "mkdir", refuse)
    assert store.write(Save()) is False


def test_the_save_does_not_live_with_the_code():
    """Inside a bundled app that directory is read-only."""
    from src.paths import root, saves
    assert root() not in saves().parents and saves() != root()
    assert "Metro Lisboa" in str(saves()) or "metro-lisboa" in str(saves())


def test_a_better_day_is_one_that_moved_more_people():
    first = DaySummary(day=1, delivered=100)
    assert first.better_than(None)
    assert DaySummary(day=2, delivered=101).better_than(first)
    assert not DaySummary(day=2, delivered=99).better_than(first)


def test_the_day_turns_over_when_the_network_is_empty():
    assert day_number(0.0) == 1
    ends_at = (DAY_END_HOUR - 7.0) % 24 * 60
    assert day_number(ends_at - 1) == 1 and day_number(ends_at) == 2
    assert clock_text(hour_of(ends_at)) == "03:00"
    assert day_number(ends_at + DAY_SECONDS) == 3


def test_a_day_of_service_is_counted_off_on_its_own(metro_map):
    """The figures are that day's, not everything since the game started."""
    sim = Simulation(metro_map, spread_trains(metro_map, 4), seed=5)
    summaries = []
    while sim.clock < DAY_SECONDS * 2:
        sim.update(FRAME)
        sim.drain_events()
        done = sim.take_finished_day()
        if done is not None:
            summaries.append(done)
    assert [s.day for s in summaries] == [1, 2]
    assert sim.day == 3
    assert sum(s.delivered for s in summaries) <= sim.delivered
    for summary in summaries:
        assert summary.delivered > 0 and summary.trains == len(sim.metros)
        assert 0 < summary.average_wait < 600


def test_the_day_is_only_handed_over_once(metro_map):
    sim = Simulation(metro_map, spread_trains(metro_map, 2), seed=5)
    sim.clock = DAY_SECONDS - 1
    sim.update(2.0)
    assert sim.take_finished_day() is not None
    assert sim.take_finished_day() is None


def test_the_report_shows_a_day_and_gets_out_of_the_way(display):
    report = DayReport()
    assert not report.open
    assert report.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0,
                                            unicode=" ", scancode=0)) is False
    report.draw(display)      # nothing open: nothing drawn, and no complaint

    today = DaySummary(day=2, delivered=2000, gave_up=10, average_wait=30.0, released=1, trains=16)
    report.show(today, DaySummary(day=1, delivered=1000), True)
    assert report.open
    report.draw(display)
    assert report.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5))) is True, "it swallows events"
    assert report.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=report.button.center, button=1)) is True
    assert not report.open

    # And with no best to compare against, which is the first day you run.
    report.show(today, None, True)
    report.draw(display)
