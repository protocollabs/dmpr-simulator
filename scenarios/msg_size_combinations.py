import functools
import itertools
import math
import multiprocessing
import os
import pickle
import random

import dmprsim
from core.dmpr.config import DefaultConfiguration as DMPRDefaultConfiguration
from topologies.square import SquareTopology

CHECKPOINT_FILE = 'msg_size_combinations.checkpoint'

EFFECTIVE_SIMULATION_TIME = 1200
SETTLING_TIME_BUFFER = 100

# SIZES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
SIZES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 13, 15)
# The mesh density and their corresponding function for average settling time
MESHES = {
    1: lambda x: (x - 1) * 2,
    math.sqrt(2): lambda x: x,
    2: lambda x: x,
    2 * math.sqrt(2): lambda x: math.ceil(x / 2)
}
LOSSES = (0, 0.01, 0.02, 0.05, 0.1, 0.2)
# FULL_INTERVALS = (0, 1, 2, 3, 4, 5, 7, 9, 11, 13, 15, 20, 25, 30, 35, 40)
FULL_INTERVALS = (0, 1, 2, 3, 4, 5, 7, 9, 11, 13, 15)


class FilterTracer(dmprsim.Tracer):
    def __init__(self, *args, **kwargs):
        self.min_time = kwargs.pop('min_time', float('-inf'))
        super(FilterTracer, self).__init__(*args, **kwargs)

    def log(self, tracepoint, msg, time):
        if time < self.min_time:
            return
        return super(FilterTracer, self).log(tracepoint, msg, time)


def run(data):
    size, mesh, loss, full_interval = data
    name = '{}-{:.2f}-{}-{}'.format(*data)
    log_directory = os.path.join(os.getcwd(), 'run-data', 'message_sizes', name)

    avg_msg_interval = DMPRDefaultConfiguration.rtn_msg_interval + \
                       DMPRDefaultConfiguration.rtn_msg_interval_jitter / 2
    min_prop_path_length = MESHES[mesh](size)
    settling_time = (min_prop_path_length + min_prop_path_length * loss) * \
                    (avg_msg_interval / 2)

    simu_time = EFFECTIVE_SIMULATION_TIME + SETTLING_TIME_BUFFER + settling_time
    simu_time = int(math.ceil(simu_time))
    tracer = functools.partial(FilterTracer,
                               min_time=simu_time - EFFECTIVE_SIMULATION_TIME)

    print("Starting scenario: size {size}x{size} loss {loss:.0%} "
          "density {mesh:.2f} interval {interval} time {time}".format(
        size=size, loss=loss, mesh=mesh, interval=full_interval, time=simu_time
    ))

    sim = SquareTopology(
        simulation_time=simu_time,
        name=name,
        log_directory=log_directory,
        size=size,
        range_factor=mesh,
        config={'max-full-update-interval': full_interval},
        visualize=False,
        simulate_forwarding=False,
        tracepoints=('tx.msg',),
        tracer=tracer,
    )
    sim.interfaces[0]['rx-loss'] = loss
    sim.print = False
    sim.prepare()
    for _ in sim.start():
        pass
    return data


def _save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'wb') as f:
        pickle.dump(data, f)


def apply(cores, data):
    pool = multiprocessing.Pool(cores)
    try:
        with open(CHECKPOINT_FILE, 'rb') as f:
            done = pickle.load(f)
    except FileNotFoundError:
        done = set()

    num = len(data)
    cur = len(done)
    data = data - done
    print('DONE: {:.2%}'.format(cur / num))

    try:
        # sorted with random (i.e. shuffle) because pypy sets are ordered but we
        # want our progress percentage to be representative
        for processed in pool.imap_unordered(
                run,
                sorted(data, key=lambda k: random.random()),
                chunksize=5):
            cur += 1
            print('DONE: {:.2%}'.format(cur / num))
            done.add(processed)
            if cur % 100 == 0:
                _save_checkpoint(done)

        pool.close()
        pool.join()
    finally:
        _save_checkpoint(done)


def main():
    combinations = set(itertools.product(SIZES, MESHES, LOSSES, FULL_INTERVALS))

    very_high_memory = {c for c in combinations if c[0] == 15}
    combinations = combinations - very_high_memory

    high_memory = {c for c in combinations if c[0] >= 13}
    combinations = combinations - high_memory

    mid_memory = {c for c in combinations if c[0] >= 9 and c[1] >= 2}
    low_memory = combinations - mid_memory

    print("low mem")
    apply(8, low_memory)
    print("mid mem")
    apply(4, mid_memory)
    print("high mem")
    apply(2, high_memory)
    print("very high mem")
    apply(1, very_high_memory)


if __name__ == '__main__':
    main()
