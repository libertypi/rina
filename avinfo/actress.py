import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator
from urllib.parse import quote as urlquote
from urllib.parse import urljoin

from avinfo import common
from avinfo.common import (
    color_printer,
    date_searcher,
    get_response_tree,
    re_compile,
    re_search,
    re_split,
    re_sub,
    sepChanged,
    sepFailed,
    sepSuccess,
    xpath,
)


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
            result.alias = set(filter(None, map(_clean_name, alias)))
        else:
            result.alias = set()

        name = result.name
        if name:
            name = _clean_name(name)
            if name:
                result.alias.add(name)
            result.name = name

        birth = result.birth
        if birth:
            result.birth = f'{birth["y"]}-{birth["m"].zfill(2)}-{birth["d"].zfill(2)}'

        if name or birth or result.alias:
            return result

    @classmethod
    def _query(cls, keyword: str) -> SearchResult:
        pass


class Wikipedia(Wiki):

    baseurl = "https://ja.wikipedia.org/wiki/"

    @classmethod
    def _query(cls, keyword: str):

        tree = get_response_tree(cls.baseurl + keyword, decoder="lxml")[1]
        if tree is None or not xpath('//a[@title="AV女優" and contains(text(),"AV女優")]')(tree):
            return

        name = tree.findtext('.//*[@id="firstHeading"]')
        box = tree.find('.//div[@id="mw-content-text"]//table[@class="infobox"]')
        if not name or box is None:
            return

        birth = None
        alias = xpath('//caption[@*="name"]/text()')(box)
        xp = xpath("td//text()")

        for tr in box.iterfind("tbody/tr[th][td]"):
            k = tr.find("th").text_content()
            if not birth and "生年月日" in k:
                birth = date_searcher("".join(xp(tr)))
            elif "別名" in k:
                alias.extend(j for i in xp(tr) for j in _split_name(i))

        return SearchResult(name=name, birth=birth, alias=alias)


class MinnanoAV(Wiki):

    baseurl = "http://www.minnano-av.com/"

    @classmethod
    def _query(cls, keyword: str):

        response, tree = get_response_tree(
            cls.baseurl + "search_result.php",
            params={"search_scope": "actress", "search_word": keyword},
            decoder="lxml",
        )
        if tree is None:
            return

        if "/search_result.php" in response.url:
            tree = cls._scan_search_page(keyword, tree)
            if tree is None:
                return

        tree = tree.find('.//section[@id="main-area"]')
        try:
            name = _clean_name(tree.findtext("section/h1"))
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

    @classmethod
    def _scan_search_page(cls, keyword: str, tree):
        """Return if there's only one match."""

        links = xpath(
            '//section[@id = "main-area"]//table[contains(@class, "actress")]'
            '//td[not(contains(., "重複"))]/h2/a[@href]'
        )(tree)

        result = None
        for a in links:
            if _match_name(keyword, a.text):
                href = a.get("href").partition("?")[0]
                if not result:
                    result = href
                elif result != href:
                    return

        if result:
            return get_response_tree(urljoin(cls.baseurl, result))[1]


class AVRevolution(Wiki):

    baseurl = "http://neo-adultmovie-revolution.com/db/jyoyuu_betumei_db/"

    @classmethod
    def _query(cls, keyword: str):

        tree = get_response_tree(cls.baseurl, params={"q": keyword}, decoder="lxml")[1]
        try:
            tree = xpath('//div[@class="container"]/div[contains(@class, "row") and @style and div[1]/a]')(tree)
        except TypeError:
            return

        title_seen = result = None
        xp = xpath('div[3]/div/text()[not(contains(., "別名無"))]')

        for row in tree:
            try:
                a = row.find("div[1]/a[@href]")
                title = _clean_name(a.text_content())
                name = re_search(r"/([^/]+)/?$", a.get("href"))[1]
            except AttributeError:
                continue

            if result:
                if title == title_seen and name != result.name:
                    return
                continue

            alias = xp(row)
            alias.append(title)
            if _match_name(keyword, *alias):
                title_seen = title
                result = SearchResult(name=name, alias=alias)

        return result


