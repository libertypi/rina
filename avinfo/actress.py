import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from re import compile as re_compile
from re import search as re_search
from re import split as re_split
from re import sub as re_sub
from urllib.parse import quote as urlquote

from avinfo import common
from avinfo.common import color_printer, get_response_tree, xp_compile

_RE_BIRTH = re_compile(
    r"(?P<y>(19|20)[0-9]{2})\s*年\s*(?P<m>1[0-2]|0?[1-9])\s*月\s*(?P<d>3[01]|[12][0-9]|0?[1-9])\s*日"
).search


@dataclass
class SearchResult:
    name: str = None
    birth: str = None
    alias: set = None

    def __post_init__(self):
        if self.alias:
            self.alias = set(_clean_name_list(self.alias))
        else:
            self.alias = set()

        if self.name:
            self.name = _clean_name(self.name)
            self.alias.add(self.name)

        birth = self.birth
        if birth:
            self.birth = f'{birth["y"]}-{birth["m"].zfill(2)}-{birth["d"].zfill(2)}'


class Wiki:

    __slots__ = "baseurl"

    @classmethod
    def search(cls, keyword: str):
        raise NotImplemented


class Wikipedia(Wiki):

    baseurl = "https://ja.wikipedia.org/wiki"

    @classmethod
    def search(cls, keyword: str):

        tree = get_response_tree(f"{cls.baseurl}/{keyword}", decoder="lxml")[1]
        if tree is None:
            return

        name = tree.findtext('.//*[@id="firstHeading"]')
        box = tree.find('.//*[@id="mw-content-text"]//table[@class="infobox"]')
        if not name or box is None or not xp_compile('//a[@title="AV女優" and contains(text(),"AV女優")]')(tree):
            return

        birth = None
        alias = xp_compile('//caption[@*="name"]/text()')(box)
        xpath = xp_compile("td//text()")

        for tr in box.iterfind("tbody/tr[th][td]"):
            k = tr.find("th").text_content()
            if not birth and "生年月日" in k:
                birth = _RE_BIRTH("".join(xpath(tr)))
            elif "別名" in k:
                alias.extend(j for i in xpath(tr) for j in _split_name(i))

        return SearchResult(name=name, birth=birth, alias=alias)


class MinnanoAV(Wiki):
    baseurl = "http://www.minnano-av.com"

    @classmethod
    def search(cls, keyword: str):

        response, tree = get_response_tree(
            f"{cls.baseurl}/search_result.php",
            params={"search_scope": "actress", "search_word": keyword},
            decoder="lxml",
        )
        if tree is None:
            return

        if "/search_result.php?" in response.url or response.url == cls.baseurl:
            tree = cls._scan_search_page(keyword, tree)

        try:
            tree = tree.find('.//*[@id="main-area"]')
            name = tree.findtext("section/h1")
            if name is None:
                return
        except AttributeError:
            return

        birth = None
        alias = []
        for td in xp_compile('//div[@class="act-profile"]/table//td[span and p]')(tree):
            title = td.findtext("span")
            if "別名" in title:
                alias.append(td.findtext("p"))
            elif not birth and "生年月日" in title:
                birth = _RE_BIRTH(td.findtext("p"))

        return SearchResult(name=name, birth=birth, alias=alias)

    @classmethod
    def _scan_search_page(cls, keyword: str, tree):
        """Return if there's only one match."""

        tree = xp_compile('//*[@id="main-area"]//table[contains(@class,"actress")]/tr/td[h2/a[@href]]')(tree)
        if not tree:
            return
        nameMask = _get_re_nameMask(keyword).fullmatch

        result = None
        for td in tree:
            if "重複" in td.text_content():
                continue
            a = td.find("h2/a[@href]")
            if nameMask(_clean_name(a.text)):
                href = a.get("href").partition("?")[0]
                if not result:
                    result = href
                elif result != href:
                    return

        if result:
            return get_response_tree(f"{cls.baseurl}/{result}")[1]


