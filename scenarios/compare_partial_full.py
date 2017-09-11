"""
Run once for each combination of size, range, partial/full mode,
can be used to compare message sizes and speed for different sized and
meshed networks
"""

import os

from topologies.square import SquareTopology

NAME = 'compare_partial_full'
SIMULATION_TIME = 1000
MAX_SIZE = 20
MAX_RANGE = None
MAX_RANGE_PERCENT = None
RANGE_STEP = 1
MAX_FULL_UPDATE_INTERVAL = 10


def simulate(size, link_range, partial):
    name = "{size}x{size}-range-{range}-partial-{partial}"
    name = name.format(size=size,
                       range=link_range,
                       partial=partial)
    log_directory = os.path.join(os.getcwd(), 'run-data', NAME, name)
    config = {
        'max-full-update-interval': partial,
    }
    sim = SquareTopology(
        name=NAME,
        simulation_time=SIMULATION_TIME,
        size=size,
        visualize=False,
        simulate_forwarding=False,
        tracepoints=('tx.msg',),
        log_directory=log_directory,
        config=config,
    )
    routers = sim.prepare()
    for second in sim.start():
        pass


def main():
    for size in range(2, MAX_SIZE):
        max_range = size + 1
        if MAX_RANGE is not None:
            max_range = min(max_range, MAX_RANGE)
        elif MAX_RANGE_PERCENT is not None:
            max_range = int(min(max_range, max_range * MAX_RANGE_PERCENT))

        for link_range in range(1, max_range, RANGE_STEP):
            for partial in (0, MAX_FULL_UPDATE_INTERVAL):
                simulate(size, link_range, partial)


if __name__ == '__main__':
    main()
