import random
from pathlib import Path

from dmprsim.simulator import MobilityArea, MovingMobilityModel
from dmprsim.topologies.utils import GenericTopology


class RandomTopology(GenericTopology):
    NAME = 'randomized'
    SIMULATION_TIME = 1000
    NUM_ROUTERS = 200
    DEFAULT_AREA = (1000, 1000)
    DEFAULT_RAND_SEED = 1
    DEFAULT_INTERFACES = [
        {
            "name": "wifi0",
            "range": 50,
            "core-config": {"bandwidth": 8000, "loss": 10},
        },
        {
            "name": "tetra0",
            "range": 100,
            "core-config": {"bandwidth": 1000, "loss": 5},
        },
    ]

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
                 area: tuple = DEFAULT_AREA,
                 interfaces: list = DEFAULT_INTERFACES,
                 random_seed_prep: int = DEFAULT_RAND_SEED,
                 velocity=lambda: 0,
                 disappearance_pattern: tuple = (0, 0, 0),
                 ):
        super(RandomTopology, self).__init__(
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
        self.area = MobilityArea(*area)
        self.interfaces = interfaces
        self.random_seed_prep = random_seed_prep
        self.velocity = velocity
        self.disappearance_pattern = disappearance_pattern

    def prepare(self):
        super(RandomTopology, self).prepare()

        random.seed(self.random_seed_prep)

        self.models = (MovingMobilityModel(self.area,
                                           velocity=self.velocity,
                                           disappearance_pattern=self.disappearance_pattern)
                       for _ in range(self.num_routers))

        self._generate_routers(self.models)

        self._set_random_tx_rx_routers()

        return self.models


if __name__ == '__main__':
    simulation = RandomTopology()
    simulation.prepare()
    for _ in simulation.start():
        pass
