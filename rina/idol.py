import os
import re
from abc import ABC
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Generator
from urllib.parse import quote, urljoin

from rina.connection import HtmlElement, get_tree, xpath
from rina.scandir import FileScanner, get_scanner
from rina.utils import AVInfo, Status, date_searcher, re_search, re_sub

is_cjk_name = r"(?=\w*?[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7a3])(\w{2,20})"
name_finder = re.compile(rf"(?:^|[】」』｝）》\])]){is_cjk_name}(?:$|[【「『｛（《\[(])").search
is_cjk_name = re.compile(is_cjk_name).fullmatch
name_cleaner = re.compile(r"\d+歳|[\s 　]").sub
split_names = re.compile(r"\s*[\n、/／●・,＝=]\s*").split


@lru_cache(maxsize=256)
def clean_name(string: str) -> str:
    m = name_finder(name_cleaner("", string))
    return m[1] if m else ""


def match_name(keyword: str, *names: str):
    return any(clean_name(s) == keyword for s in names)


@dataclass
class SearchResult:
    name: str = None
    birth: str = None
    alias: set = None


class Wiki(ABC):
    @classmethod
    def search(cls, keyword: str):
        result = cls._search(keyword)
        if not result:
            return

        alias = result.alias
        if alias:
            result.alias = set(filter(None, map(clean_name, alias)))
        else:
            result.alias = set()

        name = result.name
        if name:
            name = clean_name(name)
            if name:
                result.alias.add(name)
            result.name = name

        b = result.birth
        if b:
            result.birth = f'{int(b["y"])}-{int(b["m"]):02d}-{int(b["d"]):02d}'

        if name or b or result.alias:
            return result

    @classmethod
    def _search(cls, keyword: str) -> SearchResult:
        raise NotImplementedError


class Wikipedia(Wiki):
    @staticmethod
    def _search(keyword: str):
        tree = get_tree(f"https://ja.wikipedia.org/wiki/{keyword}")
        if tree is None or tree.find('.//a[@title="Template:AV女優"]') is None:
            return

        name = tree.find('.//*[@id="firstHeading"]').text_content()
        box = tree.find('.//div[@id="mw-content-text"]//table[@class="infobox"]')
        if not name or box is None:
            return

        birth = None
        alias = xpath('.//caption[@*="name"]/text()[normalize-space()]')(box)
        xp = xpath("td//text()[normalize-space()]")

        for tr in box.iterfind("tbody/tr[th][td]"):
            k = tr.find("th").text_content()
            if not birth and "生年月日" in k:
                birth = date_searcher("".join(xp(tr)))
            elif "別名" in k:
                alias.extend(j for i in xp(tr) for j in split_names(i))

        return SearchResult(name=name, birth=birth, alias=alias)


class MinnanoAV(Wiki):
    @classmethod
    def _search(cls, keyword: str):
        tree = get_tree(
            "http://www.minnano-av.com/search_result.php",
            params={"search_scope": "actress", "search_word": keyword},
        )
        if tree is None:
            return

        if "/search_result.php" in tree.base_url:
            tree = cls._scan_search_page(keyword, tree)
            if tree is None:
                return

        tree = tree.find('.//section[@id="main-area"]')
        try:
            name = clean_name(tree.findtext("section/h1"))
        except (AttributeError, TypeError):
            return

        birth = None
        alias = []
        for td in tree.iterfind('.//div[@class="act-profile"]/table//td[span][p]'):
            title = td.findtext("span", "")
            if "別名" in title:
                alias.append(td.findtext("p", ""))
            elif not birth and "生年月日" in title:
                birth = date_searcher(td.findtext("p", ""))

        return SearchResult(name=name, birth=birth, alias=alias)

    @staticmethod
    def _scan_search_page(keyword: str, tree: HtmlElement):
        """Return if there's only one match."""

        result = None
        for a in xpath(
            './/section[@id="main-area"]'
            '//table[contains(@class, "actress")]'
            '//td[not(contains(., "重複"))]/h2/a[@href]'
        )(tree):
            if match_name(keyword, a.text):
                href = a.get("href").partition("?")[0]
                if not result:
                    result = href
                elif result != href:
                    return

        if result:
            return get_tree(urljoin(tree.base_url, result))


