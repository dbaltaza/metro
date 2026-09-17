
from src.network import build_demo_map
from src.route import run
from src.sim import Simulation, spread_trains

TRAINS_PER_LINE = 4


def main() -> None:
    metro_map = build_demo_map()
    run(Simulation(metro_map, spread_trains(metro_map, TRAINS_PER_LINE)))


if __name__ == "__main__":
    main()
