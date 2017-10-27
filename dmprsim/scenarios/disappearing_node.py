"""
Removes a node after 300 seconds, adds it after 900 seconds
One run for full mode, one for partial
"""
from pathlib import Path

from dmprsim.topologies.circle import CircleTopology
from dmprsim.topologies.utils import ffmpeg

SIMULATION_TIME = 1200

CONFIG = {
    'max-full-update-interval': 6,

}


def main(args, results_dir: Path, scenario_dir: Path):
    simulation = CircleTopology(
        simulation_time=SIMULATION_TIME,
        tracepoints=('rx.msg.valid',),
        scenario_dir=scenario_dir,
        results_dir=results_dir,
        num_routers=8,
        core_config=CONFIG,
        args=args,
    )
    models = simulation.prepare()

    tx_router = models[0].router
    rx_router = models[2].router
    simulation.tx_router = tx_router
    tx_router.is_transmitter = True
    simulation.rx_ip = rx_router.get_random_network()
    rx_router.is_receiver = True
    simulation.simulate_forwarding = True

    for sec in simulation.start():
        if sec > 900:
            models[1].visible = True
        elif sec > 300:
            models[1].visible = False

    if simulation.gen_movie:
        ffmpeg(results_dir, scenario_dir)


if __name__ == '__main__':
    main(object(), Path.cwd(), Path.cwd())
