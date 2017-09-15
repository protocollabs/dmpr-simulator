"""
Just a large random network which moves slowly
"""

import random
from pathlib import Path

from dmprsim.topologies.randomized import RandomTopology
from dmprsim.topologies.utils import ffmpeg

SIMULATION_TIME = 20

simulation = RandomTopology(
    simulation_time=SIMULATION_TIME,
    velocity=lambda: random.random() ** 6,
    tracepoints=('tx.msg',),
    name='large_moving',
)
routers = simulation.prepare()

for sec in simulation.start():
    pass

dest_dir = Path.cwd() / 'run-data' / 'large_moving'
ffmpeg(dest_dir)
