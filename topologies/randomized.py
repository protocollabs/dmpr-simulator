import random

try:
    import draw
except ImportError:
    draw = None
from dmprsim import MobilityArea, MobilityModel
from topologies.utils import GenericTopology


class RandomTopology(GenericTopology):
    NAME = 'randomized'
    SIMULATION_TIME = 1000
    NUM_ROUTERS = 200
    DEFAULT_AREA = (1000, 1000)
    DEFAULT_RAND_SEED = 1
    DEFAULT_INTERFACES = [
        {"name": "wifi0", "range": 50, "bandwidth": 8000, "loss": 10},
        {"name": "tetra0", "range": 100, "bandwidth": 1000, "loss": 5}
    ]

    def __init__(self,
                 simulation_time=SIMULATION_TIME,
                 num_routers=NUM_ROUTERS,
                 area=DEFAULT_AREA,
                 interfaces=DEFAULT_INTERFACES,
                 random_seed_prep=DEFAULT_RAND_SEED,
                 random_seed_runtime=DEFAULT_RAND_SEED,
                 velocity=lambda: 0,
                 visualize=True,
                 simulate_forwarding=True,
                 disappearance_pattern=(0, 0, 0),
                 tracepoints=(),
                 log_directory=None,
                 name=NAME,
                 config={},
                 ):
        super(RandomTopology, self).__init__(
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
        self.area = MobilityArea(*area)
        self.interfaces = interfaces
        self.random_seed_prep = random_seed_prep
        self.velocity = velocity
        self.disappearance_pattern = disappearance_pattern

    def prepare(self):
        random.seed(self.random_seed_prep)

        if self.visualize and draw:
            draw.setup_img_folder(self.log_directory)

        models = (MobilityModel(self.area,
                                velocity=self.velocity,
                                disappearance_pattern=self.disappearance_pattern)
                  for _ in range(self.num_routers))

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
    simulation = RandomTopology()
    simulation.prepare()
    for _ in simulation.start():
        pass
