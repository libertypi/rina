#!/usr/bin/env python3

"""
Generate mgs.json for Rina.
Source: mgs_src.json
Dest: rina/mgs.json
"""

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from operator import itemgetter
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        dest="freq",
        action="store",
        type=int,
        default=2,
        help="include IDs appearing at least this many times (default: %(default)s)",
    )
    return parser.parse_args()


def reverse_bisect_left(a: list, x: int, i: int):
    """Locate the cut point `c` so that every `e[i]` in `a[:c]` have
    `e[i] >= x`. Note that `a` is reverse-sorted list of tuples."""
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid][i] < x:
            hi = mid
        else:
            lo = mid + 1
    return lo


def main():
    # Source format: [num][prefix]-[suffix] (e.g., 001AVGP-136)
    # Output format: {prefix: [num1, num2, ...], ...}
    # Only keeps prefix-num pairs that appear more than `args.freq` times
    args = parse_args()

    src = Path(__file__).resolve().with_name("mgs_src.json")
    dst = src.parents[1].joinpath("rina/mgs.json")
    print(f"Source: {src}\nOutput: {dst}")

    # update source from `footprints` project
    try:
        shutil.copy(src.parents[2].joinpath("footprints/data/mgs.json"), src)
    except FileNotFoundError:
        print("Warning: cannot update data file from footprints.")
    try:
        with open(src, "r", encoding="utf-8") as f:
            result = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(e)

    # Group data from source, using a set to eliminate duplications.
    # groups[(prefix, num)] = {suffix1, suffix2, ...}
    regex = re.compile(r"([0-9]*)([a-z]{2,})-([0-9]{2,})").fullmatch
    groups = defaultdict(set)
    sfx_len = set()
    for i in filter(None, map(regex, map(str.lower, result))):
        groups[i[2], i[1]].add(int(i[3]))
        sfx_len.add(len(i[3]))

    # Measure the frequency and sort the groups by frequency (descending) and
    # then by prefix (alphabetically)
    # groups = [(prefix, num, frequency), ...]
    groups = sorted(
        ((*k, len(v)) for k, v in groups.items()),
        key=lambda a: (-a[2], a[0], a[1]),
    )
    get_freq = itemgetter(2)
    total = sum(map(get_freq, groups))

    # Slice the list so that all items have a frequency >= args.freq
    groups = groups[: reverse_bisect_left(groups, args.freq, 2)]
    if not groups:
        sys.exit("Empty result.")

    # Produce the result
    result = defaultdict(list)
    for prefix, num, _ in groups:
        result[prefix].append(num)

    covered = sum(map(get_freq, groups))
    ppprint = lambda s: ", ".join(map(str, sorted(s)))
    print(
        "Result:\n"
        f"    Dictionary length: {len(result)}\n"
        f"    Product coverage : {covered} / {total} ({covered / total:.2%})\n"
        f"    Frequency range  : [{groups[-1][2]}, {groups[0][2]}]\n"
        f"    Number lengths   : {{{ppprint(set(len(v[1]) for v in groups))}}}\n"
        f"    Prefix lengths   : {{{ppprint(set(map(len, result)))}}}\n"
        f"    Suffix lengths   : {{{ppprint(sfx_len)}}}"
    )

    try:
        with open(dst, "r+", encoding="utf-8") as f:
            if json.load(f) == result:
                print(f"{dst.name} is up to date.")
                return
            f.seek(0)
            json.dump(result, f, separators=(",", ":"))
            f.truncate()
    except (FileNotFoundError, ValueError):
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(result, f, separators=(",", ":"))
    print(f"Update: '{dst}'")


if __name__ == "__main__":
    main()
