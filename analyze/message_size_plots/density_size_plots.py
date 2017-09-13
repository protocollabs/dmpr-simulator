"""
Generate one plot per density with x-axis: network size and y-axis: message size
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np

DENSITIES = {
    '1.00': "2 - 4 Neighbors",
    '1.41': "3 - 8 Neighbors",
    '2.00': "5 - 12 Neighbors",
    '2.83': "8 - 16 Neighbors",
}


def readfile(file, size):
    if size == 1:
        size = 2
    else:
        size **= 2

    sizes = np.genfromtxt(file, dtype=int)
    if len(sizes) == 0:
        return False
    return (size, np.min(sizes), np.percentile(sizes, 25),
            np.average(sizes), np.percentile(sizes, 75), np.max(sizes))


def plot(density, data, filename):
    sizes, mins, perc25, avg, perc75, maxs = zip(*data)
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlabel('Network Size / nodes')
    ax.set_ylabel('Message Size / bytes')
    ax.set_title(DENSITIES[density])

    # Fill the space between minimum and maximum
    ax.fill_between(sizes, mins, maxs, color=((0.16, 0.5, 0.725, 0.31),))

    ax.plot(sizes, maxs, label="maximum")
    ax.plot(sizes, perc75, label="75% percentile")
    ax.plot(sizes, avg, label="average")
    ax.plot(sizes, perc25, label="25% percentile")
    ax.plot(sizes, mins, label="minimum")

    ax.legend()

    fig.savefig(filename, dpi=300)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', '-o', required=True)
    parser.add_argument('path')
    args = parser.parse_args()
    for density in DENSITIES:
        cumulated_data = []
        for size in range(1, 16):
            path = os.path.join(args.path, 'density-{}'.format(density))
            os.makedirs(path, exist_ok=True)
            data = readfile(os.path.join(path, str(size)), size)
            if not data:
                continue

            cumulated_data.append(data)

        plot(density, cumulated_data, '{}-{}.png'.format(args.output, density))


if __name__ == '__main__':
    main()
