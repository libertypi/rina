#!/usr/bin/env python3

# This script is intended to generate avinfo/mgs.json
# run `make_dict.py -h` for help

import json
import re
import sys
from argparse import ArgumentParser
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import chain
from operator import itemgetter
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from lxml.etree import XPath
from lxml.html import HtmlElement, fromstring
from urllib3 import Retry

STDERR = sys.stderr
session = None


def parse_args():

    parser = ArgumentParser()
    parser.add_argument(
        "-l",
        dest="local",
        action="store_true",
        help="use local cache instead of web scraping (default: %(default)s)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-s",
        dest="size",
        action="store",
        type=int,
        default=1365,
        help="cut the dict to this size, 0 for unlimited (default: %(default)s)",
    )
    group.add_argument(
        "-f",
        dest="freq",
        action="store",
        type=int,
        help="cut the dict to this frequency",
    )
    return parser.parse_args()


def init_session():
    global session
    session = requests.Session()
    session.cookies.set_cookie(
        requests.cookies.create_cookie(
            domain="mgstage.com",
            name="adc",
            value="1",
        ))
    session.headers.update({
        "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/88.0.4324.104 Safari/537.36'
    })
    retry = Retry(total=7,
                  status_forcelist=frozenset((500, 502, 503, 504)),
                  backoff_factor=0.2)
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)


def get_tree(url: str) -> Optional[HtmlElement]:
    try:
        r = session.get(url, timeout=(9.1, 60))
        r.raise_for_status()
    except requests.RequestException as e:
        print(e, file=STDERR)
    else:
        return fromstring(r.content, base_url=r.url)


def scrape():
    """Yield urls containing product ids."""

    url = "https://www.mgstage.com/ppv/makers.php?id=osusume"

    if not session:
        init_session()

    xp_maker = XPath(
        '//div[@id="maker_list"]/div[@class="maker_list_box"]'
        '/dl/dt/a[2]/@href[contains(., "search.php")]',
        smart_strings=False)
    xp_last = XPath(
        'string(//div[@class="pager_search_bottom"]'
        '//a[contains(., "最後")]/@href)',
        smart_strings=False)
    xp_id = XPath(
        '//article[@id="center_column"]//div[@class="rank_list"]'
        '//li/h5/a/@href',
        smart_strings=False)
    page_matcher = re.compile(r"(.*page=)(\d+)(.*)").fullmatch

    tree = get_tree(url)
    url = tree.base_url
    results = tree.xpath('//div[@id="maker_list"]/dl[@class="navi"]'
                         '/dd/a/@href[contains(., "makers.php")]')
    results = {urljoin(url, u) for u in results}
    results.discard(url)

    with ThreadPoolExecutor() as ex:

        fmt = _get_urlfmt(len(results) + 1)
        results = chain(ex.map(get_tree, results), (tree,))
        pool = {}
        for i, tree in enumerate(results, 1):
            try:
                url = tree.base_url
            except AttributeError:
                continue
            print(fmt(i, url), file=STDERR)
            for m in xp_maker(tree):
                m = urljoin(url, m)
                if m not in pool:
                    pool[m] = ex.submit(get_tree, m)

        fmt = _get_urlfmt(len(pool))
        results = as_completed(pool.values())
        pool = []
        for i, tree in enumerate(results, 1):
            tree = tree.result()
            try:
                url = tree.base_url
            except AttributeError:
                continue
            print(fmt(i, url), file=STDERR)

            m = page_matcher(xp_last(tree))
            if m:
                url = f"{urljoin(url, m[1])}{{}}{m[3]}".format
                i = int(m[2]) + 1
                pool.extend(ex.submit(get_tree, url(j)) for j in range(2, i))
            yield from xp_id(tree)

        fmt = _get_urlfmt(len(pool))
        results = as_completed(pool)
        del pool
        for i, tree in enumerate(results, 1):
            tree = tree.result()
            try:
                print(fmt(i, tree.base_url), file=STDERR)
            except AttributeError:
                pass
            else:
                yield from xp_id(tree)


def _get_urlfmt(total: int):
    return f"[{{:{len(str(total))}d}}/{total}] {{}}".format


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

    args = parse_args()

    datafile = Path(__file__).resolve().with_name("mgsdata.json")
    outputfile = datafile.parent.parent.joinpath("avinfo", "mgs.json")

    if args.local:
        with open(datafile, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        regex = re.compile(r"product_detail/([A-Za-z0-9_-]+)/?$").search
        data = map(itemgetter(1), filter(None, map(regex, scrape())))
        data = sorted(frozenset(data))
        with open(datafile, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))

    regex = re.compile(r"([0-9]*)([a-z]{2,10})-([0-9]{2,8})").fullmatch
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
    if args.freq is None:
        i = args.size if args.size > 0 else len(data)
        for k, v in data:
            if setdefault(k, v) == v:
                i -= 1
                if not i:
                    break
    else:
        for k, v in bisect_slice(data, args.freq, group):
            setdefault(k, v)
    data[:] = tmp.items()
    if not data:
        print("Empty result.", file=STDERR)
        return

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
        with open(outputfile, "r", encoding="utf-8") as f:
            if json.load(f) == data:
                print("Dictionary is up to date.", file=STDERR)
                return
    except (FileNotFoundError, ValueError):
        pass

    print(f"Writing '{outputfile}'...", end="", flush=True, file=STDERR)
    with open(outputfile, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print("done.", file=STDERR)


if __name__ == "__main__":
    main()
