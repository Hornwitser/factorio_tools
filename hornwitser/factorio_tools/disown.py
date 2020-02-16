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

"""
disown.py - Dumb Factorio console workaround

Invokes the command specified as the first argument and prints back the
the pid of the command launched over stdout.  This is necessary because
Factorio likes to hijack whatever console it finds in the process that
spawns it.
"""

import sys
import subprocess

if __name__ == '__main__':
    proc = subprocess.Popen(sys.argv[1])
    print(proc.pid, end='')
