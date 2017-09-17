import itertools
import math
import random
from pathlib import Path

from dmprsim.simulator import MobilityArea, MobilityModel
from dmprsim.topologies.utils import GenericTopology


class GridTopology(GenericTopology):
    NAME = 'grid'
    SIMULATION_TIME = 300
    SIZE = 3
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

                 size: int = SIZE,
                 random_seed_prep: int = DEFAULT_RAND_SEED,
                 diagonal: bool = False,
                 range_factor: float = 1,
                 ):
        super(GridTopology, self).__init__(
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
        self.size = size
        self.interfaces = [
            {"name": "wifi0", "range": 0, "bandwidth": 8000, "loss": 10},
        ]
        self.random_seed_prep = random_seed_prep
        self.diagonal = diagonal
        self.range_factor = range_factor

        self.routers = []
        self.tx_router = None
        self.rx_ip = None
        self.area = None

    def prepare(self):
        super(GridTopology, self).prepare()

        random.seed(self.random_seed_prep)

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
        self.interfaces[0]['range'] = range_ * self.range_factor + 1

        models = []
        if self.size == 1:
            size_x, size_y = 2, 1
        else:
            size_x, size_y = self.size, self.size

        for x, y in itertools.product(range(size_x), range(size_y)):
            models.append(MobilityModel(self.area,
                                        x=x * distance + padding,
                                        y=y * distance + padding))

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
    simulation = GridTopology()
    simulation.prepare()
    for _ in simulation.start():
        pass
