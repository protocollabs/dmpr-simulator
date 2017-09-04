import os
import random

import draw
from dmprsim import MobilityArea, StaticMobilityModel, gen_data_packet
from scenarios.utils import generate_routers

interfaces = [
    {"name": "wifi0", "range": 50, "bandwidth": 8000, "loss": 10},
    {"name": "tetra0", "range": 100, "bandwidth": 1000, "loss": 5}
]

SIMULATION_TIME = 1000
NUM_ROUTERS = 100


def simulate(log_directory):
    draw.setup_img_folder(log_directory)
    area = MobilityArea(600, 500)

    models = (StaticMobilityModel(area) for _ in range(NUM_ROUTERS))
    routers = generate_routers(interfaces, models, log_directory)

    tx_router = random.choice(routers)
    while True:
        rx_router = random.choice(routers)
        if rx_router != tx_router:
            break

    tx_router.is_transmitter = True
    rx_router.is_receiver = True
    rx_ip = rx_router.pick_random_configured_network()

    for sec in range(SIMULATION_TIME):
        if sec % 5 != 0:
            #continue
            pass
        print("{}\n\ttime: {}/{}".format("=" * 50, sec, SIMULATION_TIME))
        for router in routers:
            router.step(sec)

        class args:
            color_scheme = 'light'

        draw.draw_images(args, log_directory, area, routers, sec)

        packet_low_loss = gen_data_packet(tx_router, rx_ip, tos='lowest-loss')
        tx_router.forward_packet(packet_low_loss)
        packet_bandwidth = gen_data_packet(tx_router, rx_ip, tos='highest-bandwidth')
        tx_router.forward_packet(packet_bandwidth)


def main():
    log_directory = os.path.join(os.getcwd(), 'run-data', 'large_static')
    os.makedirs(log_directory, exist_ok=True)
    simulate(log_directory)


if __name__ == '__main__':
    main()
