"""
Generate one plot per `chartgroup` with `xaxis` as the x-axis and message size
as the y-axis
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np

configs = {
    'density': {
        'datapoints': {
            '1.00': "2 - 4 Neighbors",
            '1.41': "3 - 8 Neighbors",
            '2.00': "5 - 12 Neighbors",
            '2.83': "8 - 16 Neighbors",
        },
        'label': "interface range",
    },
    'loss': {
        'datapoints': {
            '0': "0%",
            '0.01': "1% loss",
            '0.02': "2% loss",
            '0.05': "5% loss",
            '0.1': "10% loss",
            '0.2': "20% loss"
        },
        'label': "Loss",
    },
    'size': {
        'datapoints': {str(i): '{} Nodes'.format(str(i)) for i in range(1, 16)},
        'label': "Network size",
    },
    'interval': {
        'datapoints': {
            str(i): 'Update interval {}'.format(str(i)) for i in
            (0, 1, 2, 3, 4, 5, 7, 9, 11, 13, 15, 20, 25, 30, 35, 40)
        },
        'label': "Full update interval",
    },
}


def readfile(file, x_axis):
    try:
        sizes = np.genfromtxt(file, dtype=int)
        if len(sizes) == 0:
            return False
    except IOError:
        return False
    return (x_axis, np.min(sizes), np.percentile(sizes, 25),
            np.average(sizes), np.percentile(sizes, 75), np.max(sizes))


def plot(chartgroup, group, xaxis, data, output):
    x, mins, perc25, avg, perc75, maxs = zip(*data)
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    ax.set_ylabel('Message Size / bytes')
    ax.set_xlabel(configs[xaxis]['label'])
    ax.set_title(configs[chartgroup]['datapoints'][group])

    # Fill the space between minimum and maximum
    ax.fill_between(x, mins, maxs, color=((0.16, 0.5, 0.725, 0.31),))

    ax.plot(x, maxs, label="maximum")
    ax.plot(x, perc75, label="75% percentile")
    ax.plot(x, avg, label="average")
    ax.plot(x, perc25, label="25% percentile")
    ax.plot(x, mins, label="minimum")

    ax.legend()
    fig.savefig(
        os.path.join(output, '{}-{}-{}.png'.format(chartgroup, group, xaxis)),
        dpi=300
    )


def main(input, output, chartgroup, xaxis):
    os.makedirs(output, exist_ok=True)

    for group in configs[chartgroup]['datapoints']:
        cumulated_data = []
        for datapoint in sorted(configs[xaxis]['datapoints'], key=float):
            source = os.path.join(input, chartgroup, xaxis,
                                  '{}-{}'.format(group, datapoint))
            data = readfile(source, float(datapoint))
            if not data:
                continue
            cumulated_data.append(data)

        if not cumulated_data:
            continue

        plot(chartgroup, group, xaxis, cumulated_data, output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--chartgroup', required=True, choices=configs.keys())
    parser.add_argument('--xaxis', required=True, choices=configs.keys())
    parser.add_argument('--input', required=True)
    args = parser.parse_args()
    main(args.input, args.output, args.chartgroup, args.xaxis)
