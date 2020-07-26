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

'''
desync.py - Automated analyzis of desync reports
'''

import collections
import difflib
import enum
import itertools
import json
from os import path
import re
import zipfile

from . import parse


BUFFER_SIZE = 2**20
class TokenKind(enum.IntEnum):
    OPEN_TAG = 1
    CLOSE_TAG = 2
    DATA = 3
    COLLAPSED = 4

class Token(collections.namedtuple('Token', 'kind content tag parent pos')):
    def __eq__(self, other):
        return (
            self.kind == other.kind
            and self.content == other.content
            and self.tag == other.tag
        )

    def __ne__(self, other):
        return (
            self.kind != other.kind
            or self.content != other.content
            or self.tag != other.tag
        )

    def __hash__(self):
        return hash((self.kind, self.content, self.tag))


token_spec = [
    (b'OPEN_TAG', br'<(?P<OPEN_TAG_NAME>[a-z-]+)( ([^\x00-\x1f<>\x80-\xff]|<[a-zA-Z]+>)*)?>'),
    (b'CLOSE_TAG', br'</(?P<CLOSE_TAG_NAME>[a-z-]+)>'),
]

tag = re.compile(b'|'.join(b'(?P<%s>%s)' % pair for pair in token_spec))

def tokenize_tagged_file(tagged_file):
    parent = None
    pos = 0
    offset = 0
    buffer = tagged_file.read(BUFFER_SIZE)
    while True:
        match = tag.search(buffer, pos)
        if not match:
            more = tagged_file.read(BUFFER_SIZE)
            if not more:
                yield Token(TokenKind.DATA, buffer[pos:], None, parent, offset + pos)
                break

            buffer += more
            continue

        if match.start() > pos:
            yield Token(TokenKind.DATA, buffer[pos:match.start()], None, parent, offset + pos)

        if match.lastgroup == 'CLOSE_TAG':
            new_parent = parent
            tag_name = match['CLOSE_TAG_NAME']
            while new_parent is not None:
                if new_parent.tag == tag_name:
                    parent = new_parent.parent
                    break

                new_parent = new_parent.parent

            else:
                print(f"Unmatched close tag </{tag_name}>")

        token = Token(TokenKind[match.lastgroup], match[0], match[f'{match.lastgroup}_NAME'], parent, offset + pos)
        yield token
        if match.lastgroup == 'OPEN_TAG':
            parent = token

        pos = match.end()
        if pos > BUFFER_SIZE // 2:
            offset += pos
            buffer = buffer[pos:]
            pos = 0

def token_path(token):
    path = []
    parent = token.parent
    while parent is not None:
        path[0:0] = [parent]
        parent = parent.parent

    formatted = []
    for i, ancestor in enumerate(path):
        formatted.append(f"{'  '*i}{ancestor.content.decode('utf-8')} pos={ancestor.pos}")
    return '\n'.join(formatted)

def collapse(iterator):
    curr = next(iterator, None)
    next1 = next(iterator, None)
    next2 = next(iterator, None)

    def advance():
        nonlocal curr, next1, next2
        curr = next1
        next1 = next2
        next2 = next(iterator, None)

    while curr is not None:
        if (
            curr.kind == TokenKind.OPEN_TAG
            and next1.kind == TokenKind.DATA
            and next2.kind == TokenKind.CLOSE_TAG
            and curr.tag == next2.tag
        ):
            content = curr.content + next1.content + next2.content
            yield Token(TokenKind.COLLAPSED, content, curr.tag, curr.pos)
            advance()
            advance()

        elif (
            curr.kind == TokenKind.OPEN_TAG
            and next1.kind == TokenKind.CLOSE_TAG
            and curr.tag == next1.tag
        ):
            content = curr.content + next1.content
            yield Token(TokenKind.COLLAPSED, content, curr.tag, curr.pos)
            advance()

        else:
            yield curr

        advance()

def find_files(level_zip):
    files = {}
    for name in level_zip.namelist():
        if 'root' not in files:
            files['root'] = name[:name.find('/')]

        if re.match(r'.*/level-heuristic-\d+', name):
            files['heuristic'] = level_zip.open(name)

        if re.match(r'.*/level_with_tags_tick_\d+\.dat', name):
            files['level_with_tags'] = level_zip.open(name)

    files['script'] = level_zip.open(f'{files["root"]}/script.dat')
    return files

