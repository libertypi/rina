#!/usr/bin/env python3

# This script is intended to generate `rina/useragents.json`
# Data source: `./useragents_src.json` from
# https://www.useragents.me/#most-common-desktop-useragents-json-csv

import json
from pathlib import Path
from argparse import ArgumentParser


def parse_args(src: Path, dst: Path):
    parser = ArgumentParser()
    parser.add_argument(
        "-p",
        dest="pct",
        action="store",
        type=float,
        default=0.5,
        help="includes only useragents above this share percentage (default: %(default)s)",
    )
    parser.add_argument(
        "-s",
        dest="src",
        action="store",
        type=Path,
        default=src,
        help="path to the data source (default: %(default)s)",
    )
    parser.add_argument(
        "-d",
        dest="dst",
        action="store",
        type=Path,
        default=dst,
        help="path to the output file (default: %(default)s)",
    )
    return parser.parse_args()


def main():
    src = Path(__file__).resolve().with_name("useragents_src.json")
    args = parse_args(
        src=src,
        dst=src.parent.parent.joinpath("rina/useragents.json"),
    )
    print(f"Source: {args.src}\nOutput: {args.dst}")

    with open(args.src, "r", encoding="utf-8") as f:
        useragents = (d["ua"] for d in json.load(f) if d["pct"] >= args.pct)
        useragents = sorted(set(filter(None, map(str.strip, useragents))))

    if not useragents:
        raise ValueError(f"no valid useragents found in {src}.")

    with open(args.dst, "w", encoding="utf-8") as f:
        json.dump(useragents, f, separators=(",", ":"))

    print(f"{len(useragents)} useragents has been written to disk.")


if __name__ == "__main__":
    main()
