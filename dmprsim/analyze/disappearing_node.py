"""
Draw a sequence diagram of all transmitted messages,
requires rx.msg.valid tracepoint
"""
import argparse
import json
from pathlib import Path

from seqdiag import drawer, builder, parser as seq_parser

from dmprsim.analyze._utils.extract_messages import all_tracefiles, \
    extract_messages
from dmprsim.scenarios.disappearing_node import main as scenario

skel = """
   seqdiag {{
      activation = none;
      {}
   }}
"""


def main(args, result_path: Path, scenario_path: Path):
    scenario(args, scenario_path, result_path)

    if not args.sequence_diagram:
        return
    routers = set()
    messages = {}
    for router, tracefile in all_tracefiles([scenario_path], 'rx.msg.valid'):
        routers.add(router)
        for time, message in extract_messages(tracefile):
            messages.setdefault(time, []).append((router, message))

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
    filename = str(result_path / 'sequence_diagram.svg')
    result_path.mkdir(parents=True, exist_ok=True)
    draw = drawer.DiagramDraw(args.seq_diag_type, diagram, filename=filename)
    draw.draw()
    draw.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate sequence diagrams")
    parser.add_argument('--format', default='SVG', choices=('SVG, PNG'),
                        help='ouput format, default: SVG')
    parser.add_argument('input', help='the scenario results directory')
    parser.add_argument('output', help='the output filename')
    args = parser.parse_args()
    main(args.input, args.output, args.format)
