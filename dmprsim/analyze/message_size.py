"""
Generate one plot per `chartgroup` with `xaxis` as the x-axis and message size
as the y-axis
"""

import logging
import shutil
from pathlib import Path
from typing import Union

import matplotlib

matplotlib.use('AGG')
import matplotlib.pyplot as plt

matplotlib.style.use('ggplot')

import numpy as np

from dmprsim.analyze._utils.process_messages import ACTIONS as process_actions, \
    process_files
from dmprsim.scenarios.message_size import MessageSizeScenario

configs = {
    'density': {
        'label': "Interface Range",
        'datapoints': {
            1: "2 - 4 Neighbors",
            2: "3 - 8 Neighbors",
            4: "5 - 12 Neighbors",
            5: "7 - 20 Neighbors",
            8: "8 - 24 Neighbors",
        },
    },
    'loss': {
        'label': "Loss",
        'datapoints': {
            0: "0%",
            1: "1% loss",
            2: "2% loss",
            5: "5% loss",
            10: "10% loss",
            20: "20% loss",
        },
    },
    'size': {
        'label': "Network size",
        'datapoints': {
            i: "{} Nodes".format(i) for i in (
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            11,
            13,
            15,
        )},
    },
    'interval': {
        'label': "Full update interval",
        'datapoints': {
            i: "Update interval {}".format(i) for i in (
            0,
            1,
            2,
            3,
            4,
            5,
            7,
            9,
            11,
            13,
            15,
        )},
    },
}

# compression options: 'none', 'zlib', 'lzma
PLOTS = {
    'density': (
        ('size', {'interval': '*', 'loss': '*', 'compression': 'zlib'}),
        ('interval', {'loss': '*', 'size': '*', 'compression': 'zlib'}),
    ),
    'loss': (
        ('interval', {'density': '*', 'size': '*', 'compression': 'zlib'}),
    ),
}

logger = logging.getLogger(__name__)


def accumulate(input: Path, globs: dict, filename: str,
               xaxis_datapoint: int) -> Union[tuple, bool]:
    """
    for `glob`/filename in input directory, accumulate the message lengths
    and return a tuple with (x, min, perc25, avg, perc75, max)
    """
    files = '{size}-{density}-{loss}-{interval}/{filename}'.format(
        filename=filename, **globs)
    input_paths = input.glob(files)

    message_lengths = ''
    for file in input_paths:
        try:
            with file.open() as fin:
                message_lengths += fin.read()
        except FileNotFoundError as e:
            logger.debug("Could not find file, skipping {}".format(e))
            continue

    sizes = np.asarray([int(i) for i in message_lengths.splitlines() if i])
    if len(sizes) == 0:
        logger.debug("File lengths of {} is zero, skipping".format(files))
        return False

    return (xaxis_datapoint, np.min(sizes), np.percentile(sizes, 25),
            np.average(sizes), np.percentile(sizes, 75), np.max(sizes))


def plot(chartgroup: str, chartgroup_datapoint: int, xaxis: str, data: list,
         output: Path):
    """
    plot the data with a defined chartgroup and xaxis with title, labels and
    a legend into the output directory with the filename
    chartgroup-chartgroup_datapoint-xaxis
    """
    x, mins, perc25, avg, perc75, maxs = zip(*data)
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    ax.set_ylabel('Message Size / bytes')
    ax.set_xlabel(configs[xaxis]['label'])
    ax.set_title(configs[chartgroup]['datapoints'][chartgroup_datapoint])

    # Fill the space between minimum and maximum
    ax.fill_between(x, mins, maxs, color=((0.16, 0.5, 0.725, 0.31),))

    ax.plot(x, maxs, label="Maximum")
    ax.plot(x, perc75, label="75% Percentile")
    ax.plot(x, avg, label="Average")
    ax.plot(x, perc25, label="25% Percentile")
    ax.plot(x, mins, label="Minimum")

    ax.legend()
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        str(output / "{}-{}-{}.png".format(chartgroup, chartgroup_datapoint,
                                           xaxis)),
        dpi=300
    )


def generate_plots(input: Path, output: Path, filename: str, chartgroup: str,
                   xaxis: str, globs: dict):
    # Generate a separate chart for each datapoint in chartgroup
    for chartgroup_datapoint in configs[chartgroup]['datapoints']:
        globs[chartgroup] = chartgroup_datapoint
        cumulated_data = []

        # Parse all datafiles for the specified x-axis
        for xaxis_datapoint in configs[xaxis]['datapoints']:
            globs[xaxis] = xaxis_datapoint
            data = accumulate(input, globs, filename, xaxis_datapoint)
            if not data:
                continue
            cumulated_data.append(data)

        if not cumulated_data:
            logger.debug(
                "no data for {}-{}, skippint".format(chartgroup_datapoint,
                                                     xaxis))
            continue

        plot(chartgroup, chartgroup_datapoint, xaxis, cumulated_data, output)


def run_scenario(args: object, results_dir: Path, scenario_dir: Path):
    scenario = MessageSizeScenario(
        args,
        results_dir,
        scenario_dir,
        sizes=configs['size']['datapoints'].keys(),
        meshes=configs['density']['datapoints'].keys(),
        losses=configs['loss']['datapoints'].keys(),
        intervals=configs['interval']['datapoints'].keys(),
    )
    scenario.start()


def process_messages(path: Path, compression):
    dirs = path.glob('*-*-*-*')
    for dir in dirs:
        process_files(dir.glob('routers/*/trace/tx.msg'), dir / compression,
                      process_actions[compression])


def main(args: object, results_dir: Path, scenario_dir: Path):
    if not (scenario_dir / '.done').exists():
        run_scenario(args, results_dir, scenario_dir)

    logger.info("Start plotting")
    for chartgroup in PLOTS:
        for xaxis, conf in PLOTS[chartgroup]:
            compression = conf['compression']
            len_file = 'len-' + compression
            done_file = scenario_dir / ('.done-' + compression)
            if not done_file.exists():
                process_messages(scenario_dir, len_file)
                done_file.touch()
            generate_plots(input=scenario_dir, output=results_dir,
                           filename=len_file, chartgroup=chartgroup,
                           xaxis=xaxis, globs=conf.copy())
