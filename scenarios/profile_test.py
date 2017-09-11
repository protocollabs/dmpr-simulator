"""
A quick scenario for code profiling
"""

from topologies.randomized import RandomTopology

sim = RandomTopology(
    name='profile_test',
    simulation_time=50,
    num_routers=150,
    area=(500, 500),
    velocity=lambda: 0.05,
    visualize=False,
    simulate_forwarding=False,
)

sim.prepare()

for _ in sim.start():
    pass
