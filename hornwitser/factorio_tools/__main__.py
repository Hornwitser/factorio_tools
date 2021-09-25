# factorio_tools - Debugging utilities for Factorio
# Copyright (C) 2020  Hornwitser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import sys

from . import desync
if sys.platform == "win32":
    from . import multi
from . import parse


def main():
    parser = argparse.ArgumentParser(
        prog="factorio_tools",
        description="Debugging utilities for Factorio",
    )
    parser.set_defaults(func=lambda args: parser.print_help())
    subparsers = parser.add_subparsers(help="Tool to run")

    desync_parser(subparsers)
    dat2json_parser(subparsers)
    if sys.platform == "win32":
        multi_parser(subparsers)
    args = parser.parse_args()
    args.func(args)

def dat2json_parser(subparsers):
    parser = subparsers.add_parser(
        'dat2json', help="Convert Factorio dat files to json",
        description=
            "Converts the binary formats used in Factorio to json.  "
            "The format options are only necessary if the format cannot be deduced from filename."
    )

    parser.add_argument('--input', '-i', default='-', type=argparse.FileType('rb'), help="input file to convert")
    parser.add_argument('--input-format', help="format of input file")
    parser.add_argument('--output', '-o', default='-', type=argparse.FileType('w'), help="file to output to")
    parser.set_defaults(func=parse.dat2json)

def desync_parser(subparsers):
    parser = subparsers.add_parser(
        'desync', help="Analyze desync reports",
        description=
            "Automated parsing and diffing of desync reports from Factorio"
    )

    parser.add_argument('path', help="Path to desync report, will be extracted if in the .zip file")
    parser.set_defaults(func=desync.analyze)

def multi_parser(subparsers):
    parser = subparsers.add_parser('multi', help="Handle multiple Factorio clients")
    parser.set_defaults(func=lambda args: parser.print_help())
    subparsers = parser.add_subparsers()

    parser_generate_base = subparsers.add_parser('generate-base', help="Generate write dir to base instances on")
    parser_generate_base.add_argument('--base', default="base", help="Name of write dir to generate")
    parser_generate_base.add_argument('--data', help="Path to Factorio data directory")
    parser_generate_base.set_defaults(func=multi.generate_base)

    parser_generate_instances = subparsers.add_parser('generate-instances', help="Generate instances write dirs")
    parser_generate_instances.add_argument('count', type=int, help="Number of instances to generate")
    parser_generate_instances.add_argument('--base', default="base", help="Write dir to base instances on")
    parser_generate_instances.add_argument('--output', default="", help="Path to put generated instances into")
    parser_generate_instances.add_argument('--prefix', default="instance", help="Prefix to name of instance dirs")
    parser_generate_instances.set_defaults(func=multi.generate_instances)

    parser_spawn = subparsers.add_parser('spawn', help="Spawn single client")
    parser_spawn.add_argument('--path', default="base", help="Path to write dir to spawn from")
    parser_spawn.add_argument('--factorio', help="Path to Factorio executable")
    parser_spawn.add_argument('--args', '-a', help="Additional args to pass to Factorio")
    parser_spawn.add_argument('--title', help="Set window title to given text")
    parser_spawn.set_defaults(func=multi.spawn)

    parser_spawn_multi = subparsers.add_parser('spawn-multi', help="Spawn multiple clients")
    parser_spawn_multi.add_argument('--count', '-c', type=int, default=1, help="Clients to spawn")
    parser_spawn_multi.add_argument('--delay', '-d', type=float, default=2.0, help="Deleay between spawns")
    parser_spawn_multi.add_argument('--rows', '-R', type=int, default=4, help="Positioning rows")
    parser_spawn_multi.add_argument('--cols', '-C', type=int, default=5, help="Positioning columns")
    parser_spawn_multi.add_argument('--instance-dirs', default="", help="Location of instance dirs")
    parser_spawn_multi.add_argument('--prefix', default="instance", help="Prefix to name of instance dirs")
    parser_spawn_multi.add_argument('--factorio', help="Path to Factorio executable")
    parser_spawn_multi.add_argument('--args', '-a', help="Additional args to pass to Factorio")
    parser_spawn_multi.add_argument('--title', help="Set window title to given text")
    parser_spawn_multi.set_defaults(func=multi.spawn_multi)

    parser_click = subparsers.add_parser('click', help="Click coordinate on all clients")
    parser_click.add_argument('x', type=int, help="x coordinate")
    parser_click.add_argument('y', type=int, help="y coordinate")
    parser_click.set_defaults(func=multi.click)

if __name__ == '__main__':
    main()
