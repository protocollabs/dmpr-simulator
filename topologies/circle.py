import math
import random

import draw
from dmprsim import MobilityArea, MobilityModel
from topologies.utils import GenericTopology


class CircleTopology(GenericTopology):
    NAME = 'circle'
    SIMULATION_TIME = 300
    NUM_ROUTERS = 20
    DEFAULT_RAND_SEED = 1

    def __init__(self,
                 simulation_time=SIMULATION_TIME,
                 num_routers=NUM_ROUTERS,
                 random_seed_prep=DEFAULT_RAND_SEED,
                 random_seed_runtime=DEFAULT_RAND_SEED,
                 visualize=True,
                 simulate_forwarding=True,
                 tracepoints=(),
                 log_directory=None,
                 name=NAME,
                 config={},
                 ):
        super(CircleTopology, self).__init__(
            simulation_time,
            random_seed_runtime,
            simulate_forwarding,
            visualize,
            log_directory,
            tracepoints,
            name,
            config,
        )
        self.num_routers = num_routers
        self.interfaces = [
            {"name": "wifi0", "range": 0, "bandwidth": 8000, "loss": 10},
        ]
        self.random_seed_prep = random_seed_prep

        self.routers = []
        self.tx_router = None
        self.rx_ip = None
        self.area = None

    def prepare(self):
        random.seed(self.random_seed_prep)
        if self.visualize:
            draw.setup_img_folder(self.log_directory)

        # Set all models on a circle
        padding = 50

        size = self.num_routers * 2
        if size < 400:
            size = 400
        radius = size // 2
        size += padding
        self.area = MobilityArea(size, size)

        center = size - padding // 2 - radius
        circumference = math.pi * 2 * radius

        min_range = int(math.ceil(circumference / self.num_routers))
        self.interfaces[0]['range'] = min_range

        models = []
        step = 2 * math.pi / self.num_routers
        for i in range(self.num_routers):
            alpha = i * step
            x = radius * math.cos(alpha) + center
            y = radius * math.sin(alpha) + center
            models.append(MobilityModel(self.area, x=x, y=y))

        self.routers = self._generate_routers(models)

        if self.simulate_forwarding:
            self.tx_router = random.choice(self.routers)
            while True:
                rx_router = random.choice(self.routers)
                if rx_router != self.tx_router:
                    break

            self.tx_router.is_transmitter = True
            rx_router.is_receiver = True
            self.rx_ip = rx_router.pick_random_configured_network()

        return self.routers


if __name__ == '__main__':
    simulation = CircleTopology()
    simulation.prepare()
    for _ in simulation.start():
        pass
