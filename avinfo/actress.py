import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from re import compile as re_compile
from re import search as re_search
from re import sub as re_sub
from urllib.parse import quote as urlquote

from avinfo import common
from avinfo.common import contains_cjk, get_response_tree, printRed, printYellow, xp_compile

_birth_searcher = re_compile(
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
    def search(cls, searchName):
        raise NotImplemented


class Wikipedia(Wiki):

    baseurl = "https://ja.wikipedia.org/wiki"

    @classmethod
    def search(cls, searchName):

        tree = get_response_tree(f"{cls.baseurl}/{searchName}", decoder="lxml")[1]
        if tree is None:
            return

        name = tree.findtext('.//*[@id="firstHeading"]')
        box = tree.find('.//*[@id="mw-content-text"]//table[@class="infobox"]')
        if not name or box is None or not xp_compile('//a[@title="AV女優" and contains(text(),"AV女優")]')(tree):
            return

        birth = None
        alias = xp_compile('//caption[@*="name"]/text()')(box)
        xpath = xp_compile("td//text()")
        box = ((i.find("th").text_content(), xpath(i)) for i in box.iterfind("tbody/tr[th][td]"))
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = _birth_searcher("".join(v))
            elif "別名" in k:
                alias.extend(j for i in v for j in _split_name(i))

        return SearchResult(name=name, birth=birth, alias=alias)


class MinnanoAV(Wiki):
    baseurl = "http://www.minnano-av.com"

    @classmethod
    def search(cls, searchName):

        response, tree = get_response_tree(
            f"{cls.baseurl}/search_result.php",
            params={"search_scope": "actress", "search_word": searchName},
            decoder="lxml",
        )
        if tree is None:
            return

        if "/search_result.php?" in response.url or response.url == cls.baseurl:
            tree = cls._scan_search_page(searchName, tree)

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
            title = td.findtext("span").strip()
            if title == "別名":
                alias.append(td.findtext("p"))
            elif title == "生年月日" and not birth:
                birth = _birth_searcher(td.findtext("p"))

        return SearchResult(name=name, birth=birth, alias=alias)

    @classmethod
    def _scan_search_page(cls, searchName, tree):
        """Return if there's only one match."""

        tree = xp_compile('//*[@id="main-area"]//table[contains(@class,"actress")]/tr/td[h2/a[@href]]')(tree)
        if not tree:
            return
        nameMask = _get_re_nameMask(searchName)

        result = None
        for td in tree:
            if "重複】" in td.text_content():
                continue
            a = td.find("h2/a[@href]")
            if nameMask.fullmatch(_clean_name(a.text)):
                href = a.get("href").split("?", 1)[0]
                if not result:
                    result = href
                elif result != href:
                    return

        if result:
            return get_response_tree(f"{cls.baseurl}/{result}")[1]


class AVRevolution(Wiki):
    baseurl = "http://adultmovie-revolution.com/movies/jyoyuu_kensaku.php"

    @classmethod
    def search(cls, searchName):
        tree = get_response_tree(cls.baseurl, params={"mode": 1, "search": searchName}, decoder="lxml")[1]
        if tree is None:
            return

        nameMask = _get_re_nameMask(searchName)
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
        except Exception:
            pass
        else:
            return SearchResult(name=name, alias=alias)


class Seesaawiki(Wiki):
    baseurl = "https://seesaawiki.jp/av_neme/d"

    @classmethod
    def search(cls, searchName, url=None):

        if not url:
            try:
                encodeName = urlquote(searchName, encoding="euc-jp")
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
                birth = _birth_searcher(v)
            elif re_search(r"旧名義|別名|名前|女優名", k):
                alias.extend(_split_name(v))

        return SearchResult(name=name, birth=birth, alias=alias)


class Msin(Wiki):

    baseurl = "https://db.msin.jp/search/actress"

    @classmethod
    def search(cls, searchName: str):

        tree = get_response_tree(cls.baseurl, params={"str": searchName})[1]
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

        nameMask = _get_re_nameMask(searchName).fullmatch
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
    def search(cls, searchName):

        tree = get_response_tree(cls.baseurl, params={"q": searchName}, decoder="lxml")[1]
        if tree is None:
            return

        result = None
        nameMask = _get_re_nameMask(searchName)
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
                    birth = _birth_searcher(birth[0].text_content())
                result = SearchResult(name=name, birth=birth, alias=alias)

        return result


class Etigoya(Wiki):
    baseurl = "http://etigoya955.blog49.fc2.com"

    @classmethod
    def search(cls, searchName):

        tree = get_response_tree(cls.baseurl, params={"q": searchName})[1]
        if tree is None:
            return
        nameMask = _get_re_nameMask(searchName)

        result = None
        for a in xp_compile('.//*[@id="main"]/div[@class="content"]/ul/li/a[contains(text(), "＝")]')(tree):
            alias = _split_name(a.text)
            if any(nameMask.fullmatch(_clean_name(i)) for i in alias):
                if result:
                    return
                result = SearchResult(alias=alias)
        return result


wiki_list = (Wikipedia, MinnanoAV, Seesaawiki, Msin, Manko, Etigoya)


class Actress:

    __slots__ = ("log", "string", "path", "status", "result", "exception")

    _name_cleaner = re_compile(r"\([0-9]{4}(-[0-9]{1,2}){2}\)|\s+").sub

    def __init__(self, string: str):
        self.log = {
            "Target": string,
            "Name": None,
            "Birth": None,
            "Visited": None,
            "Unvisited": None,
            "Result": None,
            "Error": None,
        }
        self.string = self._name_cleaner("", string)
        self.status = 0  # status: || filenameDiff | success | started ||

    def run(self, ex: ThreadPoolExecutor = None):
        if contains_cjk(self.string):
            try:
                self._bfs_search(ex)
            except Exception as e:
                self.log["Error"] = e
        else:
            self.log["Error"] = "Filename contains no valid actress name."

        self._gen_report()

        status = self.status
        if status == 0b111:
            return self, True
        elif status == 0b001:
            return self, False
        return None, None

    def _bfs_search(self, ex: ThreadPoolExecutor):

        self.status |= 0b001
        nameDict = defaultdict(list)
        birthDict = defaultdict(list)
        visited = {}
        unvisited = {}

        weight_to_wiki = {weight: wiki for weight, wiki in enumerate(wiki_list)}
        unvisited[self.string] = 0

        if ex is None:
            ex = ThreadPoolExecutor(max_workers=None)

        while unvisited and weight_to_wiki:

            searchName = max(unvisited, key=unvisited.get)
            visited[searchName] = unvisited.pop(searchName)

            ft_to_weight = {ex.submit(wiki.search, searchName): weight for weight, wiki in weight_to_wiki.items()}

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
                del weight_to_wiki[weight]

        log = self.log
        log["Visited"] = ", ".join(visited)
        log["Unvisited"] = ", ".join(sorted(unvisited, key=unvisited.get, reverse=True))
        name, log["Name"] = self._sort_search_result(nameDict)
        birth, log["Birth"] = self._sort_search_result(birthDict)

        if name and birth:
            self.result = log["Result"] = f"{name}({birth})"
            self.status |= 0b010

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
            tuple(f'{k} ({", ".join(wiki_list[i].__name__ for i in v)})' for k, v in result),
        )

    def _gen_report(self):

        logs = []
        for k, v in self.log.items():
            if not v:
                continue
            if isinstance(v, tuple):
                v = iter(v)
                logs.append(f'{k + ":":>10} {next(v)}\n')
                logs.extend(f'{"":>10} {i}\n' for i in v)
            else:
                logs.append(f'{k + ":":>10} {v}\n')
        self.log = "".join(logs)

        status = self.status
        if status == 0b111:
            printer = printYellow
            sepLine = common.sepChanged
        elif status & 0b010:
            printer = print
            sepLine = common.sepSuccess
        else:
            printer = printRed
            sepLine = common.sepFailed

        printer(sepLine + self.log, end="")


