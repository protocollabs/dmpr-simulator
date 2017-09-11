import os

from topologies.circle import CircleTopology
from topologies.utils import ffmpeg

SIMULATION_TIME = 1200
NAME = 'circle_with_disappearing_node'
MOVIE_GEN = False

CONFIGS = {
    'full': {
        'max-full-update-interval': 0,
    },
    'partial': {
        'max-full-update-interval': 6,
    },
}


def main():
    for mode in 'full', 'partial':
        mode_name = '{}_{}'.format(NAME, mode)
        mode_config = CONFIGS[mode]
        simulation = CircleTopology(
            simulation_time=SIMULATION_TIME,
            tracepoints=('tx.msg',),
            name=mode_name,
            num_routers=8,
            simulate_forwarding=False,
            visualize=MOVIE_GEN,
            config=mode_config,
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


if __name__ == '__main__':
    main()