class Seesaawiki(Wiki):

    baseurl = "https://seesaawiki.jp/av_neme/d/"

    @classmethod
    def _query(cls, keyword: str):

        try:
            urls = [cls.baseurl + urlquote(keyword, encoding="euc-jp")]
        except UnicodeEncodeError:
            return

        while True:
            tree = get_response_tree(urls[-1], decoder="euc-jp")[1]
            if tree is None:
                return

            text = tree.findtext('.//*[@id="content_1"]')
            if not (text and re_search(r"((女優名|名前).*?)+変更", text)):
                break

            a = tree.find('.//div[@id="content_block_1-body"]/span/a[@href]')
            if a is not None and "移動" in a.getparent().text_content():
                url = urljoin(cls.baseurl, a.get("href"))
                if url not in urls:
                    urls.append(url)
                    continue
            return

        name = tree.findtext('.//div[@id="page-header-inner"]/div[@class="title"]//h2')
        if not name:
            return

        box = tree.find('.//*[@id="content_block_2"]')
        if box is None:
            return SearchResult(name=name)
        if box.tag == "table":
            box = ((tr.find("th").text_content(), tr.find("td").text_content()) for tr in box.iterfind(".//tr[th][td]"))
        else:
            box = (i.split("：", 1) for i in box.text.splitlines() if "：" in i)

        birth = None
        urls.clear()
        alias = urls
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = date_searcher(v)
            elif re_search(r"旧名|別名|名前|女優名", k):
                alias.extend(_split_name(v))

        return SearchResult(name=name, birth=birth, alias=alias)


class Msin(Wiki):

    baseurl = "https://db.msin.jp/search/actress"

    @classmethod
    def _query(cls, keyword: str):

        response, tree = get_response_tree(cls.baseurl, params={"str": keyword})
        if tree is None:
            return

        if "/actress?str=" in response.url:
            return cls._scan_search_page(keyword, tree)

        tree = tree.find('.//div[@id="content"]/div[@id="actress_view"]//div[@class="act_ditail"]')
        try:
            name = _clean_name(tree.findtext('.//span[@class="mv_name"]'))
        except (AttributeError, TypeError):
            return

        xp = xpath("div[contains(text(), $title)]/following-sibling::span[//text()][1]")
        alias = xp(tree, title="別名")
        if alias:
            alias = _split_name(alias[0].text_content())

        if _match_name(keyword, name, *alias):
            birth = xp(tree, title="生年月日")
            return SearchResult(
                name=name,
                birth=date_searcher(birth[0].text_content()) if birth else None,
                alias=alias,
            )

    @staticmethod
    def _scan_search_page(keyword: str, tree):

        result = None
        for div in tree.iterfind('.//div[@id="content"]//div[@class="actress_info_find"]/div[@class="act_ditail"]'):
            name = div.findtext('div[@class="act_name"]/a')
            if not name:
                continue

            alias = div.findtext('div[@class="act_anotherName"]')
            alias = _split_name(alias) if alias else ()

            if _match_name(keyword, name, *alias):
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

    baseurl = "http://mankowomiseruavzyoyu.blog.fc2.com/"

    @classmethod
    def _query(cls, keyword: str):

        tree = get_response_tree(cls.baseurl, params={"q": keyword}, decoder="lxml")[1]
        if tree is None:
            return

        result = None
        xp1 = xpath('(tr/td[@align="center" or @align="middle"]/*[self::font or self::span]//text())[1]')
        xp2 = xpath("tr[td[1][contains(text(), $title)]]/td[2]")

        for tbody in tree.iterfind('.//div[@id="center"]//div[@class="ently_body"]/div[@class="ently_text"]//tbody'):
            try:
                name = _clean_name(xp1(tbody)[0])
            except IndexError:
                continue
            if not name:
                continue

            alias = tuple(j for i in xp2(tbody, title="別名") for j in _split_name(i.text_content()))
            if _match_name(keyword, name, *alias):
                if result:
                    return
                birth = xp2(tbody, title="生年月日")
                result = SearchResult(
                    name=name,
                    birth=date_searcher(birth[0].text_content()) if birth else None,
                    alias=alias,
                )

        return result


class Etigoya(Wiki):

    baseurl = "http://etigoya955.blog49.fc2.com/"

    @classmethod
    def _query(cls, keyword: str):

        tree = get_response_tree(cls.baseurl, params={"q": keyword})[1]
        if tree is None:
            return

        result = None
        for text in xpath('//div[@id="main"]/div[@class="content"]//li/a/text()[contains(., "＝")]')(tree):
            alias = text.split("＝")
            if _match_name(keyword, *alias):
                if result:
                    return
                result = SearchResult(alias=alias)
        return result


_WIKI_LIST = (Wikipedia, MinnanoAV, AVRevolution, Seesaawiki, Msin, Manko, Etigoya)


