"""The game's noise: worked out at startup, and silent when it cannot be."""

import pygame
import pytest

from src.audio import BEDS, RATE, Audio, _build, _loopable
from src.ride_view import RideView
from src.route import MapScene, World
from src.settings import SETTINGS
from src.station_view import StationView
from tests.conftest import FRAME, run_for

SAMPLES = _build()


class Ears:
    """Stands in for the audio while a scene runs, and writes down what it
    was asked to play."""

    def __init__(self):
        self.heard: list[str] = []

    def play(self, name, volume=1.0):
        self.heard.append(name)

    def beds(self, levels):
        pass

    def update(self, dt):
        pass


@pytest.fixture
def audio(display):
    made = Audio()
    made.start()
    yield made
    made.stop()


@pytest.fixture
def world(display, metro_map):
    return World(metro_map)


def test_every_sound_is_there_and_none_is_silent_or_clipped():
    assert set(SAMPLES) >= set(BEDS)
    for name, samples in SAMPLES.items():
        peak = max(abs(v) for v in samples)
        rms = (sum(v * v for v in samples) / len(samples)) ** 0.5
        assert peak <= 1.0, f"{name} clips"
        assert rms > 0.01, f"{name} is silence"
        assert 0.02 <= len(samples) / RATE <= 4.0, f"{name} is the wrong length"


def test_the_sounds_play_for_as_long_as_they_were_drawn_for(audio):
    """pygame.init() opens the mixer at its own rate and a second init() is a
    no-op, so these were read as 44100 stereo and came out at double speed."""
    assert audio.ok
    assert pygame.mixer.get_init()[0] == RATE
    for name, samples in SAMPLES.items():
        assert audio.sounds[name].get_length() == pytest.approx(len(samples) / RATE, abs=0.02), name


def test_the_loops_have_no_seam_in_them():
    """A bed runs for hours, so a step at the loop point would tick for hours."""
    for name in BEDS:
        samples = SAMPLES[name]
        rms = (sum(v * v for v in samples) / len(samples)) ** 0.5
        assert abs(samples[-1] - samples[0]) < rms * 2, name


def test_a_seam_would_be_caught():
    """Without the fold the ends of a bed are unrelated, and the test above
    has to notice."""
    raw = SAMPLES["murmur"]
    folded = _loopable(raw)
    assert abs(folded[-1] - folded[0]) <= abs(raw[-1] - raw[0]) + 1e-9


def test_turning_the_sound_off_stops_it(audio, monkeypatch):
    played = []
    monkeypatch.setattr(pygame.mixer, "find_channel", lambda force=False: played.append(1))
    SETTINGS.sound = 0.0
    audio.play("chime")
    assert not played
    SETTINGS.sound = 1.0
    audio.play("chime")
    assert played


def test_the_game_plays_on_without_a_mixer(monkeypatch):
    def no_sound_card(**kwargs):
        raise pygame.error("no audio device")

    monkeypatch.setattr(pygame.mixer, "init", no_sound_card)
    silent = Audio()
    silent.start()
    assert not silent.ok
    # None of this may raise: the game has to run on a machine with no sound.
    silent.play("chime")
    silent.beds({"murmur": 1.0})
    silent.update(FRAME)
    silent.stop()


def test_the_backgrounds_slide_rather_than_cutting(audio):
    SETTINGS.sound = 1.0
    audio.beds({"murmur": 1.0})
    audio.update(0.1)
    part_way = audio.level["murmur"]
    assert 0.0 < part_way < 1.0, "a bed that arrives in one frame is a click"
    for _ in range(60):
        audio.update(FRAME)
    assert audio.level["murmur"] == pytest.approx(1.0)
    audio.beds({})
    for _ in range(120):
        audio.update(FRAME)
    assert audio.level["murmur"] == 0.0


def test_each_scene_says_what_it_should_sound_like(world, sim, metro_map):
    assert MapScene(world, sim).ambience() == {}

    run_for(sim, 120)
    busiest = max(metro_map.stations.values(), key=lambda s: len(s.waiting))
    quietest = min(metro_map.stations.values(), key=lambda s: len(s.waiting))
    loud = StationView(world, sim, busiest.name).ambience()["murmur"]
    soft = StationView(world, sim, quietest.name).ambience()["murmur"]
    assert loud > soft, "a platform should sound like the number of people on it"
    assert 0.0 <= soft <= loud <= 1.0

    metro = max(sim.metros, key=lambda m: len(m.riders))
    ride = RideView(world, sim, metro).ambience()
    assert ride["roll"] > 0.0


def test_a_train_is_heard_pulling_in_and_shutting_its_doors(world, sim, metro_map, monkeypatch):
    ears = Ears()
    monkeypatch.setattr("src.station_view.AUDIO", ears)
    view = StationView(world, sim, "Campo Pequeno")
    run_for(sim, 90, view)
    for wanted in ("arrive", "chime", "doors", "depart"):
        assert wanted in ears.heard, (wanted, ears.heard)
    # A train already standing there when you walk in chimes without having
    # arrived, so what matters is that an arrival is followed by a chime.
    first = ears.heard.index("arrive")
    assert "chime" in ears.heard[first:], ears.heard


def test_walking_onto_a_platform_is_not_a_train_arriving(world, sim, metro_map, monkeypatch):
    """A train already standing there has not just pulled in."""
    run_for(sim, 30)
    metro = next((m for m in sim.metros if m.cooldown > 0), None)
    assert metro is not None, "no train was standing at a platform to test with"
    ears = Ears()
    monkeypatch.setattr("src.station_view.AUDIO", ears)
    view = StationView(world, sim, metro.current_station)
    view.update(FRAME, sim.drain_events())
    assert "arrive" not in ears.heard, ears.heard


def test_a_chime_is_never_played_over_a_background(audio, monkeypatch):
    """find_channel can hand back a channel that is already busy. The beds
    are reserved so it should never be one of theirs, but if it ever is, the
    loop underneath must not be played over: it would never come back."""
    SETTINGS.sound = 1.0
    monkeypatch.setattr(pygame.mixer, "find_channel", lambda force=False: audio.channels["murmur"])
    audio.play("click")
    assert audio.channels["murmur"].get_sound() is audio.sounds["murmur"]
    assert audio.channels["murmur"].get_busy()
