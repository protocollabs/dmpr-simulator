"""
Count duplicate paths in a message
"""

import json
import sys


def count_dupl(m: dict):
    if 'routing-data' not in m:
        return
    paths = []
    for policy, p in m['routing-data'].items():
        for node, path in p.items():
            paths.append(path['path'])

    num_paths = len(paths)
    num_dupl = num_paths - len(set(paths))
    return num_paths, num_dupl


def main():
    with open(sys.argv[1]) as f:
        messages = list(f)

    dupls = set()
    for m in messages:
        dupls.add(count_dupl(json.loads(m)))
    if None in dupls:
        dupls.remove(None)
    for num_paths, num_dupl in sorted(dupls, key=lambda x: x[0]):
        print('{} | {} | {:.2%}'.format(num_paths, num_dupl,
                                        num_dupl / num_paths))


if __name__ == '__main__':
    main()
