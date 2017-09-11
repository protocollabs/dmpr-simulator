"""
Generates a histogram of different message types,
requires tx.msg tracepoint, designed for scenarios/compare_partial_full.py
"""
import argparse
import json
import os
from zlib import compress

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.style.use('ggplot')


class MessageSizeAccumulator(object):
    def __init__(self):
        self.json = []
        self.json_compressed = []

    def add_msg(self, msg):
        msg = json.dumps(json.loads(msg), sort_keys=True, separators=(',', ':'))
        self.json.append(len(msg))
        self.json_compressed.append(len(compress(msg.encode('utf-8'))))


def main():
    parser = argparse.ArgumentParser(
        description="Generate message size histograms")
    parser.add_argument('dir', help='the scenario output directories')
    args = parser.parse_args()

    full_acc = MessageSizeAccumulator()
    partial_acc = MessageSizeAccumulator()

    configs = os.listdir(args.dir)
    for config in sorted(configs):
        print("processing " + config)
        if config.endswith('partial-0'):
            acc = full_acc
        else:
            acc = partial_acc

        router_dir = os.path.join(args.dir, config, 'routers')
        for router in os.listdir(router_dir):
            with open(os.path.join(router_dir, router, 'trace', 'tx.msg')) as f:
                for line in f:
                    msg = ''.join(line.split()[1:])
                    acc.add_msg(msg)

    pd.DataFrame({
        'full': pd.Series(full_acc.json),
        'full_compressed': pd.Series(full_acc.json_compressed),
        'partial': pd.Series(partial_acc.json),
        'partial_compressed': pd.Series(partial_acc.json_compressed),
    }, columns=['full', 'full_compressed', 'partial', 'partial_compressed']
    ).plot.hist(bins=30)
    plt.show()


if __name__ == '__main__':
    main()
