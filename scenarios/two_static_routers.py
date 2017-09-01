import os
import random

from dmprsim import Router, MobilityArea, StaticMobilityModel, gen_data_packet
from scenarios.utils import generate_routers

interfaces = [
    {"name": "wifi0", "range": 200, "bandwidth": 8000, "loss": 10},
    {"name": "tetra0", "range": 350, "bandwidth": 1000, "loss": 5}
]

SIMULATION_TIME = 500


def simulate(log_directory):
    area = MobilityArea(600, 500)

    model1 = StaticMobilityModel(area, 200, 250)
    model2 = StaticMobilityModel(area, 400, 250)

    routers = generate_routers(interfaces, (model1, model2), log_directory)

    src_router = routers[0]
    dst_router = routers[1]
    dst_ip = dst_router.pick_random_configured_network()

    for sec in range(SIMULATION_TIME):
        print("{}\n\ttime: {}/{}".format("="*50, sec, SIMULATION_TIME))
        for router in routers:
            router.step(sec)

        # draw.draw_images(args, log_directory, area, routers, sec)
        packet_low_loss = gen_data_packet(src_router, dst_ip, 'lowest-loss')
        src_router.forward_packet(packet_low_loss)

def main():
    log_directory = os.path.join(os.getcwd(), 'two_static')
    os.makedirs(log_directory, exist_ok=True)
    simulate(log_directory)


if __name__ == '__main__':
    main()
