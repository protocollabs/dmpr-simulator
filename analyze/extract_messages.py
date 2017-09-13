import argparse
import os


def all_tracepoints(input_dirs, tracepoint):
    for dir in input_dirs:
        for router in os.listdir(os.path.join(dir, 'routers')):
            yield os.path.join(dir, 'routers', router, 'trace', tracepoint)


def extract_messages(tracefile):
    messages = []
    try:
        with open(tracefile) as f:
            for line in f:
                msg = ' '.join(line.split()[1:])
                messages.append(msg)
    except FileNotFoundError:
        pass
    return messages


def main():
    parser = argparse.ArgumentParser(
        description="extract all messages from a tracepoint")
    parser.add_argument('--output', '-o', required=True, help="output file")
    parser.add_argument('--tracepoint', '-t', default='tx.msg',
                        help='The tracepoint to extract')
    parser.add_argument('input', nargs='+',
                        help='The input directories, the script expects to '
                             'find the tracepoints under '
                             '<input>/routers/<router>/trace/<tracepoint>')

    args = parser.parse_args()

    with open(args.output, 'w') as out:
        for tracefile in all_tracepoints(args.input, args.tracepoint):
            messages = extract_messages(tracefile)
            out.write('\n'.join(messages) + '\n')


if __name__ == '__main__':
    main()
