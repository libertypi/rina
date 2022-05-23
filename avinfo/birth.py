import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from avinfo._utils import SEP_SLIM, get_tree, re_search, str_to_epoch, xpath


class ProductFilter:
    """actress page filter"""

    def __init__(self, active: int, uncensored: bool, solo: bool) -> None:
        self._active = (datetime.datetime.now() -
                        datetime.timedelta(days=active * 365)).timestamp()
        # The funcions in this list expect a 'tree_product' element. If any
        # returns False, the product should be filtered.
        self._filters = []
        if uncensored:
            # return true if the product is uncensored
            self._filters.append(xpath('contains(p[@class="moza"], "モザイクなし")'))
        if solo:
            # return true is the product contains only one actress
            self._filters.append(xpath('count(p[@class="cast"]/a) <= 1'))

    def run(self, tree) -> int:

        tree = tree.find('.//div[@class="act-video-list"]')

        count = 0
        path_product, path_date = self._get_col(tree)

        for tr in xpath('table/tr[count(td) = 4]')(tree):
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
                count += 1

        return count

    @staticmethod
    def _get_col(tree):
        # find the column of product and date
        xp = xpath('count(//tr/th[contains(., $title)]/preceding-sibling::th)')
        path_product = int(xp(tree, title="作品タイトル") or 1) + 1
        path_date = int(xp(tree, title="発売日") or 2) + 1
        return f'td[{path_product}]', f'td[{path_date}]'


def get_lastpage(tree):
    """return the page number of the last page, or 1."""
    nav = tree.find('.//section[@id="main-area"]//div[@class="pagination"]')
    if nav is None:
        return 1
    last = nav.findtext('.//a[@title="Last"]')
    if last:
        return int(re_search(r'[\d]+', last)[0])
    for last in reversed(nav.xpath('.//a/text()')):
        last = re_search(r'[\d]+', last)
        if last:
            return int(last[0])
    return 1


def main(args):

    domain = "http://www.minnano-av.com"
    url = f"{domain}/actress_list.php"
    _filter = ProductFilter(active=args.active,
                            uncensored=args.uncensored,
                            solo=args.solo)

    # find the total page count
    tree = get_tree(url, params={"birthday": args.target})
    if tree is None:
        exit("Connection error.")
    total = get_lastpage(tree)

    # parse the first page
    xp = xpath('.//section[@id="main-area"]'
               '/section[contains(@class, "main-column")]'
               '//tr/td/a[starts-with(@href, "actress")]/@href')
    page_list = set(xp(tree))

    with ThreadPoolExecutor(max_workers=5) as ex:

        # scan & parse all the list pages
        for ft in as_completed(
                ex.submit(
                    get_tree, url, params={
                        "birthday": args.target,
                        "page": i
                    }) for i in range(2, total + 1)):
            tree = ft.result()
            if tree is not None:
                page_list.update(xp(tree))

        total = len(page_list)
        result = 0

        # scan & filter the actress pages
        for ft in as_completed(
                ex.submit(get_tree, urljoin(domain, i)) for i in page_list):

            tree = ft.result()
            if tree is None:
                continue
            tree = tree.find('.//section[@id="main-area"]')
            count = _filter.run(tree)
            if not count:
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
                  f"Count: {count}",
                  f"Url: {tree.base_url}",
                  f"{SEP_SLIM}",
                  sep="\n")
            result += 1

    print(f'Total: {total}, result: {result}.', sep="\n")