class AVRevolution(Wiki):
    baseurl = "http://adultmovie-revolution.com/movies/jyoyuu_kensaku.php"

    @classmethod
    def search(cls, keyword: str):
        tree = get_response_tree(cls.baseurl, params={"mode": 1, "search": keyword}, decoder="lxml")[1]
        if tree is None:
            return

        nameMask = _get_re_nameMask(keyword)
        tree = xp_compile('//*[@id="entry-01"]//center/table[@summary="AV女優検索結果"]/tbody//td/a[text() and @href]')(tree)
        url = None
        for a in tree:
            if nameMask.fullmatch(_clean_name(a.text)):
                href = a.get("href")
                if not url:
                    url = href
                elif url != href:
                    return
        if not url:
            return

        tree = get_response_tree(url)[1]
        try:
            tree = tree.find('.//*[@id="entry-47"][@class="entry-asset"]')
            name = xp_compile('h2[contains(text(),"「")]/text()')(tree)
            name = re_search(r"「(.+?)」", name[0]).group(1)
            if not name:
                return
            alias = xp_compile('div/center/table[contains(@summary,"別名")]/tbody//td/text()')(tree)
        except (AttributeError, TypeError, IndexError):
            pass
        else:
            return SearchResult(name=name, alias=alias)


class Seesaawiki(Wiki):
    baseurl = "https://seesaawiki.jp/av_neme/d"

    @classmethod
    def search(cls, keyword: str, url: str = None):

        if not url:
            try:
                encodeName = urlquote(keyword, encoding="euc-jp")
            except UnicodeEncodeError:
                return
            url = f"{cls.baseurl}/{encodeName}"

        tree = get_response_tree(url, decoder="euc-jp")[1]
        if tree is None:
            return

        try:
            if re_search(r"(\W*(女優名|名前)\W*)+変更", tree.findtext('.//*[@id="content_1"]')):
                a = tree.find('.//*[@id="content_block_1-body"]/span/a[@href]')
                if a is not None and "移動" in a.getparent().text_content():
                    return cls.search(a.text, a.get("href"))
                return
        except TypeError:
            pass

        name = tree.findtext('.//*[@id="page-header-inner"]/div[@class="title"]//h2')
        if not name:
            return

        box = tree.find('.//*[@id="content_block_2"]')
        tag = getattr(box, "tag", None)
        if tag == "table":
            box = ((i.find("th").text_content(), i.find("td").text_content()) for i in xp_compile(".//tr[th][td]")(box))
        elif tag:
            box = (i.split("：", 1) for i in box.findtext(".").splitlines() if "：" in i)
        else:
            return SearchResult(name=name)

        birth = None
        alias = []
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = _RE_BIRTH(v)
            elif re_search(r"旧名義|別名|名前|女優名", k):
                alias.extend(_split_name(v))

        return SearchResult(name=name, birth=birth, alias=alias)


class Msin(Wiki):

    baseurl = "https://db.msin.jp/search/actress"

    @classmethod
    def search(cls, keyword: str):

        tree = get_response_tree(cls.baseurl, params={"str": keyword})[1]
        try:
            tree = tree.find('.//*[@id="content"]/*[@id="actress_view"]//*[@class="act_ditail"]')
            name = _clean_name(tree.findtext('.//*[@class="mv_name"]'))
            if not name:
                return
        except (AttributeError, TypeError):
            return

        xpath = xp_compile("*[contains(text(), $title)]/following-sibling::*[//text()][1]")
        try:
            alias = _split_name(xpath(tree, title="別名")[0].text_content())
        except IndexError:
            alias = ()

        nameMask = _get_re_nameMask(keyword).fullmatch
        if nameMask(name) or any(nameMask(_clean_name(i)) for i in alias):
            try:
                birth = re_search(
                    r"(?P<y>(19|20)[0-9]{2})\s*-\s*(?P<m>1[0-2]|0?[1-9])\s*-\s*(?P<d>3[01]|[12][0-9]|0?[1-9])",
                    xpath(tree, title="生年月日")[0].text_content(),
                )
            except IndexError:
                birth = None
            return SearchResult(name=name, birth=birth, alias=alias)


class Manko(Wiki):
    baseurl = "http://mankowomiseruavzyoyu.blog.fc2.com"

    @classmethod
    def search(cls, keyword: str):

        tree = get_response_tree(cls.baseurl, params={"q": keyword}, decoder="lxml")[1]
        if tree is None:
            return

        result = None
        nameMask = _get_re_nameMask(keyword)
        xpath_1 = xp_compile('(tr/td[@align="center" or @align="middle"]/*[self::font or self::span]//text())[1]')
        xpath_2 = xp_compile("tr[td[1][contains(text(), $title)]]/td[2]")

        for tbody in tree.iterfind('.//*[@id="center"]//div[@class="ently_body"]/div[@class="ently_text"]//tbody'):
            try:
                name = xpath_1(tbody)
                name = _clean_name(name[0])
                if not name:
                    continue
            except IndexError:
                continue

            alias = (i.text_content() for i in xpath_2(tbody, title="別名"))
            alias = tuple(j for i in alias for j in _split_name(i))

            if nameMask.fullmatch(name) or any(nameMask.fullmatch(i) for i in alias):
                if result:
                    return
                birth = xpath_2(tbody, title="生年月日")
                if birth:
                    birth = _RE_BIRTH(birth[0].text_content())
                result = SearchResult(name=name, birth=birth, alias=alias)

        return result


