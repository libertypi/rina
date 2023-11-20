#!/usr/bin/env python3

# This script is intended to generate `rina/mgs.json`
# Data source: `./mgs_src.json` from my `rebuilder` project
# run `mgs.py -h` for help

import argparse
import json
import re
import sys
from collections import defaultdict
from operator import itemgetter
from pathlib import Path


def parse_args(source: Path, dest: Path):
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
        "-l",
        dest="length",
        action="store",
        type=int,
        help="cut the dict to this length, 0 for unlimited",
    )
    parser.add_argument(
        "-s",
        dest="src",
        action="store",
        type=Path,
        default=source,
        help="path to data source (default: %(default)s)",
    )
    parser.add_argument(
        "-d",
        dest="dst",
        action="store",
        type=Path,
        default=dest,
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
    source = Path(__file__).resolve().with_name("mgs_src.json")
    args = parse_args(
        source=source,
        dest=source.parent.parent.joinpath("rina/mgs.json"),
    )

    print(f"Source: {args.src}\nOutput: {args.dst}", file=sys.stderr)

    try:
        with open(args.src, "r", encoding="utf-8") as f:
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

    # Trim data to `length` or `freq`. For the prefixes with multiple digits, keep
    # the most frequent one.
    tmp = {}
    setdefault = tmp.setdefault
    if args.length is None:
        for k, v in bisect_slice(data, args.freq, group):
            setdefault(k, v)
    else:
        i = args.length if args.length > 0 else len(data)
        for k, v in data:
            if setdefault(k, v) == v:
                i -= 1
                if not i:
                    break

    data[:] = tmp.items()
    if not data:
        sys.exit("Empty result.")

    length = len(data)
    total_entry = sum(group.values())
    used_entry = sum(map(group.get, data))
    key_len = frozenset(map(len, tmp))
    val_len = frozenset(map(len, tmp.values()))
    print(
        "Result:\n"
        f"  Dictionary length: {length}\n"
        f"  Product coverage : {used_entry} / {total_entry} ({used_entry / total_entry:.1%})\n"
        f"  Prefix coverage  : {length} / {len(group)} ({length / len(group):.1%})\n"
        f"  Minimum frequency: {group[data[-1]]}\n"
        f"  Key length range : {{{min(key_len)},{max(key_len)}}}\n"
        f"  Val length range : {{{min(val_len)},{max(val_len)}}}"
    )

    data.sort(key=itemgetter(1, 0))
    data = dict(data)
    try:
        with open(args.dst, "r+", encoding="utf-8") as f:
            if json.load(f) == data:
                print(f"{args.dst.name} is up to date.", file=sys.stderr)
                return
            f.seek(0)
            json.dump(data, f, separators=(",", ":"))
            f.truncate()
    except (FileNotFoundError, ValueError):
        with open(args.dst, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
    print(f"Update: '{args.dst}'", file=sys.stderr)


if __name__ == "__main__":
    main()
