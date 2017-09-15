"""
A quick scenario for code profiling
"""
from pathlib import Path

from dmprsim.topologies.randomized import RandomTopology


def main(args, log_directory: Path):
    sim = RandomTopology(
        name='python_profile',
        simulation_time=50,
        num_routers=150,
        area=(500, 500),
        velocity=lambda: 0.05,
        args=args,
        log_directory=log_directory,
    )
    sim.prepare()

    for _ in sim.start():
        pass
