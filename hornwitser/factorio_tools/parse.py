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
parse.py - Parser for the binary formats to Factorio
"""

import json
import os
import struct
import sys

from construct import \
    Construct, Container, ListContainer, Prefixed, PrefixedArray, Struct, \
    Sequence, Switch, Computed, Terminated, Int32ul, Int24ul, Int16ul, Int8ul, \
    Float64l, Float32l, PascalString, stream_read, stream_write, this


def singleton(cls):
    return cls()

@singleton
class FactorioInt32ul(Construct):
    def _parse(self, stream, context, path):
        tiny = stream_read(stream, 1, path)[0]
        if tiny != 0xff:
            return tiny

        big = stream_read(stream, 4, path)
        return struct.unpack('<l', big)[0]

    def _build(self, obj, stream, context, path):
        if obj < 0xff:
            stream_write(stream, bytes([obj]), 1, path)

        else:
            stream_write(stream, bytes([0xff]), 1, path)
            stream_write(stream, struct.pack('<l', obj), 4, path)

        return obj


    def _sizeof(self, context, path):
        raise SizeofError


object_types = {}

SerializedObject = Struct(
    "type" / Int8ul,
    "data" / Switch(this.type, object_types)
)

# boolean
object_types[0x01] = Struct(
    "uno_" / Int8ul,
    "value" / Int8ul,
)

# float double
object_types[0x02] = Struct(
    "what_" / Int8ul,
    "value" / Float64l,
)

# string
object_types[0x03] = Struct(
    "red_" / Int8ul,
    "blue_" / Int8ul,
    "value" / PascalString(Int8ul, "latin-1"),
)

KeyValuePair = Struct(
    "bloom_" / Int8ul,
    "key" / PascalString(Int8ul, "latin-1"),
    "value" / SerializedObject,
)

# mapping
object_types[0x05] = Struct(
    "monkey_" / Int8ul, # Usually 0
    "items" / PrefixedArray(Int32ul, KeyValuePair),
)

Version = Struct(
    "major" / Int16ul,
    "minor" / Int16ul,
    "patch" / Int16ul,
    "even_" / Int16ul, # Sometimes 1
    "odd_" / Int8ul, # Usually 0
)

OldScriptDat = Struct(
    "_type" / Computed(lambda this: "script"),
    "version" / Version,
    "data" / PrefixedArray(Int32ul, Struct(
        "name" / PascalString(Int8ul, "latin-1"),
        "dump" / PascalString(FactorioInt32ul, "latin-1"),
        "tabletop_" / Int8ul
    )),
    Terminated,
)


script_object_types = {}

ScriptSerializedObject = Struct(
    "type" / Int8ul,
    "data" / Switch(this.type, script_object_types),
)

# boolean
script_object_types[0x02] = Computed(lambda this: True)

# float double
script_object_types[0x03] = Float64l

# string
script_object_types[0x04] = PascalString(FactorioInt32ul, "latin-1")

ScriptKeyValuePair = Struct(
    "key" / ScriptSerializedObject,
    "value" / ScriptSerializedObject,
)

# mapping
script_object_types[0x05] = PrefixedArray(FactorioInt32ul, ScriptKeyValuePair)

# some kind of reference
script_object_types[0x06] = Int16ul

ScriptDat = Struct(
    "_type" / Computed(lambda this: "script"),
    "version" / Version,
    "data" / PrefixedArray(Int32ul, Struct(
        "name" / PascalString(Int8ul, "latin-1"),
        "dump" / Prefixed(FactorioInt32ul, Struct(
            "version" / Version,
            "data" / ScriptSerializedObject,
        )),
        "tabletop_" / Int8ul
    )),
    Terminated,
)

ModSettingsDat = Struct(
    "_type" / Computed(lambda this: "mod-settings"),
    "version" / Version,
    "settings" / SerializedObject,
    Terminated,
)

IdEntry = Struct(
    "type" / PascalString(Int8ul, "latin-1"),
    "names" / PrefixedArray(Int16ul, Struct(
        "name" / PascalString(Int8ul, "latin-1"),
        "id" / Int16ul,
    )),
)

TileIdEntry = Struct(
    "type" / PascalString(Int8ul, "latin-1"),
    "names" / PrefixedArray(Int8ul, Struct(
        "name" / PascalString(Int8ul, "latin-1"),
        "id" / Int8ul,
    )),
)

achievement_types = {
    'achievement': Computed(lambda this: "no-data"),
    'build-entity-achievement': Int32ul,
    'combat-robot-count': Int32ul,
    'construct-with-robots-achievement': Sequence(Int32ul, Int32ul),
    'deconstruct-with-robots-achievement': Int32ul,
    'deliver-by-robots-achievement': Float64l,
    'dont-build-entity-achievement': Int32ul,
    #'dont-craft-manually-achievement': Unknown
    'dont-use-entity-in-energy-production-achievement': Float64l,
    'finish-the-game-achievement': Int32ul,
    'group-attack-achievement': Int32ul,
    'kill-achievement': Float64l,
    'player-damaged-achievement': Sequence(Float32l, Int8ul),
    'produce-achievement': Float64l,
    'produce-per-hour-achievement': Float64l,
    'research-achievement': Computed(lambda this: "no-data"),
    'train-path-achievement': Float64l,
}

def id_to_type(id, table):
    for type_entry in table:
        for name_entry in type_entry.names:
            if id == name_entry.id:
                return name_entry.name, type_entry.type

    raise ValueError(f"No entry in id_table for id {id}")

AchievementEntry = Struct(
    "id" / Int16ul,
    "_name" / Computed(lambda this: id_to_type(this.id, this._._.id_table)[0]),
    "_type" / Computed(lambda this: id_to_type(this.id, this._._.id_table)[1]),
    "data" / Switch(this._type, achievement_types),
)

AchievementDat = Struct(
    "_type" / Computed(lambda this: "achievements"),
    "version" / Version,
    "id_table" / PrefixedArray(Int16ul, IdEntry),
    "achievements" / PrefixedArray(Int32ul, AchievementEntry),
    Terminated,
)

AchievementModdedEntry = Struct(
    "type" / PascalString(Int8ul, "latin-1"),
    "name" / PascalString(Int8ul, "latin-1"),
    "data" / Switch(this.type, achievement_types),
)

AchievementsModdedDat = Struct(
    "_type" / Computed(lambda this: "achievements-modded"),
    "version" / Version,
    "id_table" / PrefixedArray(Int16ul, IdEntry),
    "achievements" / PrefixedArray(Int32ul, AchievementModdedEntry),
    "gremling_" / Int32ul,
    "mole_" / Int16ul,
    Terminated,
)

MigrationEntry = Struct(
    "mod" / PascalString(Int8ul, "latin-1"),
    "migration" / PascalString(Int8ul, "latin-1"),
)

blueprint_types = {}

Blueprint = Struct(
    "bp_type" / Int16ul,
    "bp_name" / PascalString(Int8ul, "latin-1"),
    "content" / Switch(this.bp_type, blueprint_types)
)

BlueprintEntity = Struct(
    "id" / Int16ul,
)

BlueprintData = Struct(
    "version" / Version,
    "applied_migrations" / PrefixedArray(Int8ul, MigrationEntry),
    "entites" / PrefixedArray(Int32ul, BlueprintEntity),

)

# XXX: Hard coded for now
# Blueprint
blueprint_types[0x44] = Struct(
    "rock_" / Int16ul,
    "data" / Prefixed(FactorioInt32ul, BlueprintData),
)
# Blueprint Book
blueprint_types[0x48] = Struct(
    "pages" / PrefixedArray(Int32ul, Struct(
        "pos" / Int32ul,
        "content" / Blueprint,
    )),
)

BlueprintEntry = Struct(
    "ohio_" / PrefixedArray(Int8ul, Int8ul),
    "florida_" / Int8ul,
    "utah_" / Int16ul,
    "brooklyn_" / PrefixedArray(Int8ul, Int16ul),
    "hollywood_" / Int16ul,
    "blueprint" / Blueprint,
)

IdTable = Struct(
    "version" / Version,
    "item_table" / PrefixedArray(Int16ul, IdEntry),
    "tile_table" / PrefixedArray(Int8ul, TileIdEntry),
    "entity_table" / PrefixedArray(Int16ul, IdEntry),
    "recipe_table" / PrefixedArray(Int16ul, IdEntry),
    "fluid_table" / PrefixedArray(Int16ul, IdEntry),
    "signal_table" / PrefixedArray(Int16ul, IdEntry),
    Terminated,
)

from construct import GreedyRange

BlueprintStorageDat = Struct(
    "_type" / Computed(lambda this: "blueprint-storage"),
    "version" / Version,
    "applied_migrations" / PrefixedArray(Int8ul, MigrationEntry),
    "id_table" / Prefixed(FactorioInt32ul, IdTable),

    "chicago_" / Int16ul,
    "jersey_" / Int32ul,
    "buffalo_" / Int32ul,
    "blueprints" / GreedyRange(BlueprintEntry),
)

dat_formats = {
    'achievements': AchievementDat,
    'achievements-modded': AchievementsModdedDat,
    'blueprint-storage': BlueprintStorageDat,
    'mod-settings': ModSettingsDat,
    'script': ScriptDat,
# TODO
#    'crop-cache',
#    'level',
#    'level-init',
}

_excluded_keys = ('_io',)
def container_to_object(obj):
    """Convert a construct container into a json encodable object"""
    if isinstance(obj, Container):
        # Hack for simplyfying script data output
        if (set(obj.keys()) == set(["type", "data", "_io"])):
            if obj.type in (0x02, 0x03, 0x04, 0x05):
                return container_to_object(obj.data)

        return {k: container_to_object(v)
            for k, v in obj.items() if k not in _excluded_keys
        }

    if isinstance(obj, ListContainer):
        return list(map(container_to_object, obj))

    return obj

def dat2json(args):
    if not args.input_format:
        base = os.path.basename(args.input.name)
        if base.endswith('.dat'):
            args.input_format = base[:-4]
        else:
            raise RuntimeError("Unknown input file format")

    Decoder = dat_formats.get(args.input_format)
    if not Decoder:
        raise RuntimeError("Unkown input file format")

    decoded = Decoder.parse_stream(args.input)
    json.dump(container_to_object(decoded), args.output, indent="\t")
