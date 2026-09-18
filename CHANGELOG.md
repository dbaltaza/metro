# Changelog

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
