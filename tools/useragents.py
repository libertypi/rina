#!/usr/bin/env python3

# This script is intended to generate `rina/useragents.json`
# Data source: `./useragents_src.json` from
# https://www.useragents.me/#most-common-desktop-useragents-json-csv

import json
from argparse import ArgumentParser
from pathlib import Path


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "-p",
        dest="pct",
        action="store",
        type=float,
        default=0.5,
        help="includes only useragents above this share percentage (default: %(default)s)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    src = Path(__file__).resolve().with_name("useragents_src.json")
    dst = src.parents[1].joinpath("rina/useragents.json")
    print(f"Source: {src}\nOutput: {dst}")

    with open(src, "r", encoding="utf-8") as f:
        result = (d["ua"] for d in json.load(f) if d["pct"] >= args.pct)
        result = sorted(set(filter(None, map(str.strip, result))))

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
