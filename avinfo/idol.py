import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator
from urllib.parse import quote, urljoin

from avinfo._utils import (
    SEP_CHANGED,
    SEP_FAILED,
    SEP_SUCCESS,
    HtmlElement,
    color_printer,
    date_searcher,
    get_tree,
    set_cookie,
    xpath,
)

__all__ = ("scan_dir",)

set_cookie(domain="db.msin.jp", name="age", value="off")
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


class Wiki:
    @classmethod
    def search(cls, keyword: str):
        result = cls._query(keyword)
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
    def _query(cls, keyword: str) -> SearchResult:
        raise NotImplementedError


class Wikipedia(Wiki):
    @staticmethod
    def _query(keyword: str):
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
    def _query(cls, keyword: str):
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
            title = td.findtext("span")
            if "別名" in title:
                alias.append(td.findtext("p"))
            elif not birth and "生年月日" in title:
                birth = date_searcher(td.findtext("p"))

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
    def _query(keyword: str):
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
                name = re.search(r"/([^/]+)/?$", a.get("href"))[1]
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
    def _query(keyword: str):
        try:
            stack = [
                "https://seesaawiki.jp/av_neme/d/" + quote(keyword, encoding="euc-jp")
            ]
        except UnicodeEncodeError:
            return

        while True:
            tree = get_tree(stack[-1], encoding="auto")
            if tree is None:
                return

            text = tree.findtext('.//h3[@id="content_1"]')
            if not (text and re.search(r"(女優名|名前).*?変更", text)):
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
            elif re.search(r"旧名|別名|名前|女優名", k):
                stack.extend(split_names(v))

        return SearchResult(name=name, birth=birth, alias=stack)


class Msin(Wiki):
    @classmethod
    def _query(cls, keyword: str):
        tree = get_tree(
            f"https://db.msin.jp/search/actress?str={keyword}",
            encoding="auto",
        )
        if tree is None:
            return

        if "/actress?str=" in tree.base_url:
            return cls._scan_search_page(keyword, tree)

        tree = tree.find(
            './/div[@id="content"]/div[@id="actress_view"]' '//div[@class="act_ditail"]'
        )
        try:
            name = clean_name(tree.findtext('.//span[@class="mv_name"]'))
        except (AttributeError, TypeError):
            return

        xp = xpath("string(div[contains(text(), $title)]/following-sibling::span)")
        alias = split_names(xp(tree, title="別名"))

        if match_name(keyword, name, *alias):
            return SearchResult(
                name=name,
                birth=date_searcher(xp(tree, title="生年月日")),
                alias=alias,
            )

    @staticmethod
    def _scan_search_page(keyword: str, tree: HtmlElement):
        result = None
        for div in tree.iterfind(
            './/div[@id="content"]//div[@class="actress_info_find"]'
            '/div[@class="act_ditail"]'
        ):
            name = div.findtext('div[@class="act_name"]/a')
            if not name:
                continue

            alias = div.findtext('div[@class="act_anotherName"]')
            alias = split_names(alias) if alias else ()

            if match_name(keyword, name, *alias):
                if result:
                    return

                birth = div.findtext('div[@class="act_barth"]')
                result = SearchResult(
                    name=name,
                    birth=date_searcher(birth) if birth else None,
                    alias=alias,
                )
        return result


class Manko(Wiki):
    @staticmethod
    def _query(keyword: str):
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
    def _query(keyword: str):
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


class Actress:
    __slots__ = ("name", "birth", "result", "status", "_report")

    def __init__(self, keyword: str, executor: ThreadPoolExecutor = None):
        self.status = "failed"
        self.name = self.birth = self.result = None
        self._report = {
            "Target": keyword,
            "Name": None,
            "Birth": None,
            "Visited": None,
            "Unvisited": None,
            "Result": None,
        }

        keyword = re.sub(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}|\s+", "", keyword)
        if not is_cjk_name(keyword):
            self._report["Error"] = "Not valid actress name."
            return

        try:
            if executor:
                self._bfs_search(keyword, executor)
            else:
                with ThreadPoolExecutor(max_workers=None) as ex:
                    self._bfs_search(keyword, ex)
        except Exception as e:
            self._report["Error"] = str(e)

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

        report = self._report
        report["Visited"] = ", ".join(visited)
        report["Unvisited"] = ", ".join(
            sorted(unvisited, key=unvisited_get, reverse=True)
        )
        name, report["Name"] = self._sort_search_result(nameDict)
        birth, report["Birth"] = self._sort_search_result(birthDict)

        if name and birth:
            self.status = "ok"
            self.result = report["Result"] = f"{birth} {name}"
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

    def print(self):
        """Print report to stdout."""
        if self.status == "ok":
            print(SEP_SUCCESS, self.report, sep="\n")
        elif self.status == "changed":
            color_printer(SEP_CHANGED, self.report, sep="\n", red=False)
        else:
            color_printer(SEP_FAILED, self.report, sep="\n")

    @property
    def report(self):
        report = self._report
        if isinstance(report, dict):
            log = []
            for k, v in report.items():
                if v:
                    if isinstance(v, tuple):
                        v = iter(v)
                        log.append(f"{k:>10}: {next(v)}")
                        log.extend(f'{"":>11} {i}' for i in v)
                    else:
                        log.append(f"{k:>10}: {v}")
            report = self._report = "\n".join(log)
        return report


class ActressFolder(Actress):
    __slots__ = "path"

    def __init__(self, path: Path, executor: ThreadPoolExecutor = None):
        super().__init__(path.name, executor)
        self.path = self._report["Target"] = path

        if self.status == "ok" and self.result != path.name:
            self.status = "changed"

    def apply(self):
        path = self.path
        if self.status == "changed":
            new = path.with_name(self.result)
            os.rename(path, new)
            path = new
        return path


def scan_dir(top_dir: Path, newer: float = None) -> Iterator[ActressFolder]:
    if not isinstance(top_dir, Path):
        top_dir = Path(top_dir)

    outer_max = min(32, (os.cpu_count() or 1) + 4) // 2
    with ThreadPoolExecutor(outer_max) as outer, ThreadPoolExecutor() as inner:
        pool = [
            outer.submit(ActressFolder, Path(entry.path), inner)
            for entry in os.scandir(top_dir)
            if entry.is_dir()
            and entry.name[0] not in "#@"
            and (newer is None or entry.stat().st_mtime >= newer)
        ]
        pool.append(outer.submit(ActressFolder, top_dir, inner))

        for ft in as_completed(pool):
            yield ft.result()
