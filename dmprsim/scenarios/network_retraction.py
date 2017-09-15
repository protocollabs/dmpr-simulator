import os

from dmprsim.topologies.circle import CircleTopology
from dmprsim.topologies.utils import ffmpeg

SIMULATION_TIME = 500
NAME = 'circle_with_removing'

simulation = CircleTopology(
    simulation_time=SIMULATION_TIME,
    tracepoints=('tx.msg',),
    name=NAME,
    num_routers=8,
)
routers = simulation.prepare()

simulation.tx_router = routers[0]
routers[0].is_transmitter = True
simulation.rx_ip = routers[2].pick_random_configured_network()
routers[2].is_receiver = True
simulation.simulate_forwarding = True

for sec in simulation.start():
    if sec == 150:
        routers[1].mm.visible = False

dest_dir = os.path.join(os.getcwd(), 'run-data', NAME)
print("generating movie in {}".format(dest_dir))
ffmpeg(dest_dir)
