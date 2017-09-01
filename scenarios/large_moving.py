import os
import random

from dmprsim import Router, MobilityArea, MobilityModel, gen_data_packet
from scenarios.utils import generate_routers

interfaces = [
    {"name": "wifi0", "range": 50, "bandwidth": 8000, "loss": 10},
    {"name": "tetra0", "range": 100, "bandwidth": 1000, "loss": 5}
]

SIMULATION_TIME = 100
NUM_ROUTERS = 100

def simulate(log_directory):
    area = MobilityArea(600, 500)

    models = (MobilityModel(area) for i in range(NUM_ROUTERS))
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
            continue
        print("{}\n\ttime: {}/{}".format("=" * 50, sec, SIMULATION_TIME))
        for router in routers:
            router.step(sec)

        # draw.draw_images(args, log_directory, area, routers, sec)

        packet_low_loss = gen_data_packet(tx_router, rx_ip, tos='lowest-loss')
        tx_router.forward_packet(packet_low_loss)



def main():
    log_directory = os.path.join(os.getcwd(), 'two_static')
    os.makedirs(log_directory, exist_ok=True)
    simulate(log_directory)


if __name__ == '__main__':
    main()
