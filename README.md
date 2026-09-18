<p align="center"><img src="docs/logo.png" width="440" alt="Metro Lisboa"></p>

# Metro Lisboa

A Lisbon metro simulation you can walk around in, in pixel art. Trains run the
four real lines, passengers plan their own journeys and change at interchanges,
and you can drop from the network map into any station, then step aboard a
train and ride it to the other end of the city.

![The network map](docs/map.png)

## Running it

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python init.py
```

Needs Python 3.12 or newer.

### Easier ways to launch it

- **Double-click `Metro.command`** on macOS. It sets up the virtual environment
  the first time and starts the game every time after that.
- **Build an app** you can drop into Applications:

  ```
  tools/build_app.sh --install
  ```

  This builds `dist/Metro Lisboa.app` and copies it into Applications, so it
  opens from Launchpad or Spotlight like anything else. Python, the map data
  and the icon are inside it, so it runs on a Mac with nothing else installed.
  Leave off `--install` to only build. On Linux and Windows the result is a
  folder `dist/Metro Lisboa` with an executable in it. The first launch of an
  unsigned app on macOS needs a right-click, then Open.

## What you can do

**Run the network from the map.** Drag the map to move around it and scroll to
zoom in on a corner of the city; zoomed in, a small picture of the whole network
sits in the corner with your view boxed on it, and clicking it takes you there.
Hover a station to see who is waiting, and three pips beside each one light up
as its crowd grows. The panel scores you on
average wait and deliveries per minute, gives you a `+` and `-` per line to put
a train into service or take one out, and logs stalls and fleet changes as they
happen. Run the service too thin and people give up waiting and walk out, which
the panel counts against you in red.

**Walk into any station.** Clicking one takes you down through a tiled entrance,
past the sign telling you which lines stop there, and out onto the platform.
Coming back up runs the same way in reverse.

![Going down into a station](docs/loading.png)

**Watch a platform work.** Both directions are live: trains pull in, the doors
slide open, people get off and head for the stairs while the queue at the doors
files on, and the doors close again. New passengers come up out of the stairwell
rather than appearing out of nowhere. While they wait they check their phones,
sit on the benches, wander over to read the next-train display, and get up and
line up by the doors when a train is close. The signs count down. Interchanges
have a tab per line, and the station sign changes colour with it.

![Inside a station](docs/station.png)

**Get on and ride.** Click a train while its doors are open and you step through
them into the car. The tunnel scrolls past the windows and the next platform
slides in as you arrive. Riders take the seats and the standing room; hover one
to see where they are going. The line diagram above the board tracks the train,
and you can get off at any stop.

![Riding a train](docs/ride.png)

**Change how it plays.** `S` opens the settings over whatever is on screen and
pauses the game while they are open.

![The settings menu](docs/settings.png)

## Controls

| Key or click | Does |
|---|---|
| Drag the map | Move around the network |
| Scroll wheel, `+` `-` | Zoom in and out where the cursor is |
| Arrow keys | Pan |
| `0` | Fit the whole network again |
| Click a station | Walk into it |
| Click a stopped train (in a station) | Board it |
| `E` or the green button (on a train) | Get off at this stop |
| `Tab` (in an interchange) | Switch line |
| `Esc` or the MAP button | Back to the network |
| `S` | Open the settings |
| `Space` | Pause |
| `1` `2` `3` | Run at 1x, 2x, 4x |
| `+` `-` (panel) | Add or remove a train on a line |

## How it is put together

- `src/network.py` loads the network from `data/lisbon.json`: 50 stations on a
  0..1000 grid, four lines as ordered station lists.
- `src/routing.py` plans a journey as legs of "ride this line, get off here",
  over a graph of (station, line) states so changing costs something.
- `src/sim.py` moves the trains, keeps them a safe headway apart, spawns
  passengers, and handles boarding, changes, stalls, the fleet and the score.
  It knows nothing about screens: scenes read its state and drain its events.
- `src/settings.py` holds the handful of values the settings menu changes.
- `src/route.py` draws the map, owns the main loop and its three scenes, and
  holds the transitions between them. `Camera` is what you move around the map
  with: it only zooms in whole numbers of pixels, so the art never scales
  unevenly, and station names are drawn live at screen resolution on top so
  they stay sharp at any zoom.
- `src/station_view.py`, `src/station_layout.py` and `src/station_train.py` are
  the station scene. `src/ride_view.py` is the ride. `src/sprites.py` has the
  pixel characters and the caches they need to stay cheap.

Everything in the world is drawn at half size onto a 24-bit surface and scaled
up with no smoothing, which is where the chunky pixels come from. The 24 bits
matter: a surface with an alpha channel picks up stray alpha from sprite blits
and turns into coloured blocks on a real display driver, which the dummy driver
used in tests will not show you.

`tools/make_logo.py` draws the logo and the window icon. `tools/screenshots.py`
regenerates the pictures above. `tools/build_app.sh` packages the app.

## Tests

```
.venv/bin/python -m pytest -q
```

Eighty-four tests, running headless in a couple of seconds each. They cover the
rules that are easy to break by accident: people only board trains going their
way, everyone is through the doors before they close, countdowns that never
jump backwards, no two trains on one segment or one platform, nothing standing
in a doorway, platform queues that stay bounded over a long session, a drag of
the map that never turns into walking into a station, and every scene rendering
without raising. GitHub Actions runs them on every push, and a
tagged release builds the macOS app.

## License

Source-available, all rights reserved. You can read the code and play the game
yourself, but you cannot redistribute it, publish something based on it, or use
it commercially without permission. See [LICENSE](LICENSE).
