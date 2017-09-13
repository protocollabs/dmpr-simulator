import itertools
import math
import multiprocessing
import os
import pickle

from topologies.square import SquareTopology

CHECKPOINT_FILE = 'size_combinations.checkpoint'

SIMU_TIME = 1200

SIZES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
MESHES = (1, math.sqrt(2), 2, 2 * math.sqrt(2))
LOSSES = (0, 0.01, 0.02, 0.05, 0.1, 0.2)
FULL_INTERVALS = (0, 1, 2, 3, 4, 5, 7, 9, 11, 13, 15, 20, 25, 30, 35, 40)


def run(data):
    size, mesh, loss, full_interval = data
    name = '{}-{:.2f}-{}-{}'.format(*data)
    log_directory = os.path.join(os.getcwd(), 'run-data', 'message_sizes', name)
    sim = SquareTopology(
        simulation_time=SIMU_TIME,
        name=name,
        log_directory=log_directory,
        size=size,
        range_factor=mesh,
        config={'max-full-update-interval': full_interval},
        visualize=False,
        simulate_forwarding=False,
        tracepoints=('tx.msg',),
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

    try:
        for processed in pool.imap_unordered(run, data, chunksize=5):
            cur += 1
            print('{:.2%}'.format(cur / num), end='\r')
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

    mid_memory = {c for c in combinations if c[0] >= 10 and c[1] >= 2}
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
