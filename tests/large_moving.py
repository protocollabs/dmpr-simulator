import random

from scenarios.parameterized import main as simulate

# Start simulation

SIMULATION_TIME = 300

routers = simulate(
    simulation_time=SIMULATION_TIME,
    velocity=lambda: random.random() ** 6,
    tracepoints=('tx.msg',),
    random_seed_prep=2,
)

for router in routers:
    pass
