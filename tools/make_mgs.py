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
from urllib.parse import urljoin

import requests
from lxml.etree import XPath
from lxml.html import fromstring
from urllib3 import Retry

ENTRY_PAGE = "https://www.mgstage.com/ppv/makers.php?id=osusume"
DATAFILE = Path(__file__).resolve().with_name("mgsdata.json")
OUTPUT = DATAFILE.parent.parent.joinpath("avinfo", "mgs.json")
session = None


def parse_args():

    parser = ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-s",
        dest="size",
        action="store",
        type=int,
        default=1365,
        help="cut the dict to this size, 0 for unlimited (default %(default)s)",
    )
    group.add_argument(
        "-f",
        dest="freq",
        action="store",
        type=int,
        help="cut the dict to this frequency",
    )
    parser.add_argument(
        "-l",
        dest="local",
        action="store_true",
        help="use cached data instead of web scraping (default %(default)s)",
    )
    return parser.parse_args()


def init_session():
    global session
    session = requests.Session()
    session.cookies.set_cookie(
        requests.cookies.create_cookie(domain="mgstage.com",
                                       name="adc",
                                       value="1"))
    session.headers.update({
        "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/88.0.4324.104 Safari/537.36'
    })
    retry = Retry(total=5,
                  status_forcelist=frozenset((500, 502, 503, 504)),
                  backoff_factor=0.2)
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)


def get_tree(url: str):
    try:
        response = session.get(url, timeout=(9.1, 60))
        response.raise_for_status()
    except requests.HTTPError:
        pass
    except requests.RequestException as e:
        print(e, file=sys.stderr)
    else:
        return fromstring(response.content, base_url=response.url)


def scrape():
    """Yield urls containing product ids."""

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
        '//article[@id="center_column"]'
        '//div[@class="rank_list"]//li/h5/a/@href',
        smart_strings=False)

    tree = get_tree(ENTRY_PAGE)
    url = tree.base_url
    makers = tree.xpath('//div[@id="maker_list"]/dl[@class="navi"]'
                        '/dd/a/@href[contains(., "makers.php")]')
    makers = {urljoin(url, u) for u in makers}
    makers.discard(url)

    with ThreadPoolExecutor() as ex:

        pool = []
        visited = set()
        for tree in chain(ex.map(get_tree, makers), (tree,)):
            try:
                url = tree.base_url
            except AttributeError:
                continue
            print(f"Scanning: {url}")
            makers.clear()
            makers.update(urljoin(url, u) for u in xp_maker(tree))
            makers.difference_update(visited)
            pool.extend(ex.submit(get_tree, u) for u in makers)
            visited.update(makers)
        del visited

        makers = as_completed(pool)
        pool = []
        for tree in makers:
            tree = tree.result()
            try:
                url = tree.base_url
            except AttributeError:
                continue
            print(f"Processing: {url}")
            last = xp_last(tree).rpartition("page=")
            if last[0] and last[2].isdigit():
                url = urljoin(url, last[0] + last[1])
                last = int(last[2]) + 1
                pool.extend(
                    ex.submit(get_tree, f"{url}{i}") for i in range(2, last))
            yield from xp_id(tree)

        for tree in as_completed(pool):
            tree = tree.result()
            try:
                print(f"Processing: {tree.base_url}")
            except AttributeError:
                continue
            yield from xp_id(tree)


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

    regex = r"(([0-9]*)([A-Za-z]{2,10})-([0-9]{2,8}))"
    group = defaultdict(set)

    if args.local:
        regex = re.compile(regex).fullmatch
        with open(DATAFILE, "rb") as f:
            data = json.load(f)
        for i in filter(None, map(regex, data)):
            group[i[3].lower(), i[2]].add(int(i[4]))
    else:
        regex = re.compile(rf"/{regex}/?$").search
        data = set()
        add = data.add
        for i in filter(None, map(regex, scrape())):
            add(i[1])
            group[i[3].lower(), i[2]].add(int(i[4]))
        with open(DATAFILE, "w", encoding="utf-8") as f:
            json.dump(sorted(data), f, separators=(",", ":"))
        del add

    # (prefix, digit): frequency
    group = dict(zip(group, map(len, group.values())))

    # list of tuples
    # [0]: prefix, [1]: digit
    data = sorted(group)
    data.sort(key=group.get, reverse=True)

    # Trim the 2-tuple list to `size` or `freq`. For the prefixes with multiple
    # digits, keep the most frequent one.
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
        sys.exit("Empty result.")

    size = len(data)
    used_entry = sum(map(group.get, data))
    total_entry = sum(group.values())
    digit_len = frozenset(map(len, tmp.values()))
    prefix_len = frozenset(map(len, tmp))
    print(
        f"Dictionary size: {size}\n"
        f"Product coverage: {used_entry} / {total_entry} ({used_entry / total_entry:.1%})\n"
        f"Prefix coverage: {size} / {len(group)} ({size / len(group):.1%})\n"
        f"Minimum frequency: {group[data[-1]]}\n"
        f"Key length: {{{min(prefix_len)},{max(prefix_len)}}}\n"
        f'Value length: {{{min(digit_len) or ""},{max(digit_len)}}}',)

    data.sort(key=itemgetter(1, 0))
    print(f"Writing '{OUTPUT}'...", end="", flush=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(dict(data), f, separators=(",", ":"))
    print("done.")


if __name__ == "__main__":
    main()
