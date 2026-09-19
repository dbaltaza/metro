"""Everything the game makes a noise with.

Nothing here is a recording: every sound is worked out from arithmetic when
the game starts, so there is nothing to ship alongside the code and nothing
anybody else owns. It is all cheap arithmetic over a few thousand samples,
which costs a fraction of a second at startup and nothing after that.

If there is no sound card, or the mixer will not start, everything in here
quietly does nothing rather than taking the game down with it.
"""

import array
import math
import random

import pygame

from src.settings import SETTINGS

RATE = 22050          # plenty for chimes and rumble, and half the arithmetic
FADE = 1.8            # how fast a background bed slides to its new level

# The looping backgrounds, and the channel each one holds.
BEDS = ("murmur", "roll")


def _pcm(samples) -> bytes:
    """Floats in -1..1 to the signed 16 bit mono the mixer is opened with."""
    return array.array("h", (int(max(-1.0, min(1.0, v)) * 30000) for v in samples)).tobytes()


def _tone(freq: float, seconds: float, harmonic: float = 0.0) -> list[float]:
    n = int(RATE * seconds)
    step = 2 * math.pi * freq / RATE
    return [math.sin(step * i) + harmonic * math.sin(2 * step * i) for i in range(n)]


def _sweep(start: float, end: float, seconds: float) -> list[float]:
    """A tone sliding from one pitch to another, by carrying the phase along
    rather than by the clock, which would make it jump."""
    n = int(RATE * seconds)
    out, phase = [], 0.0
    for i in range(n):
        freq = start + (end - start) * (i / n)
        phase += 2 * math.pi * freq / RATE
        out.append(math.sin(phase))
    return out


def _noise(seconds: float, rng: random.Random) -> list[float]:
    return [rng.uniform(-1.0, 1.0) for _ in range(int(RATE * seconds))]


def _lowpass(samples: list[float], k: float) -> list[float]:
    """One pole, which is all it takes to turn white noise into something
    that sounds like it is coming through a tunnel."""
    out, y = [], 0.0
    for x in samples:
        y += (x - y) * k
        out.append(y)
    return out


def _shape(samples: list[float], attack: float = 0.01, release: float = 0.08) -> list[float]:
    n = len(samples)
    rise = max(int(RATE * attack), 1)
    fall = max(int(RATE * release), 1)
    out = []
    for i, v in enumerate(samples):
        gain = min(i / rise, 1.0)
        remaining = n - i
        if remaining < fall:
            gain *= remaining / fall
        out.append(v * gain)
    return out


def _swell(samples: list[float], peak: float = 0.5) -> list[float]:
    """Quiet, loud, quiet: a train coming in and going past."""
    n = len(samples)
    mark = max(int(n * peak), 1)
    return [v * (i / mark if i < mark else max((n - i) / (n - mark), 0.0)) for i, v in enumerate(samples)]


def _mix(*layers: list[float]) -> list[float]:
    longest = max(len(layer) for layer in layers)
    out = [0.0] * longest
    for layer in layers:
        for i, v in enumerate(layer):
            out[i] += v
    return out


def _gain(samples: list[float], amount: float) -> list[float]:
    return [v * amount for v in samples]


def _at(samples: list[float], peak: float) -> list[float]:
    """Scale a sound to a stated loudness. Filtering noise takes most of its
    amplitude away, so how loud a layer ends up is nothing like how loud the
    numbers that went into it were: better to say than to guess."""
    loudest = max((abs(v) for v in samples), default=0.0)
    return samples if loudest == 0 else _gain(samples, peak / loudest)


