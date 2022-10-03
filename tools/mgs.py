#!/usr/bin/env python3

# This script is intended to generate avinfo/mgs.json
# run `mgs.py -h` for help

import argparse
import json
import re
import sys
from collections import defaultdict
from operator import itemgetter
from pathlib import Path


def parse_args(root: Path):

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-f",
        dest="freq",
        action="store",
        type=int,
        default=3,
        help="cut the dict to this frequency (default: %(default)s)",
    )
    group.add_argument(
        "-s",
        dest="size",
        action="store",
        type=int,
        help="cut the dict to this size, 0 for unlimited",
    )
    parser.add_argument(
        "-d",
        dest="source",
        action="store",
        type=Path,
        default=root.parent.joinpath("regenerator/builder/data/mgs.json"),
        help="path to data source (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        dest="output",
        action="store",
        type=Path,
        default=root.joinpath("avinfo/mgs.json"),
        help="path to output file (default: %(default)s)",
    )
    return parser.parse_args()


def bisect_slice(a: list, x, d: dict):
    """Slice a reversely sorted list `a` to the first element whose value in `d`
    is smaller than `x`.
    """
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if x > d[a[mid]]:
            hi = mid
        else:
            lo = mid + 1
    return a[:lo]


def main():

    args = parse_args(Path(__file__).resolve().parent.parent)
    print(f"Source: {args.source}\nOutput: {args.output}", file=sys.stderr)

    try:
        with open(args.source, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(e)

    regex = re.compile(r"([0-9]*)([a-z]{2,10})[_-]?([0-9]{2,8})").fullmatch
    group = defaultdict(set)
    for i in filter(None, map(regex, map(str.lower, data))):
        group[i[2], i[1]].add(int(i[3]))

    # (prefix, digit): frequency
    group = dict(zip(group, map(len, group.values())))

    # list of tuples, sorted reversely by frequency
    # [0]: prefix, [1]: digit
    data = sorted(group)
    data.sort(key=group.get, reverse=True)

    # Trim data to `size` or `freq`. For the prefixes with multiple digits, keep
    # the most frequent one.
    tmp = {}
    setdefault = tmp.setdefault
    if args.size is None:
        for k, v in bisect_slice(data, args.freq, group):
            setdefault(k, v)
    else:
        i = args.size if args.size > 0 else len(data)
        for k, v in data:
            if setdefault(k, v) == v:
                i -= 1
                if not i:
                    break

    data[:] = tmp.items()
    if not data:
        sys.exit("Empty result.")

    size = len(data)
    total_entry = sum(group.values())
    used_entry = sum(map(group.get, data))
    key_len = frozenset(map(len, tmp))
    val_len = frozenset(map(len, tmp.values()))
    print(
        f"Dictionary size: {size}\n"
        f"Product coverage: {used_entry} / {total_entry} ({used_entry / total_entry:.1%})\n"
        f"Prefix coverage: {size} / {len(group)} ({size / len(group):.1%})\n"
        f"Minimum frequency: {group[data[-1]]}\n"
        f"Key length: {{{min(key_len)},{max(key_len)}}}\n"
        f'Value length: {{{min(val_len) or ""},{max(val_len)}}}')

    data.sort(key=itemgetter(1, 0))
    data = dict(data)
    try:
        with open(args.output, "r+", encoding="utf-8") as f:
            if json.load(f) == data:
                print("Dictionary is up to date.", file=sys.stderr)
                return
            f.seek(0)
            json.dump(data, f, separators=(",", ":"))
            f.truncate()
    except (FileNotFoundError, ValueError):
        args.output.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
    print(f"Update: '{args.output}'", file=sys.stderr)


if __name__ == "__main__":
    main()