class Etigoya(Wiki):
    baseurl = "http://etigoya955.blog49.fc2.com"

    @classmethod
    def search(cls, keyword: str):

        tree = get_response_tree(cls.baseurl, params={"q": keyword})[1]
        if tree is None:
            return
        nameMask = _get_re_nameMask(keyword)

        result = None
        for a in xp_compile('.//*[@id="main"]/div[@class="content"]/ul/li/a[contains(text(), "＝")]')(tree):
            alias = _split_name(a.text)
            if any(nameMask.fullmatch(_clean_name(i)) for i in alias):
                if result:
                    return
                result = SearchResult(alias=alias)
        return result


_WIKI_LIST = (Wikipedia, MinnanoAV, Seesaawiki, Msin, Manko, Etigoya)


class Actress:

    __slots__ = ("name", "birth", "result", "_report", "_status")

    def __init__(self, keyword: str, executor: ThreadPoolExecutor = None):

        # status: || filenameDiff | success | started ||
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
        if not (re_search(r"^\w+$", keyword) and contains_cjk(keyword)):
            self._report["Error"] = "Not valid actress name."
            return

        self._status |= 0b001
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

        while unvisited and weight_to_func:

            keyword = max(unvisited, key=unvisited.get)
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
                for i in result.alias:
                    if i in visited:
                        continue
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
            self._status |= 0b010
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

    @property
    def success(self):
        return self._status & 0b011 == 0b011

    @property
    def scrape_failed(self):
        return self._status & 0b011 == 0b001

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

    def print(self):
        if self._status == 0b011:
            print(common.sepSuccess, self.report, sep="", end="")
        else:
            if self._status == 0b111:
                color = "yellow"
                sep = common.sepChanged
            else:
                color = "red"
                sep = common.sepFailed
            color_printer(sep, self.report, color=color, sep="", end="")


class ActressFolder(Actress):

    __slots__ = Actress.__slots__ + ("path",)

    def __init__(self, path: Path, executor: ThreadPoolExecutor = None):
        super().__init__(path.name, executor)
        self.path = self._report["Target"] = path

        if self._status & 0b010 and self.result != path.name:
            self._status |= 0b100

    def apply(self):
        if self._status == 0b111:
            os.rename(self.path, self.path.with_name(self.result))

    @property
    def has_new_info(self):
        return self._status == 0b111


def _split_name(string: str):
    return re_split(r"\s*[\n、/／・,＝]+\s*", string)


@lru_cache(128)
def _get_re_nameMask(keyword: str) -> re.Pattern:
    return re_compile(r"\b\s*{}\s*\b".format(r"\s*".join(keyword)))


@lru_cache(512)
def _clean_name(string: str) -> str:
    for string in re_split(r"[【「『｛（《\[(].*?[】」』｝）》\])]", re_sub(r"[\s 　]+", "", string)):
        string = re_sub(r"[【「『｛（《\[(].*|.*?[】」』｝）》\])]", "", string)
        if string:
            return string
    return ""


def _clean_name_list(nameList):
    for i in nameList:
        name = _clean_name(i)
        if len(name) > 1 and contains_cjk(name):
            yield name


def contains_cjk():
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

    def _contains_cjk(string: str) -> bool:
        return any(1 << ord(c) & mask for c in string)

    return _contains_cjk


contains_cjk = contains_cjk()


def scan_path(target: Path):

    changed = []
    failed = []
    total = 0
    worker = min(32, os.cpu_count() + 4) / 2

    with ThreadPoolExecutor(max_workers=worker) as ex, ThreadPoolExecutor(max_workers=None) as exe:
        for ft in as_completed(ex.submit(ActressFolder, p, exe) for p in common.list_dir(target)):
            total += 1
            actress = ft.result()
            actress.print()
            if actress.has_new_info:
                changed.append(actress)
            elif actress.scrape_failed:
                failed.append(actress)

    return total, changed, failed