class ActressFolder(Actress):
    def __init__(self, path: Path):
        super().__init__(path.name)
        self.path = self.log["Target"] = path

    def _bfs_search(self, *args, **kwargs):
        super()._bfs_search(*args, **kwargs)
        if self.status & 0b010 and self.result != self.path.name:
            self.status |= 0b100

    def apply(self):
        try:
            os.rename(self.path, self.path.with_name(self.result))
        except OSError as e:
            self.exception = e
            return False
        return True


def _split_name(string: str):
    return re.split(r"\s*[\n、/／・,＝]+\s*", string)


@lru_cache(128)
def _get_re_nameMask(searchName: str) -> re.Pattern:
    return re_compile(r"\b\s*{}\s*\b".format(r"\s*".join(searchName)))


@lru_cache(512)
def _clean_name(string: str) -> str:
    for string in re.split(r"[【（\[(].*?[】）\])]", re_sub(r"[\s 　]+", "", string)):
        string = re_sub(r"[【（\[(].*|.*?[】）\])]", "", string)
        if string:
            return string
    return ""


def _clean_name_list(nameList):
    for i in nameList:
        name = _clean_name(i)
        if len(name) > 1 and contains_cjk(name):
            yield name


def main(target, quiet=False):

    if isinstance(target, str):
        Actress(target).run()
        return

    changed = []
    failed = []
    total = 0
    with ThreadPoolExecutor(max_workers=None) as ex, ThreadPoolExecutor(max_workers=None) as exe:
        for ft in as_completed(ex.submit(ActressFolder(p).run, exe) for p in common.list_dir(target)):
            actress, status = ft.result()
            total += 1
            if actress:
                if status:
                    changed.append(actress)
                else:
                    failed.append(actress)

    total_changed = len(changed)
    summary = f"Total: {total}. Changed: {total_changed}. Failed: {len(failed)}."
    print(common.sepBold)
    print("Actress scan finished.")

    if not total_changed:
        print(summary, "No change can be made.", sep="\n")
        return

    msg = f"""{summary}
Please choose an option:
1) Apply changes.
2) Reload changes.
3) Reload failures (not including skipped items).
4) Quit without applying.
"""

    while not quiet:
        choice = input(msg)

        if choice == "1":
            break
        elif choice == "4":
            return

        print(common.sepBold)
        if choice == "2":
            if changed:
                common.printObjLogs(changed, printer=printYellow)
            else:
                print("Nothing here.")
        elif choice == "3":
            if failed:
                common.printObjLogs(failed, printer=printRed)
            else:
                print("Nothing here.")
        else:
            print("Invalid option.")
        print(common.sepBold)

    failed.clear()
    sepLine = common.sepSlim + "\n"
    printProgressBar = common.printProgressBar
    printProgressBar(0, total_changed)

    with open(common.logFile, "a", encoding="utf-8") as f:
        for i, actress in enumerate(changed, 1):
            if actress.apply():
                f.write(f"[{common.epoch_to_str(None)}] Folder Rename\n")
                f.write(actress.log)
                f.write(sepLine)
            else:
                failed.extend(f"{i:>6}: {j}" for i, j in (("Target", actress.path), ("Type", actress.exception)))
            printProgressBar(i, total_changed)

    if failed:
        printRed(f"{'Errors':>6}:")
        printRed("\n".join(failed))
