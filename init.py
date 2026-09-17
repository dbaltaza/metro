
from src.metro import Metro
from src.network import build_demo_map
from src.route import run
from src.sim import Simulation

TRAINS_PER_LINE = 4


def main() -> None:
    metro_map = build_demo_map()
    metros = []
    for line in metro_map.lines:
        # Trains start spread evenly along the line, alternating direction, so
        # the service is already running instead of bunching at the ends.
        last = len(line.stations) - 1
        for k in range(TRAINS_PER_LINE):
            index = round(k * last / max(TRAINS_PER_LINE - 1, 1))
            direction = 1 if k % 2 == 0 else -1
            if index == last:
                direction = -1
            elif index == 0:
                direction = 1
            metros.append(Metro(
                id=len(metros) + 1,
                line=line.name,
                current_station=line.stations[index],
                direction=direction,
            ))
    run(Simulation(metro_map, metros))


if __name__ == "__main__":
    main()
