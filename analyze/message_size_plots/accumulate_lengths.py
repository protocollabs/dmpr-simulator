"""
Accumulate all message lengths for specific configurations
"""
import argparse
import glob
import os

from analyze.message_size_plots.msg_size_plots import configs


def main(input, output, ext, first, second, globs):
    output_dir = os.path.join(output, first, second)
    os.makedirs(output_dir, exist_ok=True)

    for first_datapoint in configs[first]['datapoints']:
        globs[first] = first_datapoint

        for second_datapoint in configs[second]['datapoints']:
            globs[second] = second_datapoint
            filename = '{size}-{density}-{loss}-{interval}'.format(**globs)
            input_path = os.path.join(input, filename, ext)
            input_paths = glob.glob(input_path)
            output_path = os.path.join(output_dir,
                                       '{}-{}'.format(first_datapoint,
                                                      second_datapoint))

            with open(output_path, 'w') as fout:
                for i in input_paths:
                    with open(i) as fin:
                        fout.write(fin.read())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for i in configs:
        parser.add_argument('--{}'.format(i), default='*')
    parser.add_argument('--input', required=True)
    parser.add_argument('--filename', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    args = parser.parse_args()
    globs = {}
    for c in configs:
        if c not in (args.first, args.second):
            globs[c] = getattr(args, c)
    main(args.input, args.output, args.filename, args.first, args.second, globs)
