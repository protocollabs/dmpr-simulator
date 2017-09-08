import os

from topologies.circle import CircleTopology
from topologies.utils import ffmpeg

SIMULATION_TIME = 1200
NAME = 'circle_with_disappearing_node'
MOVIE_GEN = False

simulation = CircleTopology(
    simulation_time=SIMULATION_TIME,
    tracepoints=('tx.msg',),
    name=NAME,
    num_routers=8,
    simulate_forwarding=False,
    visualize=MOVIE_GEN,
)
routers = simulation.prepare()

simulation.tx_router = routers[0]
routers[0].is_transmitter = True
simulation.rx_ip = routers[2].pick_random_configured_network()
routers[2].is_receiver = True
simulation.simulate_forwarding = True

for sec in simulation.start():
    if sec == 300:
        routers[1].mm.visible = False

    if sec == 900:
        routers[1].mm.visible = True

if MOVIE_GEN:
    dest_dir = os.path.join(os.getcwd(), 'run-data', NAME)
    print("generating movie in {}".format(dest_dir))
    ffmpeg(dest_dir)