class Actress:

    __slots__ = ("name", "birth", "result", "_status", "_report")

    def __init__(self, keyword: str, executor: ThreadPoolExecutor = None):

        # status: || filenameDiff | ok ||
        self._status = 0
        self.name = self.birth = self.result = None
        self._report = {
            "Target": keyword,
            "Name": None,
            "Birth": None,
            "Visited": None,
            "Unvisited": None,
            "Result": None,
        }

        keyword = re_sub(r"\([0-9\s._-]+\)|\s+", "", keyword)
        if not is_cjk_name(keyword):
            self._report["Error"] = "Not valid actress name."
            return

        try:
            if executor:
                self._bfs_search(keyword, executor)
            else:
                with ThreadPoolExecutor(max_workers=None) as executor:
                    self._bfs_search(keyword, executor)
        except Exception as e:
            self._report["Error"] = str(e)

    def _bfs_search(self, keyword: str, ex: ThreadPoolExecutor):

        nameDict = defaultdict(list)
        birthDict = defaultdict(list)
        visited = {}
        unvisited = {}

        weight_to_func = {i: wiki.search for i, wiki in enumerate(_WIKI_LIST)}
        unvisited[keyword] = 0
        all_visited = unvisited.keys().isdisjoint

        while unvisited and weight_to_func:

            if all_visited(nameDict):
                pool = unvisited
            else:
                pool = filter(unvisited.get, nameDict)

            keyword = max(pool, key=unvisited.get)
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
                    v = unvisited.get(i)
                    if v:
                        v[0] += 1
                    else:
                        unvisited[i] = [1, len(i)]

                del weight_to_func[weight]

        report = self._report
        report["Visited"] = ", ".join(visited)
        report["Unvisited"] = ", ".join(sorted(unvisited, key=unvisited.get, reverse=True))
        name, report["Name"] = self._sort_search_result(nameDict)
        birth, report["Birth"] = self._sort_search_result(birthDict)

        if name and birth:
            self._status |= 0b01
            self.result = report["Result"] = f"{name}({birth})"
            self.name = name
            self.birth = birth

    @staticmethod
    def _sort_search_result(result: dict):
        if not result:
            return None, None

        for i in result.values():
            i.sort()
        result = sorted(
            result.items(),
            key=lambda i: (len(i[1]), -i[1][0]),
            reverse=True,
        )
        return (
            result[0][0],
            tuple(f'{k} ({", ".join(_WIKI_LIST[i].__name__ for i in v)})' for k, v in result),
        )

    def print(self):
        if self._status == 0b01:
            print(sepSuccess, self.report, sep="", end="")
        elif self._status & 0b10:
            color_printer(sepChanged, self.report, color="yellow", sep="", end="")
        else:
            color_printer(sepFailed, self.report, color="red", sep="", end="")

    @property
    def report(self):
        report = self._report
        if isinstance(report, str):
            return report

        log = []
        for k, v in report.items():
            if v:
                if isinstance(v, tuple):
                    v = iter(v)
                    log.append(f'{k + ":":>10} {next(v)}\n')
                    log.extend(f'{"":>10} {i}\n' for i in v)
                else:
                    log.append(f'{k + ":":>10} {v}\n')

        report = self._report = "".join(log)
        return report

    @property
    def ok(self):
        return not not self._status & 0b01


class ActressFolder(Actress):

    __slots__ = Actress.__slots__ + ("path",)

    def __init__(self, path: Path, executor: ThreadPoolExecutor = None):
        super().__init__(path.name, executor)
        self.path = self._report["Target"] = path

        if self._status & 0b01 and self.result != path.name:
            self._status |= 0b10

    def apply(self):
        if self._status == 0b11:
            os.rename(self.path, self.path.with_name(self.result))

    @property
    def has_new_info(self):
        return self._status == 0b11


def _split_name(string: str):
    return re_split(r"\s*[\n、/／●・,＝=]\s*", string)


def _match_name(keyword: str, *names: str):
    return any(_clean_name(s) == keyword for s in names)


@lru_cache(512)
def _clean_name(string: str) -> str:
    for string in re_split(r"[【「『｛（《\[(].*?[】」』｝）》\])]", re_sub(r"\d+歳|[\s 　]+", "", string)):
        string = re_sub(r"[【「『｛（《\[(].*|.*?[】」』｝）》\])]", "", string)
        if is_cjk_name(string):
            return string
    return ""


def is_cjk_name():

    is_word = re_compile(r"\w{2,20}").fullmatch
    mask = 0
    for i, j in (
        (4352, 4607),
        (11904, 42191),
        (43072, 43135),
        (44032, 55215),
        (63744, 64255),
        (65072, 65103),
        (65381, 65500),
        (131072, 196607),
    ):
        mask |= (1 << j + 1) - (1 << i)

    def _is_cjk_name(string: str) -> bool:
        return is_word(string) and any(1 << ord(c) & mask for c in string)

    def _all_cjk(string: str):
        return all(1 << ord(c) & mask for c in string)

    return _is_cjk_name, _all_cjk


is_cjk_name, all_cjk = is_cjk_name()


def scan_path(target: Path) -> Iterator[ActressFolder]:

    w = min(32, os.cpu_count() + 4) / 2
    with ThreadPoolExecutor(max_workers=w) as ex, ThreadPoolExecutor(max_workers=None) as exe:
        for ft in as_completed(ex.submit(ActressFolder, p, exe) for p in common.list_dir(target)):
            yield ft.result()
