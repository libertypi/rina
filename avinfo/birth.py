from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from avinfo._utils import (SEP_SLIM, XPath, get_tree, re_search, str_to_epoch,
                           strftime, xpath)


class ProductFilter:
    """actress page filter"""

    def __init__(self, active: float, uncensored: bool, solo: bool) -> None:
        self._active = active
        # The funcions in this list expect a 'tree_product' element. If any
        # returns False, the product should be filtered.
        self._filters = []
        if uncensored:
            # return true if the product is uncensored
            self._filters.append(XPath('contains(p[@class="moza"], "モザイクなし")'))
        if solo:
            # return true is the product contains only one actress
            self._filters.append(XPath('count(p[@class="cast"]/a) <= 1'))

    def run(self, tree) -> int:

        tree = tree.find('.//div[@class="act-video-list"]')
        path_product = self._get_col_path(tree, "作品タイトル", 2)
        path_date = self._get_col_path(tree, "発売日", 3)

        for tr in xpath('table/tr[count(td) > 3]')(tree):
            tree_product = tr.find(path_product)
            if not all(f(tree_product) for f in self._filters):
                continue
            title = tree_product.find('h3[@class="ttl"]').text_content()
            if "東熱激情" in title:
                continue
            if "再配信" in title or "同一内容" in title:
                date = title
            else:
                date = tr.findtext(path_date)
            date = str_to_epoch(date)
            if date and date >= self._active:
                return date

    @staticmethod
    def _get_col_path(tree, title: str, default: int):
        """find the path accroding to column title"""
        tree = xpath('//tr/th[contains(., $title)]')(tree, title=title)
        if tree:
            default = int(xpath('count(preceding-sibling::th) + 1')(tree[0]))
        return f'td[{default}]'


def get_lastpage(tree):
    """return the page number of the last page, or 1."""
    last = tree.xpath(
        './/section[@id="main-area"]//div[@class="pagination"]//a/text()')
    for last in reversed(last):
        last = re_search(r'\d+', last)
        if last:
            return int(last[0])
    return 1


xpath_actress_list = XPath(
    './/section[@id="main-area"]/section[contains(@class, "main-column")]'
    '//td/*[@class="ttl"]/a/@href[contains(., "actress")]',
    smart_strings=False)


def main(args):

    domain = "http://www.minnano-av.com"
    _filter = ProductFilter(active=args.active,
                            uncensored=args.uncensored,
                            solo=args.solo)

    with ThreadPoolExecutor(max_workers=6) as ex:

        # scrape the 1st index of each birth year; put the 2nd-last pages
        # into pool.
        url = f"{domain}/actress_list.php"
        index_pool = [
            ex.submit(get_tree, url, params={"birthday": i})
            for i in args.target
        ]
        for ft in as_completed(index_pool):
            tree = ft.result()
            if tree is not None:
                index_pool.extend(
                    ex.submit(get_tree, tree.base_url, params={"page": i})
                    for i in range(2,
                                   get_lastpage(tree) + 1))

        # parse all the index pages
        page_pool = {}
        for ft in as_completed(index_pool):
            tree = ft.result()
            if tree is None:
                continue
            for url in xpath_actress_list(tree):
                if url not in page_pool:
                    page_pool[url] = ex.submit(get_tree, urljoin(domain, url))
        del index_pool

        # scan & filter the actress pages
        total = len(page_pool)
        result = 0
        for ft in as_completed(page_pool.values()):

            tree = ft.result()
            if tree is None:
                continue
            tree = tree.find('.//section[@id="main-area"]')
            date = _filter.run(tree)
            if not date:
                continue

            name = tree.findtext('section/h1')
            try:
                birth = tree.findtext(
                    './/div[@class="act-profile"]//tr/td[span="生年月日"]/p'
                ).split(maxsplit=1)[0]
            except AttributeError:
                birth = None
            print(f"Name: {name}",
                  f"Birth: {birth}",
                  f"Latest: {strftime(date)}",
                  f"Url: {tree.base_url}",
                  SEP_SLIM,
                  sep="\n")
            result += 1

    print(f'Scanned: {total}, found: {result}.')
