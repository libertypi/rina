#!/usr/bin/env python3

# This script is intended to generate avinfo/_mgs.py
# run `make_dict.py -h` for help

if __name__ != "__main__":
    raise ImportError("This file should not be imported.")

import json
import re
import sys
from argparse import ArgumentParser
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from itertools import chain
from operator import itemgetter
from pathlib import Path
from urllib.parse import urljoin

import requests
from lxml.etree import XPath
from lxml.html import fromstring
from urllib3 import Retry

FILE = Path(__file__).resolve()
JSON_FILE = FILE.with_name("mgs.json")
path = FILE.parent.parent
PY_FILE = path.joinpath("avinfo", "_mgs.py")
sys.path.insert(0, str(path))
del path

from avinfo._mgs import mgs_map

ENTRY_PAGE = "https://www.mgstage.com/ppv/makers.php?id=osusume"


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "-s",
        dest="size",
        action="store",
        type=int,
        default=1024,
        help="max size of the dict, 0 for unlimited (default %(default)s)",
    )
    parser.add_argument(
        "-l",
        dest="local",
        action="store_true",
        help="use cached data instead of web scraping (default %(default)s)",
    )
    return parser.parse_args()


def _init_session():
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
    adapter = requests.adapters.HTTPAdapter(
        max_retries=Retry(total=5,
                          status_forcelist=frozenset((500, 502, 503, 504)),
                          backoff_factor=0.1))
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_tree(url: str):
    try:
        response = session.get(url, timeout=(6.1, 60))
        response.raise_for_status()
    except requests.HTTPError:
        pass
    except requests.RequestException as e:
        print(e, file=sys.stderr)
    else:
        return fromstring(response.content, base_url=response.url)


def scrape_mgs(matcher):
    """Scrape product ids from web, yields match objects."""

    result = set()
    result_add = result.add

    xp = XPath(
        '//article[@id="center_column"]'
        '//div[@class="rank_list"]//li/h5/a/@href',
        smart_strings=False)

    data = chain.from_iterable(map(xp, _get_product_trees()))
    for m in filter(None, map(matcher, data)):
        result_add(m[1])
        yield m

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(result), f, separators=(",", ":"))


def _get_product_trees():
    """Yield trees of product pages."""

    xp_maker = XPath(
        '//div[@id="maker_list"]/div[@class="maker_list_box"]'
        '/dl/dt/a[2]/@href[contains(., "search.php")]',
        smart_strings=False)
    xp_last = XPath(
        'string(//div[@class="pager_search_bottom"]'
        '//a[contains(., "最後")]/@href)',
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
        del makers, visited

        fts = as_completed(pool)
        pool = []
        for tree in fts:
            tree = tree.result()
            try:
                url = tree.base_url
            except AttributeError:
                continue
            print(f"Processing: {url}")
            yield tree

            last = xp_last(tree).rpartition("page=")
            if last[0] and last[2].isdigit():
                url = urljoin(url, last[0] + last[1])
                last = int(last[2]) + 1
                pool.extend(
                    ex.submit(get_tree, f"{url}{i}") for i in range(2, last))

        for tree in as_completed(pool):
            tree = tree.result()
            try:
                print(f"Processing: {tree.base_url}")
            except AttributeError:
                continue
            yield tree


def main():

    args = parse_args()

    matcher = r"(([0-9]*)([A-Za-z]{2,10})-([0-9]{2,8}))"
    if args.local:
        matcher = re.compile(matcher).fullmatch
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = filter(None, map(matcher, json.load(f)))
    else:
        matcher = re.compile(rf"/{matcher}/?$").search
        data = scrape_mgs(matcher)

    result = defaultdict(set)
    for i in data:
        result[i[2], i[3].lower()].add(int(i[4]))

    # [0]: frequency, [1]: digit, [2]: prefix
    result = [(len(v), k[0], k[1]) for k, v in result.items()]
    uniq_ids = sum(map(itemgetter(0), result))
    uniq_prefix = len(result)

    # eliminate same prefix with different digits
    # [0]: prefix, [1]: digit
    result.sort()
    result[:] = {t[2]: t[1] for t in result}.items()

    i = (len(result) - args.size) if args.size > 0 else 0
    if i > 0:
        result = result[i:]

    result.sort(key=itemgetter(1, 0))
    result = dict(result)
    digit_len = set(map(len, result.values()))

    print(result)
    print(f"\nUnique IDs: {uniq_ids}",
          f"Unique prefixes: {uniq_prefix}",
          f'Prefix digit range: {{{min(digit_len) or ""},{max(digit_len)}}}',
          f"Dict size (old): {len(mgs_map)}",
          f"Dict size (new): {len(result)}",
          sep="\n")

    if result == mgs_map:
        print("Dictionary is up to date.")
        return

    print("Writing changes to file...")
    i = " " * 4
    with open(PY_FILE, "w", encoding="utf-8") as f:
        f.write(f"# Generated by {FILE.name}\n"
                f"# Dictionary size: {len(result)}\n"
                f"# Update: {datetime.now().ctime()}\n\n")
        f.write("mgs_map = {\n")
        f.writelines(f'{i}"{k}": "{v}",\n' for k, v in result.items())
        f.write("}\n")
    print("Done.")


session = _init_session()
main()
