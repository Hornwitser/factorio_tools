Factorio Tools
==============

A collection of command-line tools for debugging and inspecting Factorio
related things, written in Python.


Installation
------------

Factorio Tools is available on PyPi, you can install/update it using the
``pip`` module with the following command.

.. code ::

    > py -m pip install --user --upgrade hornwitser.factorio_tools


desync tool
-----------

Automatically parse and diff Factorio desync reports, takes a single
parameter ``path`` to the desync report to analyze.  If the report is in
a .zip file it will be exacted first.  For example:

.. code ::

    > py -m hornwitser.factorio_tools desync desync-report-2020-07-01_10-00-00.zip

The output shows differences found in the script.dat, level-heuristics
and level_with_tags files between the reference and desynced level
contained in the desync report.

This tool is rather slow and may take a long time to run.


dat2json tool
-------------

Decode some of Factorio's .dat files into pretty formatted JSON.  The
decoding is a work in progress and the meaning of fields ending with an
underscore is not know.  For example:

.. code ::

    > py -m hornwitser.factorio_tools dat2json -i script.dat -o script.json

Takes 3 options, ``--input`` for setting the input .dat file,
``--output`` for setting the output file, both of which accept ``-`` for
stdin/stdout (the default), and ``--input-format`` which is needed in
case the format can not be deduced from name of the file.  The format
should be the name Factorio gives the .dat file without the .dat suffix.

Currently acheivements, mod-dettings and script data can be decoded
using this tool.


multi tool
----------

.. note ::  This tool is only available on Windows.

Automate spawning, arranging, and interacting with many Factorio clients
at the same time.  It works by arranging the client windows on a grid
using the Windows API, and has a mode that clicks a specific location
in every Factorio window on the desktop.  To make it work you'll have to
do the following steps:

1.  Open a command propmt and navigate/create a new directory to store
    the write directories for all of the client instances.  If you place
    this new directory inside the Factorio installation directory then
    the Factorio executable will be auto detected, otherwise you will
    need to pass it with the ``--factorio`` when spawning instances.

2.  Generate a base write dir for the instances to be based on.

    .. code ::

        > py -m hornwitser.factorio_tools multi generate-base

    This creates a new directory named base by default (can be changed
    with the ``--base`` option.)

3.  Start the base instance

    .. code ::

        > py -m hornwitser.factorio_tools multi spawn

    This should launch Factorio in windowed mode with music and updates
    disabled.  You should consider changing the following settings in
    order to make the management of the instances less annoying and use
    less resources:

    - Disable minimap.
    - Disable show tips and tricks.
    - Disable show tutorial notifications.
    - Disable play sound for chat messages.
    - Disable entity tooltip on the side.
    - Set shortcut bar rows and active quickbars to 1.
    - Set a player name.
    - Disable all show ... graphics settings.
    - Set sprite resoultion to normal.
    - Disable high quality animations.
    - Set Video memory usage to low.
    - Set Texture compression to low quality.
    - Disable full color depth.

    After making the setting changes exit Factorio.

4.  Generate instance write directories.

    .. code ::

        > py -m hornwitser.factorio_tools multi generate-instances 8

    This generates 8 instance directories named instance1 to instance8
    in the current directory based on the base instance.  You can
    change the base instance, name of the output instances and where
    they are output with the ``--base``, ``--output`` and ``--prefix``
    options.

5.  Spawn instances using the spawn-multi command

    .. code ::

        > py -m hornwitser.factorio_tools multi spawn-multi --count 8

    This will spawn and arrange Factorio clients in a 5x4 grid starting
    from the top right and going down.  There are numerous options to
    control the behaviour, including how many rows and columns to use
    and the delay between each spawn.

    You can add arguments that are passed to factorio with the
    ``--args`` option.  This is useful to have the clients auto connect
    to a server by passing ``--args "--mp-connect example.com"``.

Once you've generated the instances you only need to perform step 5 to
start instances.  If you want to change the config for all of the
instances perform step 3 followed step 4 again.

Finally there's a ``click`` tool that's invoked with

.. code ::

    > py -m hornwitser.factorio_tools multi click 200 180

and clicks on the given x, y coordinate on every window who's title
starts with "Factorio".  Taking a screenshot of one of the Factorio
windows with Alt+PrtScn and then pasting it into MS Paint is useful
to figure out what coordinate a button is on.
