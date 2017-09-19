import random
from pathlib import Path

from dmprsim.topologies.randomized import RandomTopology
from dmprsim.topologies.utils import ffmpeg

SIMU_TIME = 300


def main(args, results_dir: Path, scenario_dir: Path):
    sim = RandomTopology(
        simulation_time=getattr(args, 'simulation_time', 300),
        num_routers=getattr(args, 'num_routers', 100),
        random_seed_prep=getattr(args, 'random_seed_prep', 1),
        random_seed_runtime=getattr(args, 'random_seed_runtime', 1),
        scenario_dir=scenario_dir,
        results_dir=results_dir,
        args=args,
        tracepoints=('tx.msg',),
        area=(640, 720),
        velocity=lambda: random.random()**6,
    )
    sim.prepare()
    for _ in sim.start():
        pass

    if sim.gen_movie:
        ffmpeg(results_dir, scenario_dir)
