#!/usr/bin/env python3
import argparse
from pathlib import Path

# TODO description
DESCRIPTION = """\
description
"""

RESULT_PATH = Path('results')
SCENARIO_PATH = RESULT_PATH / '.scenarios'


def _add_default_arguments(parser: argparse.ArgumentParser):
    parser.add_argument('--enable-video', action='store_true')
    parser.add_argument('--enable-images', action='store_true')


class AbstractAnalyzer(object):
    NAME = 'abstract'
    NUM = 0
    DEFAULT_ARGUMENTS = True

    @classmethod
    def argparser(cls, sub_parser: argparse._SubParsersAction):
        parser = sub_parser.add_parser(cls.NAME, aliases=[str(cls.NUM)])
        if cls.DEFAULT_ARGUMENTS:
            _add_default_arguments(parser)
        cls.add_args(parser)
        parser.set_defaults(func=cls.run)

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        pass

    @classmethod
    def run(cls, args):
        raise NotImplementedError


class MessageSize(AbstractAnalyzer):
    NUM = 1
    NAME = '{:03}-message-size'.format(NUM)

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        parser.add_argument('--quiet', type=bool, default=True)
        parser.add_argument('--max-ram', default=16, type=int,
                            help='Maximum RAM in GB')

    @classmethod
    def run(cls, args):
        from dmprsim.analyze.message_size import main
        main(args, RESULT_PATH / cls.NAME, SCENARIO_PATH / cls.NAME)


class DisappearingNode(AbstractAnalyzer):
    NUM = 2
    NAME = '{:03}-disappearing-node'.format(NUM)

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        parser.add_argument('--sequence-diagram', action='store_true')
        parser.add_argument('--seq-diag-type', default='SVG',
                            choices=('SVG', 'PNG'))

    @classmethod
    def run(cls, args):
        from dmprsim.analyze.disappearing_node import main
        main(args, RESULT_PATH / cls.NAME, SCENARIO_PATH / cls.NAME)


def main():
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=lambda args: parser.print_help())
    sub_parsers = parser.add_subparsers(title="Analyze options",
                                        description="valid analyze scripts")
    MessageSize.argparser(sub_parsers)
    DisappearingNode.argparser(sub_parsers)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