def _loopable(samples: list[float], seconds: float = 0.25) -> list[float]:
    """Fold the tail back over the head so the loop has no seam in it."""
    n = min(int(RATE * seconds), len(samples) // 2)
    out = list(samples[:-n])
    for i in range(n):
        k = i / n
        out[i] = out[i] * k + samples[len(samples) - n + i] * (1 - k)
    return out


def _silence(seconds: float) -> list[float]:
    return [0.0] * int(RATE * seconds)


def _build() -> dict[str, list[float]]:
    """Every sound in the game, as floats, before the mixer sees them."""
    rng = random.Random(4)
    beep = _shape(_tone(1180, 0.075, harmonic=0.3), 0.004, 0.03)
    gap = _silence(0.075)
    return {
        # Doors opening: the two note chime, falling.
        "chime": _at(_mix(
            _shape(_tone(1318, 0.13, harmonic=0.25), 0.005, 0.09),
            _silence(0.11) + _shape(_tone(1046, 0.18, harmonic=0.25), 0.005, 0.13),
        ), 0.55),
        # Doors closing: three short beeps, the way they mean stand clear.
        "doors": _at(beep + gap + beep + gap + beep, 0.5),
        # A train coming in: rumble under a whine that falls as it slows.
        "arrive": _at(_mix(
            _at(_swell(_lowpass(_noise(1.2, rng), 0.035), 0.62), 1.0),
            _at(_shape(_sweep(320, 90, 1.2), 0.25, 0.35), 0.35),
        ), 0.6),
        # And going out: the whine climbs and the rumble goes with it.
        "depart": _at(_mix(
            _at(_swell(_lowpass(_noise(1.1, rng), 0.04), 0.3), 1.0),
            _at(_shape(_sweep(110, 380, 1.1), 0.15, 0.5), 0.35),
        ), 0.5),
        # The wrong control on the driver's desk: low and rough, twice.
        "buzz": _at(_shape(_tone(148, 0.12, harmonic=0.8), 0.003, 0.05) + _silence(0.05)
                    + _shape(_tone(148, 0.14, harmonic=0.8), 0.003, 0.06), 0.5),
        "click": _at(_shape(_lowpass(_noise(0.035, rng), 0.5), 0.001, 0.03), 0.4),
        # A platform full of people, as a wash with no voice you can pick out.
        "murmur": _at(_loopable(_lowpass(_noise(2.6, rng), 0.012)), 0.4),
        # Rolling: heavier rumble, with the rail joints going by underneath.
        "roll": _at(_loopable(_mix(
            _at(_lowpass(_noise(1.6, rng), 0.02), 1.0),
            _at(_mix(*[_silence(k * 0.4) + _shape(_lowpass(_noise(0.05, rng), 0.3), 0.002, 0.04)
                       for k in range(4)]), 0.45),
        )), 0.55),
    }


class Audio:
    """The game's noise. Silent until start() finds a mixer to use."""

    def __init__(self):
        self.ok = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.channels: dict[str, pygame.mixer.Channel] = {}
        self.level: dict[str, float] = {name: 0.0 for name in BEDS}
        self.target: dict[str, float] = {name: 0.0 for name in BEDS}

    def start(self) -> None:
        try:
            # pygame.init() has already opened the mixer at its own defaults,
            # and a second init() is a no-op, so the samples below would be
            # read as 44100 stereo and come out at double speed. Close it.
            pygame.mixer.quit()
            pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(16)
            # The beds loop forever and hold their channels for good, so
            # they are reserved: find_channel() is then never offered one,
            # even when it is forced to take a channel that is still busy.
            pygame.mixer.set_reserved(len(BEDS))
            self.sounds = {name: pygame.mixer.Sound(buffer=_pcm(samples))
                           for name, samples in _build().items()}
            for i, name in enumerate(BEDS):
                channel = pygame.mixer.Channel(i)
                channel.set_volume(0.0)
                channel.play(self.sounds[name], loops=-1)
                self.channels[name] = channel
        except (pygame.error, IndexError):
            # No sound card, no mixer, no noise. The game plays on regardless.
            self.ok = False
            return
        self.ok = True

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.ok or not SETTINGS.sound:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        channel = pygame.mixer.find_channel(True)
        if channel is None or channel in self.channels.values():
            return
        channel.set_volume(volume * SETTINGS.sound)
        channel.play(sound)

    def beds(self, levels: dict[str, float]) -> None:
        """How loud each background should be from now on; they slide there.
        Anything left out is on its way to silence, so a scene only has to
        say what it wants heard."""
        for name in BEDS:
            self.target[name] = max(0.0, min(levels.get(name, 0.0), 1.0))

    def update(self, dt: float) -> None:
        """Slide the backgrounds towards where they were asked to be. Called
        every frame whether the game is paused or not, so they can fade out."""
        if not self.ok:
            return
        for name in BEDS:
            target = self.target[name] * SETTINGS.sound
            current = self.level[name]
            if current != target:
                step = FADE * dt
                current = min(current + step, target) if current < target else max(current - step, target)
                self.level[name] = current
                self.channels[name].set_volume(current)

    def stop(self) -> None:
        if self.ok:
            pygame.mixer.stop()


AUDIO = Audio()
