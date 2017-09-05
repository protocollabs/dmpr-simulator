import random

from topologies.randomized import RandomTopology

# Start simulation

SIMULATION_TIME = 300

simulation = RandomTopology(
    simulation_time=SIMULATION_TIME,
    velocity=lambda: random.random() ** 6,
    tracepoints=('tx.msg',),
)
routers = simulation.prepare()

for sec in simulation.start():
    pass
