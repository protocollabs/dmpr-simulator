import itertools
import math
import os
import random

import draw
from dmprsim import MobilityArea, MobilityModel
from scenarios.utils import generate_routers, GenericSimulation


class SquareScenario(GenericSimulation):
    SIMULATION_TIME = 300
    SIZE = 3
    DEFAULT_RAND_SEED = 1

    def __init__(self,
                 simulation_time=SIMULATION_TIME,
                 size=SIZE,
                 random_seed_prep=DEFAULT_RAND_SEED,
                 random_seed_runtime=DEFAULT_RAND_SEED,
                 visualize=True,
                 simulate_forwarding=True,
                 tracepoints=(),
                 log_directory=None,
                 diagonal=False
                 ):
        self.simulation_time = simulation_time
        self.size = size
        self.interfaces = [
            {"name": "wifi0", "range": 0, "bandwidth": 8000, "loss": 10},
        ]
        self.random_seed_prep = random_seed_prep
        self.random_seed_runtime = random_seed_runtime
        self.visualize = visualize
        self.simulate_forwarding = simulate_forwarding
        self.tracepoints = tracepoints
        self.diagonal = diagonal
        self.log_directory = log_directory

        if log_directory is None:
            self.log_directory = os.path.join(os.getcwd(), 'run-data', 'square')

        self.routers = []
        self.tx_router = None
        self.rx_ip = None
        self.area = None

    def prepare(self):
        random.seed(self.random_seed_prep)
        if self.visualize:
            draw.setup_img_folder(self.log_directory)

        # Set all models on a circle
        padding = 25
        distance = 5

        canvas_size = self.size * distance
        if canvas_size < 400:
            canvas_size = 400
            distance = 400 // self.size
        canvas_size += padding * 2
        self.area = MobilityArea(canvas_size, canvas_size)

        range_ = distance
        if self.diagonal:
            range_ *= math.sqrt(2)
        self.interfaces[0]['range'] = range_ + 1

        models = []
        for x, y in itertools.product(range(self.size), range(self.size)):
            models.append(MobilityModel(self.area,
                                        x=x * distance + padding,
                                        y=y * distance + padding))

        self.routers = generate_routers(self.interfaces, models,
                                        self.log_directory)

        for router in self.routers:
            for tracepoint in self.tracepoints:
                router.tracer.enable(tracepoint)

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
    simulation = SquareScenario(diagonal=True)
    simulation.prepare()
    for _ in simulation.start():
        pass
