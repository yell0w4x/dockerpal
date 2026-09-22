from dockerpal import __version__
from dockerpal.app import app

from argparse import ArgumentParser
import sys


def cli(args=None):
    parser = ArgumentParser(prog='dockerpal', description='TUI based docker explorer')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    return parser.parse_args(sys.argv[1:] if args is None else args)


def main():
    cli()
    app()


if __name__ == '__main__':
    main()
