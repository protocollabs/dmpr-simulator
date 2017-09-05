import os.path
import random

import draw
from dmprsim import Router, gen_data_packet


class GenericSimulation:
    def start(self):
        random.seed(self.random_seed_runtime)

        for sec in range(self.simulation_time):
            print(
                "{}\n\ttime: {}/{}".format("=" * 50, sec, self.simulation_time))
            for router in self.routers:
                router.step(sec)

            self._draw(sec)
            self._forward_packet('lowest-loss')
            self._forward_packet('highest-bandwidth')
            yield sec

    def _forward_packet(self, tos):
        if self.simulate_forwarding:
            packet = gen_data_packet(self.tx_router, self.rx_ip, tos=tos)
            self.tx_router.forward_packet(packet)

    def _draw(self, sec):
        if self.visualize:
            class args:
                color_scheme = 'light'

            draw.draw_images(args, self.log_directory, self.area, self.routers,
                             sec)


def generate_routers(interfaces, mobility_models, log_directory):
    routers = []
    for i, model in enumerate(mobility_models):
        ld = os.path.join(log_directory, str(i))
        routers.append(Router(str(i), interfaces, model, ld))
    for router in routers:
        router.register_routers(routers)
        router.connect()
        router.start(0)
    return routers
