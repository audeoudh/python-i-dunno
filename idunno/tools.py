# Python I-DUNNO (RFC8771) implementation.
# Copyright 2021  Henry-Joseph Audéoud
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

"""Load resources from Unicode Consortium."""

import re
import urllib.request


def merge_ranges(r):
    pending_start, pending_stop, *pending_args = None, None, None
    for start, stop, *args in r:
        if pending_start is None:
            pending_start, pending_stop, pending_args = start, stop, args
        elif pending_args == args and pending_stop + 1 == start:
            # Merge "pending" and this entry
            pending_stop = stop
        else:
            yield pending_start, pending_stop, *pending_args
            pending_start, pending_stop, pending_args = start, stop, args
    yield pending_start, pending_stop, *pending_args


def get_emoji_ranges():
    page = urllib.request.urlopen('https://www.unicode.org/Public/13.0.0/ucd/emoji/emoji-data.txt')
    line_p = re.compile(r"(?P<start>[0-9A-F]+)(?:\.\.(?P<stop>[0-9A-F]+))?\s+;\s+(?P<emoji>\w+)")
    for line in page:
        line = line.decode('utf-8')
        if line.startswith('#') or line == "\n":
            continue
        elif (m := line_p.match(line)) is not None:
            start = int(m['start'], 16)
            stop = m['stop']
            stop = int(stop, 16) if stop is not None else (start + 1)
            emoji = m['emoji']
            yield start, stop, emoji
        else:
            line = line.rstrip("\n")
            raise ValueError(f"unexpected line: '{line}'")


def get_scripts_ranges():
    page = urllib.request.urlopen('http://www.unicode.org/Public/UNIDATA/Scripts.txt')
    line_p = re.compile(r"(?P<start>[0-9A-F]+)(?:\.\.(?P<stop>[0-9A-F]+))?\s+;\s+"
                        r"(?P<script>\w+)\s+#\s+(?P<category>[A-Z][a-z&])")
    for line in page:
        line = line.decode('utf-8')
        if line.startswith('#') or line == "\n":
            continue
        elif (m := line_p.match(line)) is not None:
            start = int(m['start'], 16)
            stop = m['stop']
            stop = int(stop, 16) if stop is not None else (start + 1)
            script = m['script']
            yield start, stop, script
        else:
            line = line.rstrip("\n")
            raise ValueError(f"unexpected line: '{line}'")


def get_confusable():
    page = urllib.request.urlopen('http://www.unicode.org/Public/security/revision-03/confusablesSummary.txt')
    line_p = re.compile(r"←?\s+\(‎ .+ ‎\)\s+(?P<code_points>[0-9A-F ]+?)\s+(?P<names>[A-Z, ]+?)(?:\s+#)?")
    for line in page:
        line = line.decode('utf-8')
        if line.startswith('#') or line.startswith("﻿#") or line == "\n":
            continue
        if (m := line_p.match(line)) is not None:
            code_points = "".join(chr(int(x, 16)) for x in m['code_points'].split(" "))
            names = m['names'].split(", ")
            yield code_points
        else:
            line = line.rstrip("\n")
            raise ValueError(f"unexpected line: '{line}'")


if __name__ == '__main__':
    intranges_emoji = ((start << 32) | (end + 1) for start, end in merge_ranges(get_emoji_ranges()))
    confusables = get_confusable()
