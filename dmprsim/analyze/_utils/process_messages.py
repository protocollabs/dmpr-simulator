"""
Helper methods to process tracefiles
"""

import argparse
import lzma
import zlib
from pathlib import Path

from dmprsim.analyze._utils.extract_messages import extract_messages


def extract(input_file: Path):
    try:
        _, messages = zip(*extract_messages(input_file))
        return messages
    except ValueError:
        return ()


def message_lengths(input_file: Path):
    messages = extract(input_file)
    return (len(m) for m in messages)


def message_lengths_zlib(input_file: Path):
    messages = extract(input_file)
    return (len(zlib.compress(m.encode('utf-8'))) for m in messages)


def message_lengths_lzma(input_file: Path):
    messages = extract(input_file)
    return (len(lzma.compress(m.encode('utf-8'))) for m in messages)


def process_files(dirs: list, output: Path, action: callable):
    with output.open('w') as f:
        for input_file in dirs:
            f.write('\n'.join(str(i) for i in action(input_file)))
            f.write('\n')


ACTIONS = {
    'len': message_lengths,
    'len-zlib': message_lengths_zlib,
    'len-lzma': message_lengths_lzma,
}


def main():
    parser = argparse.ArgumentParser(description="process a list of tracefiles")
    parser.add_argument('--action', '-a', required=True, choices=ACTIONS.keys(),
                        help='The action to take')
    parser.add_argument('--output', '-o', required=True,
                        help='output file')
    parser.add_argument('input', nargs='+',
                        help='the tracepoint files')
    args = parser.parse_args()

    action = ACTIONS[args.action]
    process_files(args.input, args.output, action)


if __name__ == '__main__':
    main()
