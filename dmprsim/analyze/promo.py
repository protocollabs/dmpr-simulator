import random
from pathlib import Path

from dmprsim.topologies.randomized import RandomTopology
from dmprsim.topologies.utils import ffmpeg

SIMULATION_TIME = 1200

INTERFACES = [
    {
        "name": "wifi0",
        "range": 75,
        "core-config": {
            "link-attributes": {"bandwidth": 8000, "loss": 10},
        }
    },
    {
        "name": "tetra0",
        "range": 200,
        "core-config": {
            "link-attributes": {"bandwidth": 1000, "loss": 5},
        }
    },
    {
        "name": "lte0",
        "range": 300,
        "core-config": {
            "link-attributes": {"bandwidth": 400, "loss": 10},
        }
    },
]


def main(args, results_dir: Path, scenario_dir: Path):
    sim = RandomTopology(
        simulation_time=SIMULATION_TIME,
        interfaces=INTERFACES,
        num_routers=30,
        scenario_dir=scenario_dir,
        results_dir=results_dir,
        args=args,
        area=(1600, 900),
        velocity=lambda: random.random() ** 6,
    )
    sim.prepare()
    for _ in sim.start():
        pass

    if sim.gen_movie:
        ffmpeg(results_dir, scenario_dir)