class AVRevolution(Wiki):
    @staticmethod
    def _search(keyword: str):
        tree = get_tree(
            f"http://neo-adultmovie-revolution.com/db/jyoyuu_betumei_db/?q={keyword}"
        )
        if tree is None:
            return

        title_seen = result = None
        alias_xp = xpath('div[3]/div/text()[not(contains(., "別名無"))]')

        for row in xpath(
            './/div[@class="container"]'
            '/div[contains(@class,"row") and @style and div[1]/a]'
        )(tree):
            try:
                a = row.find("div[1]/a[@href]")
                title = clean_name(a.text_content())
                name = re_search(r"/([^/]+)/?$", a.get("href"))[1]
            except (AttributeError, TypeError):
                continue

            if result:
                if title == title_seen and name != result.name:
                    return
                continue

            alias = alias_xp(row)
            alias.append(title)
            if match_name(keyword, *alias):
                title_seen = title
                result = SearchResult(name=name, alias=alias)

        return result


class Seesaawiki(Wiki):
    @staticmethod
    def _search(keyword: str):
        try:
            stack = [
                "https://seesaawiki.jp/av_neme/d/" + quote(keyword, encoding="euc-jp")
            ]
        except UnicodeEncodeError:
            return

        while True:
            tree = get_tree(stack[-1])
            if tree is None:
                return

            text = tree.findtext('.//h3[@id="content_1"]')
            if not (text and re_search(r"(女優名|名前).*?変更", text)):
                break

            url = xpath(
                'string(.//div[@id="content_block_1-body" '
                'and contains(., "移動")]/span/a/@href)'
            )(tree)
            if url:
                url = urljoin(tree.base_url, url)
                if url not in stack:
                    stack.append(url)
                    continue
            return

        name = tree.findtext('.//div[@id="page-header-inner"]/div[@class="title"]//h2')
        if not name:
            return

        box = tree.find('.//*[@id="content_block_2"]')
        if box is None:
            return SearchResult(name=name)
        if box.tag == "table":
            box = (
                (tr.find("th").text_content(), tr.find("td").text_content())
                for tr in box.iterfind(".//tr[th][td]")
            )
        else:
            box = (i.split("：", 1) for i in box.text.splitlines() if "：" in i)

        stack.clear()
        birth = None
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = date_searcher(v)
            elif re_search(r"旧名|別名|名前|女優名", k):
                stack.extend(split_names(v))

        return SearchResult(name=name, birth=birth, alias=stack)


class Msin(Wiki):
    @classmethod
    def _search(cls, keyword: str):
        tree = get_tree(
            "https://db.msin.jp/branch/search",
            params={"sort": "jp.actress", "str": keyword},
        )
        if tree is None:
            return

        if "/actress?str=" in tree.base_url:
            return cls._scan_search_page(keyword, tree)

        tree = tree.find('.//div[@id="top_content"]//div[@class="act_ditail"]')
        try:
            name = clean_name(
                tree.findtext('.//div[@class="act_name"]/span[@class="mv_name"]')
            )
        except (AttributeError, TypeError):
            return

        alias = split_names(xpath('string(.//span[@class="mv_anotherName"])')(tree))
        if match_name(keyword, name, *alias):
            return SearchResult(
                name=name,
                birth=date_searcher(tree.findtext('.//span[@class="mv_barth"]', "")),
                alias=alias,
            )

    @staticmethod
    def _scan_search_page(keyword: str, tree: HtmlElement):
        result = None
        for div in tree.iterfind(
            './/div[@class="actress_info"]/div[@class="act_detail"]'
        ):
            name = clean_name(div.findtext('div[@class="act_name"]/a', ""))
            if not name:
                continue
            alias = split_names(xpath('string(div[@class="act_anotherName"])')(div))
            if match_name(keyword, name, *alias):
                if result:
                    return
                result = SearchResult(
                    name=name,
                    birth=date_searcher(
                        div.findtext('.//span[@class="act_barth"]', "")
                    ),
                    alias=alias,
                )
        return result


class Manko(Wiki):
    @staticmethod
    def _search(keyword: str):
        tree = get_tree(f"http://mankowomiseruavzyoyu.blog.fc2.com/?q={keyword}")
        if tree is None:
            return

        result = None
        name_xp = xpath(
            'string(tr/td[@align="center" or @align="middle"]'
            "/*[self::font or self::span]//text())"
        )
        info_xp = xpath("string(tr[td[1][contains(text(), $title)]]/td[2])")

        for tbody in tree.iterfind(
            './/div[@id="center"]//div[@class="ently_body"]'
            '/div[@class="ently_text"]//tbody'
        ):
            name = clean_name(name_xp(tbody))
            if not name:
                continue

            alias = split_names(info_xp(tbody, title="別名"))
            if match_name(keyword, name, *alias):
                if result:
                    return
                result = SearchResult(
                    name=name,
                    birth=date_searcher(info_xp(tbody, title="生年月日")),
                    alias=alias,
                )

        return result


