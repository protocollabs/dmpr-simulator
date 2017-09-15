import os.path
import random
import subprocess

try:
    from simulator import draw
except ImportError:
    draw = None
from dmprsim.simulator.dmprsim import Router, gen_data_packet


class GenericTopology:
    def __init__(self,
                 simulation_time: int = 100,
                 random_seed_runtime: int = 1,
                 log_directory: str = None,
                 tracepoints: tuple = (),
                 name: str = 'generic',
                 core_config: dict = {},
                 router_args: dict = {},
                 args: object = object(),
                 ):
        self.random_seed_runtime = random_seed_runtime
        self.simulation_time = simulation_time
        self.log_directory = log_directory
        self.tracepoints = tracepoints
        self.name = name
        self.config_override = core_config
        self.router_args = router_args
        self.args = args

        self.simulate_forwarding = getattr(args, 'simulate_forwarding', False)
        self.quiet = getattr(args, 'quiet', False)
        self.gen_images = getattr(args, 'images', False)
        self.gen_movie = getattr(args, 'movie', False)
        if self.gen_movie and not self.gen_images:
            self.gen_images = True

        if log_directory is None:
            self.log_directory = os.path.join(os.getcwd(), 'run-data',
                                              self.name)
            os.makedirs(self.log_directory, exist_ok=True)

        self.tx_router = None
        self.rx_ip = None
        self.area = None
        self.routers = []

    def start(self):
        for tracepoint in self.tracepoints:
            for router in self.routers:
                router.tracer.enable(tracepoint)

        random.seed(self.random_seed_runtime)

        for sec in range(self.simulation_time):
            if not self.quiet:
                print("{}\n\ttime: {}/{}".format("=" * 50, sec,
                                                 self.simulation_time))
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
        if self.gen_images and draw:
            class args:
                color_scheme = 'light'

            draw.draw_images(args, self.log_directory, self.area, self.routers,
                             sec)

    def _generate_routers(self, models):
        return generate_routers(interfaces=self.interfaces,
                                log_directory=self.log_directory,
                                config_override=self.config_override,
                                mobility_models=models,
                                router_args=self.router_args)

    def prepare(self):
        raise NotImplementedError("A scenario needs a prepare method")


def generate_routers(interfaces: list, mobility_models: list,
                     log_directory: str, config_override: dict, router_args={}):
    routers = []
    for i, model in enumerate(mobility_models):
        ld = os.path.join(log_directory, 'routers', str(i))
        routers.append(Router(str(i), interfaces, model, ld,
                              config_override, **router_args))
    for router in routers:
        router.register_routers(routers)
        router.connect()
        router.start(0)
    return routers


def ffmpeg(directory: str):
    source = os.path.join(directory, 'images-range-tx-merge', '*.png')
    dest = os.path.join(directory, 'dmpr.mp4')
    subprocess.call(('ffmpeg',
                     '-framerate', '10',
                     '-pattern_type', 'glob',
                     '-i', source,
                     '-c:v', 'libx264',
                     '-pix_fmt', 'yuv420p',
                     '-y',
                     dest))
