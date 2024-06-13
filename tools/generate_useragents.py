#!/usr/bin/env python3

"""
Generate useragents.json for Rina.
Source: useragents_src.json
    https://www.useragents.me/#most-common-desktop-useragents-json-csv
Dest: rina/useragents.json
"""

import json
from argparse import ArgumentParser
from pathlib import Path


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "-n",
        dest="max",
        action="store",
        type=float,
        default=20,
        help="maximun number of UAs to draw from data (default: %(default)s)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    src = Path(__file__).resolve().with_name("useragents_src.json")
    dst = src.parents[1].joinpath("rina/useragents.json")
    print(f"Source: {src}\nOutput: {dst}")

    with open(src, "r", encoding="utf-8") as f:
        data = {d["ua"].strip(): d["pct"] for d in json.load(f)}

    result = sorted(filter(None, data), key=data.get, reverse=True)[: args.max]

    if not result:
        raise ValueError(f"no valid useragents found in {src}.")

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
    print(f"{len(result)} useragents has been written to disk.")


if __name__ == "__main__":
    main()
