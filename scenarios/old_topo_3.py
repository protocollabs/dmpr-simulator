"""
The old topology 3 rebuilt, mainly for speed comparison before/after rewrite
"""

from topologies.randomized import RandomTopology

sim = RandomTopology(
    simulation_time=30,
    num_routers=200,
    area=(960, 1080),
    velocity=lambda: 1,
    visualize=False,
)

sim.prepare()

for _ in sim.start():
    pass
