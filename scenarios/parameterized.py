import os
import random

import draw
from dmprsim import MobilityArea, MobilityModel, gen_data_packet
from scenarios.utils import generate_routers

SIMULATION_TIME = 1000
NUM_ROUTERS = 200
DEFAULT_AREA = (1000, 1000)
DEFAULT_RANGE_1 = 50
DEFAULT_RANGE_2 = 100
DEFAULT_RAND_SEED = 1


def simulate(log_directory, simulation_time, num_routers, area, interfaces,
             random_seed_prep, random_seed_runtime, velocity, visualize):
    random.seed(random_seed_prep)
    if visualize:
        draw.setup_img_folder(log_directory)
    area = MobilityArea(*area)

    models = (MobilityModel(area, velocity=velocity) for _ in
              range(num_routers))

    routers = generate_routers(interfaces, models, log_directory)

    tx_router = random.choice(routers)
    while True:
        rx_router = random.choice(routers)
        if rx_router != tx_router:
            break

    tx_router.is_transmitter = True
    rx_router.is_receiver = True
    rx_ip = rx_router.pick_random_configured_network()

    random.seed(random_seed_runtime)

    for sec in range(simulation_time):
        print("{}\n\ttime: {}/{}".format("=" * 50, sec, simulation_time))
        for router in routers:
            router.step(sec)

        class args:
            color_scheme = 'light'

        if visualize:
            draw.draw_images(args, log_directory, area, routers, sec)

        packet_low_loss = gen_data_packet(tx_router, rx_ip, tos='lowest-loss')
        tx_router.forward_packet(packet_low_loss)
        packet_bandwidth = gen_data_packet(tx_router, rx_ip,
                                           tos='highest-bandwidth')
        tx_router.forward_packet(packet_bandwidth)


def main(simulation_time=SIMULATION_TIME,
         num_routers=NUM_ROUTERS,
         area=DEFAULT_AREA,
         range1=DEFAULT_RANGE_1,
         range2=DEFAULT_RANGE_2,
         random_seed_prep=DEFAULT_RAND_SEED,
         random_seed_runtime=DEFAULT_RAND_SEED,
         velocity=lambda: 0,
         visualize=True
         ):
    interfaces = [
        {"name": "wifi0", "range": range1, "bandwidth": 8000, "loss": 10},
        {"name": "tetra0", "range": range2, "bandwidth": 1000, "loss": 5}
    ]
    log_directory = os.path.join(os.getcwd(), 'run-data', 'large_static')
    os.makedirs(log_directory, exist_ok=True)
    simulate(log_directory, simulation_time, num_routers, area, interfaces,
             random_seed_prep, random_seed_runtime, velocity, visualize)


if __name__ == '__main__':
    main()
