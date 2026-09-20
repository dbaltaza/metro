"""The hour of the day, and what the city is doing at it.

A second of play at 1x is a minute of the day, so a full day takes twenty-four
minutes to run and the service opens at seven, climbing into the morning peak.
Nothing here knows about trains or screens: the simulation asks how busy the
network is and which way people are going, and draws its own conclusions.
"""

from pydantic import BaseModel, Field

MINUTES_PER_SECOND = 1.0
START_HOUR = 7.0

# How busy the whole network is at a given hour, interpolated between these.
# Two peaks, a midday that never quite settles, and a city that mostly sleeps.
DEMAND: tuple[tuple[float, float], ...] = (
    (0.0, 0.10), (3.0, 0.03), (5.0, 0.12), (6.5, 0.75),
    (8.5, 2.30), (10.0, 0.95), (12.5, 1.10), (14.0, 0.85),
    (17.0, 1.50), (18.5, 2.20), (20.0, 0.95), (22.0, 0.50), (24.0, 0.10),
)

# Which way the city is travelling. +1 is everyone heading for the middle of
# it, -1 is everyone heading back out, 0 is no particular direction.
PULL: tuple[tuple[float, float], ...] = (
    (0.0, 0.0), (6.0, 0.3), (8.5, 1.0), (11.0, 0.2),
    (14.0, 0.0), (17.0, -0.7), (18.5, -1.0), (21.0, -0.3), (24.0, 0.0),
)


class Period(BaseModel):
    """A named stretch of the day, for the panel to put a word to the hour."""

    from_hour: float = Field(ge=0.0, le=24.0)
    name: str


PERIODS: tuple[Period, ...] = (
    Period(from_hour=0.0, name="night"),
    Period(from_hour=5.0, name="first trains"),
    Period(from_hour=6.5, name="early service"),
    Period(from_hour=7.5, name="morning peak"),
    Period(from_hour=9.5, name="midday"),
    Period(from_hour=16.5, name="evening peak"),
    Period(from_hour=19.5, name="evening"),
    Period(from_hour=23.0, name="last trains"),
)


# Service ends in the small hours, when the network is empty: that is where
# one day is counted off from the next.
DAY_END_HOUR = 3.0
DAY_SECONDS = 24 * 60 / MINUTES_PER_SECOND
_DAY_OFFSET = (DAY_END_HOUR - START_HOUR) % 24 * 60 / MINUTES_PER_SECOND


def day_number(clock: float) -> int:
    """Which day of service a moment belongs to, counting from one."""
    return 1 + int((clock + DAY_SECONDS - _DAY_OFFSET) // DAY_SECONDS)


def hour_of(clock: float) -> float:
    """The hour of the day, 0 to 24, at a given moment of the simulation."""
    return (START_HOUR + clock * MINUTES_PER_SECOND / 60.0) % 24.0


def _at(curve: tuple[tuple[float, float], ...], hour: float) -> float:
    """Read a curve at an hour, straight lines between its points."""
    hour %= 24.0
    for (h1, v1), (h2, v2) in zip(curve, curve[1:]):
        if h1 <= hour <= h2:
            span = h2 - h1
            return v1 if span == 0 else v1 + (v2 - v1) * (hour - h1) / span
    return curve[-1][1]


def demand_at(hour: float) -> float:
    """How busy the network is, as a multiplier on the usual rate."""
    return _at(DEMAND, hour)


def pull_at(hour: float) -> float:
    """Which way people are going: towards the middle, or away from it."""
    return _at(PULL, hour)


def period_at(hour: float) -> str:
    hour %= 24.0
    name = PERIODS[-1].name
    for period in PERIODS:
        if hour >= period.from_hour:
            name = period.name
    return name


# The hours the network is at its busiest: the tall points of the curve, so
# they follow it if the curve is ever redrawn.
PEAKS: tuple[float, ...] = tuple(
    hour for i, (hour, busy) in enumerate(DEMAND[1:-1], start=1)
    if busy >= 1.5 and busy > DEMAND[i - 1][1] and busy > DEMAND[i + 1][1]
)


def next_peak(hour: float) -> tuple[float, float]:
    """The next peak: how many hours away it is, and which hour it is at.
    Inside a peak it gives that peak, counting down to nothing."""
    hour %= 24.0
    for peak in PEAKS:
        if peak >= hour:
            return peak - hour, peak
    return PEAKS[0] + 24.0 - hour, PEAKS[0]


def clock_text(hour: float) -> str:
    hour %= 24.0
    minutes = round(hour * 60) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
