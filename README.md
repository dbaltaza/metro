<p align="center"><img src="docs/logo.png" width="440" alt="Metro Lisboa"></p>

# Metro Lisboa

A Lisbon metro simulation you can walk around in. Trains run the four real
lines, passengers plan journeys and change at interchanges, and you can drop
from the network map into any station, then board a train and ride it.

![The network map](docs/map.png)

## Running it

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python init.py
```

Needs Python 3.12 or newer.

## What you can do

**On the map**, hover a station to see who is waiting and click to walk in.
Three pips beside each station light up as its crowd grows. The panel on the
right scores the network by average wait and deliveries per minute, has `+`
and `-` per line to put a train into service or take one out, and logs stalls
and fleet changes.

**In a station**, both platforms of the line are live: trains pull in, doors
open, people get off and the queues file in, then the doors close. The signs
count down to the next train. Interchanges have a tab per line. Click a train
while its doors are open to board it.

![Inside a station](docs/station.png)

**On the train**, the tunnel scrolls past the windows and the next platform
slides in as you arrive. Riders sit and stand in the car; hover one to see
where they are going. The line diagram tracks the train, and a button lets
you get off at any stop.

![Riding a train](docs/ride.png)

## Controls

| Key or click | Does |
|---|---|
| Click a station | Enter it |
| Click a stopped train (in a station) | Board it |
| `E` or the green button (on a train) | Get off at this stop |
| `Tab` (in an interchange) | Switch line |
| `Esc` or the MAP button | Back to the network |
| `Space` | Pause |
| `1` `2` `3` | Run at 1x, 2x, 4x |
| `+` `-` (panel) | Add or remove a train on a line |

## How it is put together

- `src/network.py` loads the network from `data/lisbon.json`: stations on a
  0..1000 grid, lines as ordered station lists.
- `src/routing.py` plans journeys as legs of "ride this line, get off here".
- `src/sim.py` moves the trains, applies the headway rule so they never share
  a segment or a platform, spawns passengers, handles boarding, transfers,
  stalls and the fleet.
- `src/route.py` draws the map and runs the main loop with its three scenes.
- `src/station_view.py`, `src/station_layout.py`, `src/station_train.py` are
  the station scene; `src/ride_view.py` the ride; `src/sprites.py` the shared
  pixel characters and caches.

Everything is drawn at half size and scaled up without smoothing, which is
where the pixel look comes from.

The logo and window icon are drawn the same way by `tools/make_logo.py`,
which writes `docs/logo.png` and `docs/icon.png`.

## Tests

```
.venv/bin/python -m pytest -q
```

They run headless and cover the simulation invariants: boarding only in the
train's direction, everyone inside before the doors close, countdowns that
never jump, no two trains on one segment, and the scenes rendering cleanly.
GitHub Actions runs them on every push.
