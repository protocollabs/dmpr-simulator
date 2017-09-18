"""
Helper methods to process tracefiles
"""

import argparse
import lzma
import zlib
from pathlib import Path

from dmprsim.analyze._utils.compress_path import compress_paths
from dmprsim.analyze._utils.extract_messages import extract_messages


def extract(input_file: Path):
    try:
        _, messages = zip(*extract_messages(input_file))
        return messages
    except ValueError:
        return ()


def message_lengths(messages: list):
    return (len(m) for m in messages)


def messages_zlib(messages: list):
    return (zlib.compress(m.encode('utf-8')) for m in messages)


def messages_lzma(messages: list):
    return (lzma.compress(m.encode('utf-8')) for m in messages)


def reduce_paths(messages: list):
    return (compress_paths(m) for m in messages)


ACTIONS = {
    'len': message_lengths,
    'zlib': messages_zlib,
    'lzma': messages_lzma,
    'reduce': reduce_paths,
}


def process_files(dirs: list, output: Path, actions: list):
    with output.open('w') as f:
        for input_file in dirs:
            messages = extract(input_file)
            for action in actions:
                messages = ACTIONS[action](messages)
            f.write('\n'.join(str(i) for i in messages))
            f.write('\n')


def main():
    parser = argparse.ArgumentParser(description="process a list of tracefiles")
    parser.add_argument('--action', '-a', required=True,
                        help='The actions to take')
    parser.add_argument('--output', '-o', required=True,
                        help='output file')
    parser.add_argument('input', nargs='+',
                        help='the tracepoint files')
    args = parser.parse_args()

    actions = [action.strip() for action in args.action.split(',')]
    process_files(args.input, args.output, actions)


if __name__ == '__main__':
    main()
