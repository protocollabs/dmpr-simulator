"""
Draw a sequence diagram of all transmitted messages,
requires rx.msg.valid tracepoint
"""
import argparse
import json
import os

from seqdiag import drawer, builder, parser as seq_parser

skel = """
   seqdiag {{
      activation = none;
      {}
   }}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate sequence diagrams")
    parser.add_argument('--type', default='SVG',
                        help='could be SVG, PNG, default: SVG')
    parser.add_argument('dir', help='the scenario output directory')
    parser.add_argument('output', help='the output filename')
    args = parser.parse_args()

    routers_dir = os.path.join(args.dir, 'routers')
    routers = os.listdir(routers_dir)
    messages = {}
    for router in routers:
        with open(os.path.join(routers_dir, router, 'trace',
                               'rx.msg.valid')) as f:
            for line in f:
                time = line.split()[0]
                msg = ''.join(line.split()[1:])
                messages.setdefault(time, []).append((router, msg))

    diag = []
    diag_skel = '{sender} -> {receiver} [label="{time}\n{type}\n{data}"]'
    for time in sorted(messages, key=float):
        for receiver, message in messages[time]:
            message = json.loads(message)
            sender = message['id']
            type = message['type']
            data = []
            if 'routing-data' in message:
                for policy in message['routing-data']:
                    for node, path in message['routing-data'][policy].items():
                        if path is not None:
                            path = path['path']
                        data.append('{}: {}'.format(node, path))
            data = '\n'.join(sorted(data))

            diag.append(diag_skel.format(sender=sender,
                                         receiver=receiver,
                                         type=type,
                                         data=data,
                                         time=time))

    diag.insert(0, ';'.join(sorted(routers)) + ';')
    result = skel.format('\n'.join(diag))

    tree = seq_parser.parse_string(result)
    diagram = builder.ScreenNodeBuilder.build(tree)
    draw = drawer.DiagramDraw(args.type, diagram, filename=args.output)
    draw.draw()
    draw.save()


if __name__ == '__main__':
    main()
