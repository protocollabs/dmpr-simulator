import logging
import random
import subprocess
from pathlib import Path

try:
    from dmprsim.simulator import draw
except ImportError:
    draw = None
from dmprsim.simulator import Router, gen_data_packet

logger = logging.getLogger(__name__)


class GenericTopology:
    def __init__(self,
                 simulation_time: int = 100,
                 random_seed_runtime: int = 1,
                 scenario_dir: Path = None,
                 results_dir: Path = None,
                 tracepoints: tuple = (),
                 name: str = 'generic',
                 core_config: dict = {},
                 router_args: dict = {},
                 args: object = object(),
                 ):
        self.random_seed_runtime = random_seed_runtime
        self.simulation_time = simulation_time
        self.scenario_dir = scenario_dir
        self.results_dir = results_dir
        self.tracepoints = tracepoints
        self.name = name
        self.config_override = core_config
        self.router_args = router_args
        self.args = args

        self.simulate_forwarding = getattr(args, 'simulate_forwarding', False)
        self.quiet = getattr(args, 'quiet', False)
        self.gen_images = getattr(args, 'enable_images', False)
        self.gen_movie = getattr(args, 'enable_video', False)
        if self.gen_movie and not self.gen_images:
            self.gen_images = True

        if draw is None:
            logger.warning("Could not import pil and cairo, skipping image and "
                           "video generation")
            self.gen_movie = False
            self.gen_images = False

        if scenario_dir is None:
            self.scenario_dir = Path.cwd() / 'run-data' / self.name

        try:
            self.scenario_dir.mkdir(parents=True)
        except FileExistsError:
            pass

        self.tx_router = None
        self.rx_ip = None
        self.area = None
        self.routers = []

    def prepare(self):
        if self.gen_images and draw:
            draw.setup_img_folder(self.scenario_dir)

    def start(self):
        for tracepoint in self.tracepoints:
            for router in self.routers:
                router.tracer.enable(tracepoint)

        random.seed(self.random_seed_runtime)

        for sec in range(self.simulation_time):
            if not self.quiet:
                logger.info("{}\n\ttime: {}/{}".format("=" * 50, sec,
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
            draw.draw_images(self.args, self.scenario_dir, self.area,
                             self.routers, sec)

    def _generate_routers(self, models):
        return generate_routers(interfaces=self.interfaces,
                                log_directory=self.scenario_dir,
                                config_override=self.config_override,
                                mobility_models=models,
                                router_args=self.router_args)


def generate_routers(interfaces: list, mobility_models: list,
                     log_directory: Path, config_override: dict,
                     router_args={}):
    routers = []
    for i, model in enumerate(mobility_models):
        ld = log_directory / 'routers' / str(i)
        routers.append(Router(str(i), interfaces, model, ld,
                              config_override, **router_args))
    for router in routers:
        router.register_routers(routers)
        router.connect()
        router.start(0)
    return routers


def ffmpeg(result_path: Path, scenario_path: Path):
    source = scenario_path / 'images' / '*.png'
    dest = result_path / 'dmpr.mp4'
    logger.info("Generating movie at {}".format(dest))

    subprocess.call(('ffmpeg',
                     '-framerate', '10',
                     '-pattern_type', 'glob',
                     '-i', str(source),
                     '-c:v', 'libx264',
                     '-pix_fmt', 'yuv420p',
                     '-y',
                     str(dest)))
