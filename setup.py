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

import setuptools

def read_file(path):
    with open(path) as f:
        return f.read()

setuptools.setup(
    name="hornwitser.factorio_tools",
    version="0.0.4",
    author="Hornwitser",
    author_email="github@hornwitser.no",
    description="Tools for Debugging Factorio",
    long_description=read_file('README.rst'),
    long_description_content_type='text/x-rst',
    url="https://github.com/Hornwitser/factorio_tools",
    namespace_packages=['hornwitser'],
    packages=['hornwitser.factorio_tools'],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Utilities",
    ],
    python_requires='>=3.7',
    install_requires=[
        "construct>=2.10.53",
    ],
    zip_safe=True,
)
