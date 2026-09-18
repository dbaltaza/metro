# Changelog

## 1.1.0 (2026-09-18)

A map you can move around in, a way in and out of every station, and a
platform that behaves like a real one.

**Getting around the map.** Drag to pan, scroll to zoom in on a corner of
the city, arrows to pan, `0` to fit the whole network again. Zoomed in, a
small picture of the network sits in the corner with your view boxed on it;
click it to go there. Zoom steps are whole numbers of pixels, so the art
never scales unevenly, and station names are drawn live on top so they stay
sharp however far in you are. The names themselves are cut out against a
dark stroke, bold and brighter where lines meet, and the one under your
cursor lights up.

**Walking in and out.** Clicking a station takes you down through a tiled
entrance past a sign for the lines that stop there, and coming back up runs
the same way in reverse. Stepping on or off a train slides its door leaves
open and shut around you.

**The platform.** Passengers come up out of the stairwell instead of
appearing out of nowhere, and a whole trainload changing lines arrives as a
stream rather than a clump. While they wait they check their phones, sit on
the benches, wander over to the next-train display, and line up by the doors
when a train is close. Waiting is not infinite: people give up and walk out,
and the panel counts them against you.

**The train.** The car is bigger, with a Lisbon interior: moulded seats,
priority seats by the doors, poles planted on the floor, straps that sway,
a route strip over the windows and a door call button. People getting off
are animated off the train instead of vanishing, and the whole business of
getting off and on now fits inside the dwell.

**Settings.** `S` opens a menu over whatever is on screen and pauses the
game: passenger demand, incidents on or off, how long people wait, and how
many are drawn on a platform.

**Fixes.** Six bugs that only showed after a long session, among them
platform queues that grew without limit and a slow frame that got slower the
longer you played: the worst frame after twenty minutes went from 199 ms to
0.4 ms and stopped growing. Switching line at an interchange no longer
leaves the other line's people walking about, and the station sign changes
colour with the line.

**Licence.** Source-available, all rights reserved. Read it and play it, but
no redistribution, derivative publication or commercial use without
permission.

**Under the hood.** 84 tests now, up from 35.

## 1.0.0 (2026-09-18)

First release. A Lisbon metro simulation you can walk around in.

**The network.** The four real lines with 50 stations, drawn as a pixel-art
map. Trains keep a safe headway, reverse at the termini, and occasionally
stall. Passengers pick a destination anywhere on the network, plan the
journey, and change lines at interchanges.

**Three views.**
- The map, with a panel showing average wait, deliveries per minute, the
  fleet on each line, and a log of what just happened.
- Any station: two platforms, two tracks, trains pulling in, doors opening,
  people boarding only on the side that goes their way.
- Inside a train: ride the line, watch people get on and off, and get off
  yourself at any stop.

**Playing it.** Speed control (1, 2, 3), pause (space), add or remove trains
per line, and incidents to deal with.

**Launching.** `Metro.command` runs it from the source checkout. The macOS
app attached to this release runs without Python installed: unzip, drop it
into Applications, right-click and Open the first time.

**Under the hood.** Python 3.12, pygame, pydantic models, 35 tests running
on every push.
