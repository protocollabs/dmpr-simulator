import json


def path_in(path, new_paths):
    for n in new_paths:
        if n.startswith(path):
            return True
    return False


def get_nodes(path):
    return path.split('>')[::2]


def compress_paths(msg: str) -> str:
    msg = json.loads(msg)
    if 'routing-data' in msg:
        for policy, nodes in msg.get('routing-data').items():
            paths = [node['path'] for node in nodes.values() if node is not None]
            paths = sorted(paths, key=lambda p: -len(get_nodes(p)))

            new_paths = []

            for path in paths:
                if not path_in(path, new_paths):
                    new_paths.append(path)
            msg['routing-data'][policy] = new_paths

    return json.dumps(msg, separators=(',', ':'))
