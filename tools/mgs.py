#!/usr/bin/env python3

# This script is intended to generate `rina/mgs.json`
# Data source: `./mgs_src.json` from my `rebuilder` project

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
        help="cut the dict to this frequency (default: %(default)s)",
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
    """
    Source format: [num][prefix]-[suffix] (e.g., 001AVGP-136)
    Output format: {prefix: [num1, num2, ...], ...}
    Only keeps prefix-num pairs that appear more than `args.freq` times
    """
    args = parse_args()

    src = Path(__file__).resolve().with_name("mgs_src.json")
    dst = src.parents[1].joinpath("rina/mgs.json")
    print(f"Source: {src}\nOutput: {dst}", file=sys.stderr)

    # copy source from `rebuilder` project
    try:
        shutil.copy(src.parents[2].joinpath("rebuilder/data/mgs_src.json"), src)
    except FileNotFoundError as e:
        pass
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

    # Measure the frequency and sort the groups:
    # 1. with prefix so it looks nice
    # 2. with frequency, from the highest to the lowest, so the program starts
    #    with a more common `num`
    # groups = [(prefix, num, frequency), ...]
    groups = sorted(((*k, len(v)) for k, v in groups.items()))
    get_third = itemgetter(2)
    groups.sort(key=get_third, reverse=True)
    total = sum(map(get_third, groups))

    # Slice the list so that all items have a frequency >= args.freq
    groups = groups[: reverse_bisect_left(groups, args.freq, 2)]
    if not groups:
        sys.exit("Empty result.")

    # Produce the result
    result = defaultdict(list)
    for prefix, num, _ in groups:
        result[prefix].append(num)

    covered = sum(map(get_third, groups))
    pre_len = frozenset(len(v[0]) for v in groups)
    num_len = frozenset(len(v[1]) for v in groups)
    print(
        "Result:\n"
        f"  Dictionary length: {len(result)}\n"
        f"  Product coverage : {covered} / {total} ({covered / total:.1%})\n"
        f"  Frequency range  : {min(map(get_third, groups))} - {max(map(get_third, groups))}\n"
        f"  Num len range    : {{{min(num_len)},{max(num_len)}}}\n"
        f"  Prefix len range : {{{min(pre_len)},{max(pre_len)}}}\n"
        f"  Suffix len range : {{{min(sfx_len)},{max(sfx_len)}}}"
    )

    try:
        with open(dst, "r+", encoding="utf-8") as f:
            if json.load(f) == result:
                print(f"{dst.name} is up to date.", file=sys.stderr)
                return
            f.seek(0)
            json.dump(result, f, separators=(",", ":"))
            f.truncate()
    except (FileNotFoundError, ValueError):
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(result, f, separators=(",", ":"))
    print(f"Update: '{dst}'", file=sys.stderr)


if __name__ == "__main__":
    main()
