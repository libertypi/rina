#!/usr/bin/env python3

if __name__ != "__main__":
    raise ImportError("This file should not be imported.")

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import chain
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from avinfo import scraper
from avinfo._mgs import mgs_map
from avinfo._utils import get_tree, re_compile, xpath


def make_mgs_map(freq_thresh=5):

    result = defaultdict(set)
    matcher = re_compile(r'/([0-9]*)([A-Za-z]+)-([0-9]+)/?$').search
    xp_id = xpath('//article[@id="center_column"]'
                  '//div[@class="rank_list"]//h5/a/@href')

    for tree in _scan_mgs("/ppv/makers.php?id=osusume"):
        try:
            print(f"Processing: {tree.base_url}")
        except AttributeError:
            continue
        for m in filter(None, map(matcher, xp_id(tree))):
            result[m[1], m[2].lower()].add(m[3])

    print(f"{len(result)} unique prefixes fetched.")

    result = [k for k, v in result.items() if len(v) >= freq_thresh]
    result.sort()
    print(f"{len(result)} common prefixes extracted.")

    result = {i[1]: i[0] for i in result}
    if result != mgs_map:
        print(f"difference found ({len(mgs_map)} -> {len(result)}):")
        print(result)
    else:
        print("Dictionary up to date.")


def _scan_mgs(url, max_page=25):
    """input in initial url, output trees of maker pages."""

    domain = "https://www.mgstage.com/"
    xp_maker = xpath('//div[@id="maker_list"]/div[@class="maker_list_box"]'
                     '/dl/dt/a[2]/@href[contains(., "search.php")]')
    xp_last = xpath('string(.//div[@class="pager_search_bottom"]'
                    '//a[contains(., "最後")]/@href)')

    url = urljoin(domain, url)
    tree = get_tree(url)
    makers = tree.xpath('//div[@id="maker_list"]/dl[@class="navi"]'
                        '/dd/a/@href[contains(., "makers.php")]')
    makers = {urljoin(domain, u) for u in makers}
    makers.discard(url)

    with ThreadPoolExecutor() as ex:

        pool = []
        visited = set()
        for tree in chain(ex.map(get_tree, makers), (tree,)):
            try:
                makers = set(xp_maker(tree))
            except TypeError:
                continue
            print(f"Scanning: {tree.base_url}")
            pool.extend(
                ex.submit(get_tree, urljoin(domain, u))
                for u in makers
                if u not in visited)
            visited.update(makers)
        del makers, visited

        fts = as_completed(pool)
        pool = []
        for tree in fts:
            tree = tree.result()
            try:
                last = xp_last(tree).rpartition("page=")[2]
            except TypeError:
                continue
            yield tree

            if last.isdigit():
                last = min(int(last), max_page) + 1
                url = tree.base_url
                pool.extend(
                    ex.submit(get_tree, f"{url}&page={i}")
                    for i in range(2, last))

        for tree in as_completed(pool):
            yield tree.result()


make_mgs_map()
