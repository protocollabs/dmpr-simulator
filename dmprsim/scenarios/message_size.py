import functools
import itertools
import logging
import math
import multiprocessing
import pickle
import random
from pathlib import Path

from dmprsim.simulator import dmprsim
from dmprsim.topologies.grid import GridTopology
from ..core.dmpr.config import DefaultConfiguration as DMPRDefaultConfiguration

CHECKPOINT_FILE = '.message_sizes.checkpoint'

AVG_MSG_INTERVAL = DMPRDefaultConfiguration.rtn_msg_interval + \
                   DMPRDefaultConfiguration.rtn_msg_interval_jitter / 2

EFFECTIVE_SIMULATION_TIME = 1200
SETTLING_TIME_BUFFER = 100

logger = logging.getLogger(__name__)


class FilterTracer(dmprsim.Tracer):
    def __init__(self, *args, **kwargs):
        self.min_time = kwargs.pop('min_time', float('-inf'))
        super(FilterTracer, self).__init__(*args, **kwargs)

    def log(self, tracepoint, msg, time):
        if time < self.min_time:
            return
        return super(FilterTracer, self).log(tracepoint, msg, time)


class MessageSizeScenario(object):
    def __init__(self, args: object, dir: Path, sizes, meshes, losses,
                 intervals):
        self.args = args
        self.log_directory = dir
        self.checkpoint_file = self.log_directory / CHECKPOINT_FILE

        self.combinations = set(
            itertools.product(sizes, meshes, losses, intervals))
        self.all = self.combinations.copy()

    def start(self):
        very_high_memory = {c for c in self.combinations if c[0] == 15}
        combinations = self.combinations - very_high_memory

        high_memory = {c for c in combinations if c[0] >= 13}
        combinations = combinations - high_memory

        mid_memory = {c for c in combinations if c[0] >= 9 and c[1] >= 2}
        low_memory = combinations - mid_memory

        ram = getattr(self.args, 'max_ram', 16)
        if ram < 2:
            print("Need at least 16 GB")
            exit(1)

        logger.info("Starting low memory scenarios, ~2GB each")
        self._apply(math.floor(ram / 2), low_memory)
        logger.info("Starting mid memory scenarios, ~4GB each")
        self._apply(math.floor(ram / 2), mid_memory)
        logger.info("Starting high memory scenarios, ~8GB each")
        self._apply(math.floor(ram / 2), high_memory)
        logger.info("Starting very high memory scenarios, ~12GB each")
        self._apply(math.floor(ram / 2), very_high_memory)

        (self.log_directory / '.done').touch()
        logger.info("Scenarios done")

    def _save_checkpoint(self, data):
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with self.checkpoint_file.open('wb') as f:
            pickle.dump(data, f)

    def _apply(self, cores, data):
        pool = multiprocessing.Pool(cores)
        try:
            with self.checkpoint_file.open('rb') as f:
                done = pickle.load(f)
        except FileNotFoundError:
            done = set()

        cur = len(done)
        num = len(self.all)
        data = data - done

        try:
            # sorted with random (i.e. shuffle) because pypy sets are ordered
            # but we want our progress percentage to be representative
            for processed in pool.imap_unordered(
                    self._run,
                    sorted(data, key=lambda k: random.random()),
                    chunksize=5):
                cur += 1
                logger.info('DONE: {:.2%}'.format(cur / num))
                done.add(processed)
                if cur % 100 == 0:
                    self._save_checkpoint(done)

            pool.close()
            pool.join()
        finally:
            self._save_checkpoint(done)

    def _run(self, data):
        size, mesh, loss, full_interval = data
        name = '{}-{}-{}-{}'.format(*data)
        log_directory = self.log_directory / name
        mesh = math.sqrt(mesh)
        loss /= 100

        if size == 1:
            min_prop_path_length = 2 * size
        else:
            min_prop_path_length = size

        settling_time = (min_prop_path_length + min_prop_path_length * loss) * \
                        (AVG_MSG_INTERVAL / 2)
        simu_time = EFFECTIVE_SIMULATION_TIME + SETTLING_TIME_BUFFER + \
                    settling_time
        simu_time = int(math.ceil(simu_time))
        min_trace_time = simu_time - EFFECTIVE_SIMULATION_TIME

        tracer = functools.partial(FilterTracer, min_time=min_trace_time)

        logger.info("Starting scenario: size {size}x{size} loss {loss:.0%} "
                    "density {mesh:.2f} interval {interval} time {time}".format(
            size=size, loss=loss, mesh=mesh, interval=full_interval,
            time=simu_time))

        sim = GridTopology(
            simulation_time=simu_time,
            name=name,
            log_directory=log_directory,
            size=size,
            range_factor=math.sqrt(mesh),
            core_config={'max-full-update-interval': full_interval},
            tracepoints=('tx.msg',),
            router_args={'tracer': tracer},
            args=self.args,
        )
        sim.quiet = not getattr(self.args, 'verbose', False)
        sim.interfaces[0]['rx-loss'] = loss
        sim.prepare()
        for _ in sim.start():
            pass
        return data
