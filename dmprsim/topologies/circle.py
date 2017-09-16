import math
import random
from pathlib import Path

from dmprsim.simulator.dmprsim import MobilityArea, MobilityModel
from dmprsim.topologies.utils import GenericTopology


class CircleTopology(GenericTopology):
    NAME = 'circle'
    SIMULATION_TIME = 300
    NUM_ROUTERS = 20
    DEFAULT_RAND_SEED = 1

    def __init__(self,
                 simulation_time: int = SIMULATION_TIME,
                 random_seed_runtime: int = DEFAULT_RAND_SEED,
                 scenario_dir: Path = None,
                 results_dir: Path = None,
                 tracepoints: tuple = (),
                 name: str = NAME,
                 core_config: dict = {},
                 router_args: dict = {},
                 args: object = object(),
                 num_routers: int = NUM_ROUTERS,
                 random_seed_prep: int = DEFAULT_RAND_SEED,
                 ):
        super(CircleTopology, self).__init__(
            simulation_time=simulation_time,
            random_seed_runtime=random_seed_runtime,
            scenario_dir=scenario_dir,
            results_dir=results_dir,
            tracepoints=tracepoints,
            name=name,
            core_config=core_config,
            router_args=router_args,
            args=args,
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
        super(CircleTopology, self).prepare()

        random.seed(self.random_seed_prep)

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