def file_differs(a, b):
    try:
        bytes_a = None
        while bytes_a != b'':
            bytes_a = a.read(1024)
            if bytes_a != b.read(1024):
                return True

        return False

    finally:
        a.seek(0)
        b.seek(0)

def diff_script_objects(a, b, path=[]):
    if type(a) is not type(b):
        yield (path, a, b)

    elif type(a) is list:
        for i in range(max(len(a), len(b))):
            sub_path = path + [i] if path != ['data'] else path + [a[i]['name']]
            if i < len(a) and i < len(b):
                yield from diff_script_objects(a[i], b[i], sub_path)
            elif i < len(a):
                yield (sub_path, a[i], None)
            else:
                yield (sub_path, None, b[i])

    elif type(a) is dict:
        shared_keys = {*a.keys(), *b.keys()}
        if shared_keys == {'key', 'value'}:
            path = path[:-1] + [a['key']]
        for k in shared_keys:
            if k in a and k in b:
                yield from diff_script_objects(a[k], b[k], path + [k])
            elif k in a:
                yield (path + [k], a[k], None)
            else:
                yield (path + [k], None, b[k])

    elif a != b:
        yield (path, a, b)


def script_dat_to_object(level_files):
    print(f"parsing {level_files['root']}/script.dat")
    decoded = parse.ScriptDat.parse_stream(level_files['script'])
    level_files['script'].seek(0)
    return parse.container_to_object(decoded)

def diff_tagged_files(a_file, b_file):

    # SequenceMatcher is too slow to work on an entire parsed level
    # so we will instead diff top level tags one by one
    def top_level_tags(generator):
        chunk = []
        for token in generator:
            chunk.append(token)
            if token.parent is None and token.kind != TokenKind.OPEN_TAG:
                yield chunk
                chunk = []

        if chunk:
            yield chunk

    a_generator = top_level_tags(tokenize_tagged_file(a_file))
    b_generator = top_level_tags(tokenize_tagged_file(b_file))

    # For now it's assumed two levels have the same number of chunks
    # and have them in the same order.  This may not actually hold true
    combined = itertools.zip_longest(a_generator, b_generator)
    for a_chunk, b_chunk in combined:
        if a_chunk == b_chunk:
            continue

        if max(len(a_chunk), len(b_chunk)) > 200000:
            print(f"diffing <{a_chunk[0].tag}> {len(a_chunk)}/{len(b_chunk)} tokens, this may take a long time")

        matcher = difflib.SequenceMatcher(None, a_chunk, b_chunk)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == 'equal': continue
            print()
            print(f"{op:7}   ref[{i1}:{i2}] -> des[{j1}:{j2}]")
            print(token_path(a_chunk[i1]))
            print(f"ref: {b''.join(map(lambda t: t.content, a_chunk[i1:i2]))!r}")
            print(token_path(b_chunk[j1]))
            print(f"des: {b''.join(map(lambda t: t.content, b_chunk[j1:j2]))}")

def analyze(args):
    if args.path.endswith('.zip'):
        print(f"Unzipping {args.path}")
        report = zipfile.ZipFile(args.path)
        report.extractall(path.dirname(args.path))
        args.path = args.path[:-4]

    ref_zip = zipfile.ZipFile(path.join(args.path, 'reference-level.zip'))
    des_zip = zipfile.ZipFile(path.join(args.path, 'desynced-level.zip'))

    ref_files = find_files(ref_zip)
    des_files = find_files(des_zip)

    if file_differs(ref_files['heuristic'], des_files['heuristic']):
        print()
        print("level-heuristic differs")
        print("-----------------------")
        diff_tagged_files(ref_files['heuristic'], des_files['heuristic'])

    if file_differs(ref_files['script'], des_files['script']):
        print()
        print("script.dat differs")
        print("------------------")

        des_script = script_dat_to_object(des_files)
        ref_script = script_dat_to_object(ref_files)
        for diff in diff_script_objects(ref_script, des_script):
            print(f"Path: {diff[0]}")
            print(f"Reference value: {json.dumps(diff[1])}")
            print(f"Desynced value: {json.dumps(diff[2])}")

    if file_differs(ref_files['level_with_tags'], des_files['level_with_tags']):
        print()
        print("level_with_tags.dat differs")
        print("---------------------------")
        diff_tagged_files(ref_files['level_with_tags'], des_files['level_with_tags'])
