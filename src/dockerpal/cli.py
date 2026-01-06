
from dockerpal.app import app

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import sys


def cli(args=sys.argv[1:]):
    parser = ArgumentParser(description='dockerpal description goes here')
    parser.add_argument('--change-me', default='An option sample', required=False, 
        help='Just an option sample of your cli to be substituted by real ones')

    return parser.parse_args(args)


def main():
    args = cli()
    app()


if __name__ == '__main__':
    main()
