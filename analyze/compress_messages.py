"""
Compress a list of messages
"""

import argparse
import zlib
import lzma
import pickle
import os

COMPRESS = {
    'zlib': zlib.compress,
    'lzma': lzma.compress,
}


def main():
    parser = argparse.ArgumentParser(description="compress all messages")
    parser.add_argument('--type', '-t', default='zlib',
                        help='the compression method, default: zlib',
                        choices=('zlib', 'lzma'))
    parser.add_argument('input',
                        help='the input file, one message per line')
    parser.add_argument('output',
                        help='the output file, a pickled list')
    args = parser.parse_args()

    compress = COMPRESS[args.type]

    size = os.path.getsize(args.input)
    processed = 0
    compressed_msg = []
    with open(args.input) as f:
        for line in f:
            print("{:.2%}".format(processed / size), end='\r')
            processed += len(line)
            compressed_msg.append(compress(line.encode('utf-8')))

    with open(args.output, 'wb') as output_file:
        pickle.dump(compressed_msg, output_file)


if __name__ == '__main__':
    main()