class Etigoya(Wiki):
    @staticmethod
    def _search(keyword: str):
        tree = get_tree(f"http://etigoya955.blog49.fc2.com/?q={keyword}")
        if tree is None:
            return

        result = None
        for text in xpath(
            './/div[@id="main"]/div[@class="content"]' '//li/a/text()[contains(., "＝")]'
        )(tree):
            alias = text.split("＝")
            if match_name(keyword, *alias):
                if result:
                    return
                result = SearchResult(alias=alias)
        return result


_WIKI_LIST = (Wikipedia, MinnanoAV, AVRevolution, Seesaawiki, Msin, Manko, Etigoya)


class Idol(AVInfo):
    name: str = None
    birth: str = None
    final: str = None
    keywidth = 10

    def __init__(self, keyword: str, ex: ThreadPoolExecutor = None):
        self.status = Status.FAILURE
        self.result = {
            "Source": keyword,
            "Name": None,
            "Birth": None,
            "Visited": None,
            "Unvisited": None,
            "Final": None,
        }

        keyword = re_sub(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}|\s+", "", keyword)
        if not is_cjk_name(keyword):
            self.result["Error"] = "Not a valid actress name."
            return

        try:
            if ex is None:
                with ThreadPoolExecutor() as ex:
                    self._bfs_search(keyword, ex)
            else:
                self._bfs_search(keyword, ex)
        except Exception as e:
            self.result["Error"] = e
            self.status = Status.ERROR

    def _bfs_search(self, keyword: str, ex: ThreadPoolExecutor):
        nameDict = defaultdict(list)
        birthDict = defaultdict(list)
        visited = {}
        unvisited = {}

        unvisited_get = unvisited.get
        all_visited = unvisited.keys().isdisjoint

        unvisited[keyword] = 0
        weight_to_func = {i: wiki.search for i, wiki in enumerate(_WIKI_LIST)}

        while unvisited and weight_to_func:
            if all_visited(nameDict):
                pool = unvisited
            else:
                pool = filter(unvisited_get, nameDict)

            keyword = max(pool, key=unvisited_get)
            visited[keyword] = unvisited.pop(keyword)

            ft_to_weight = {ex.submit(f, keyword): i for i, f in weight_to_func.items()}

            for ft in as_completed(ft_to_weight):
                result = ft.result()
                if not result:
                    continue
                weight = ft_to_weight[ft]

                if result.name:
                    nameDict[result.name].append(weight)
                if result.birth:
                    birthDict[result.birth].append(weight)

                result.alias.difference_update(visited)
                for i in result.alias:
                    v = unvisited_get(i)
                    if v:
                        v[0] += 1
                    else:
                        unvisited[i] = [1, len(i)]

                del weight_to_func[weight]

        report = self.result
        report["Visited"] = ", ".join(visited)
        report["Unvisited"] = ", ".join(
            sorted(unvisited, key=unvisited_get, reverse=True)
        )
        name, report["Name"] = self._sort_search_result(nameDict)
        birth, report["Birth"] = self._sort_search_result(birthDict)

        if name and birth:
            self.status = Status.SUCCESS
            self.final = report["Final"] = f"{birth} {name}"
            self.name = name
            self.birth = birth

    @staticmethod
    def _sort_search_result(result: dict):
        if not result:
            return None, None

        for i in result.values():
            i.sort()
        result = sorted(result.items(), key=lambda i: (-len(i[1]), i[1][0]))

        return (
            result[0][0],
            tuple(
                f'{k} ({", ".join(_WIKI_LIST[i].__name__ for i in v)})'
                for k, v in result
            ),
        )


class IdolFolder(Idol):
    def __init__(self, path, ex: ThreadPoolExecutor = None):
        if not isinstance(path, Path):
            path = Path(path)
        super().__init__(path.name, ex)
        self.path = self.result["Source"] = path

        if self.status == Status.SUCCESS and self.final != path.name:
            self.status = Status.UPDATED

    def apply(self):
        if self.status == Status.UPDATED:
            path = self.path
            os.rename(path, path.with_name(self.final))


def from_dir(root, scanner: FileScanner = None) -> Generator[IdolFolder, None, None]:
    """Scan a directory and yield ActressFolder objects."""
    if scanner is None:
        scanner = FileScanner(recursive=False)

    # Use two executors to avoid deadlock
    m = min(32, (os.cpu_count() or 1) + 4)
    o = m // 3
    with ThreadPoolExecutor(o) as outer, ThreadPoolExecutor(m - o) as inner:
        pool = [
            outer.submit(IdolFolder, e.path, inner)
            for e in scanner.scandir(root, "dir")
        ]
        # If there is no subdirectory, add the root.
        if not pool:
            pool.append(outer.submit(IdolFolder, root, inner))

        for ft in as_completed(pool):
            yield ft.result()


def from_args(args):
    """:type args: argparse.Namespace"""
    return from_dir(args.source, get_scanner(args))
