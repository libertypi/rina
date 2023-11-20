#!/usr/bin/env python3

# This script is intended to generate `rina/useragents.json`
# Data source: `./useragents_src.json` from
# https://www.useragents.me/#most-common-desktop-useragents-json-csv

import json
from pathlib import Path


def main():
    source = Path(__file__).resolve().with_name("useragents_src.json")
    dest = source.parent.parent.joinpath("rina/useragents.json")

    print(f"Source: {source}\nOutput: {dest}")

    with open(source, "r", encoding="utf-8") as f:
        useragents = (d["ua"] for d in json.load(f))
        useragents = sorted(set(filter(None, map(str.strip, useragents))))

    if not useragents:
        raise ValueError(f"no valid useragents found in {source}.")

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(useragents, f, separators=(",", ":"))

    print(f"{len(useragents)} useragents has been written to disk.")


if __name__ == "__main__":
    main()
