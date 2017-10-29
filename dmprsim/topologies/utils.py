import os
import logging
import random
import subprocess
from pathlib import Path

try:
    from dmprsim.simulator import draw
except ImportError:
    draw = None
from dmprsim.simulator import Router

from dmprsim.simulator.middlewares import MiddlewareController, RouterTransmittedMiddleware, RouterForwardedPacketMiddleware

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
        self.models = []
        self.interfaces = []

    def prepare(self):
        if self.gen_images and draw:
            draw.setup_img_folder(self.scenario_dir)
            MiddlewareController.activate(RouterForwardedPacketMiddleware())
            MiddlewareController.activate(RouterTransmittedMiddleware())

    def start(self):
        for tracepoint in self.tracepoints:
            for model in self.models:
                model.router.tracer.enable(tracepoint)

        self.area.start()

        random.seed(self.random_seed_runtime)

        for sec in range(self.simulation_time):
            if not self.quiet:
                logger.info("{}\n\ttime: {}/{}".format("=" * 50, sec,
                                                       self.simulation_time))
            self.area.step(sec)

            self._forward_packet('lowest-loss')
            self._forward_packet('highest-bandwidth')

            self._draw(sec)
            yield sec
            RouterTransmittedMiddleware.reset()
            RouterForwardedPacketMiddleware.reset()

    def _set_random_tx_rx_routers(self):
        if self.simulate_forwarding:
            tx_model, rx_model = random.sample(self.models, 2)
            self.tx_router = tx_model.router
            self.tx_router.is_transmitter = True
            rx_model.router.is_receiver = True
            self.rx_ip = rx_model.router.get_random_network()

    def _forward_packet(self, tos):
        if self.simulate_forwarding:
            self.tx_router.send_packet(self.rx_ip, tos)

    def _draw(self, sec):
        if self.gen_images and draw:
            draw.draw_images(self.args, self.scenario_dir, self.area, sec)

    def _generate_routers(self, models):
        generate_routers(interfaces=self.interfaces,
                         log_directory=self.scenario_dir,
                         config_override=self.config_override,
                         mobility_models=models,
                         router_args=self.router_args)


def generate_routers(interfaces: list, mobility_models: list,
                     log_directory: Path, config_override: dict,
                     router_args={}):
    for i, model in enumerate(mobility_models):
        ld = log_directory / 'routers' / str(i)
        Router(str(i),
               interfaces=interfaces,
               model=model,
               log_directory=ld,
               config_override=config_override,
               **router_args)


def ffmpeg(result_path: Path, scenario_path: Path):
    source = scenario_path / 'images' / '*.png'
    dest = os.path.join(str(result_path), 'dmpr.mp4')
    cmd = ('ffmpeg',
           '-framerate', '10',
           '-pattern_type', 'glob',
           '-i', str(source),
           '-c:v', 'libx264',
           '-pix_fmt', 'yuv420p',
           '-y',
           dest)
    logger.info("now generating video: \"\"".format(" ".join(cmd)))
    subprocess.call(cmd)

    if os.path.isfile(dest):
        logger.info("Generated movie at {}".format(dest))
    else:
        logger.info("Generated movie failed! Please take a look "
                    "output and fill a bug report")
