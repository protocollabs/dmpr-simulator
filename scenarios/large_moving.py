import os
import random

from topologies.randomized import RandomTopology
from topologies.utils import ffmpeg

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

dest_dir = os.path.join(os.getcwd(), 'run-data', 'large_moving')
print("generating movie in {}".format(dest_dir))
ffmpeg(dest_dir)
