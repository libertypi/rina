import dataclasses
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from urllib.parse import quote as urlquote

from lxml import etree

from avinfo import common
from avinfo.common import get_response_tree, list_dir, printObjLogs, printProgressBar, printRed, printYellow

_re_birth = re.compile(r"(?P<y>(19|20)[0-9]{2})\s*年\s*(?P<m>1[0-2]|0?[1-9])\s*月\s*(?P<d>3[01]|[12][0-9]|0?[1-9])\s*日")


@dataclasses.dataclass
class SearchResult:
    name: str = None
    birth: str = None
    alias: set = None

    def __post_init__(self):
        try:
            self.alias = set(_clean_name_list(self.alias))
        except TypeError:
            self.alias = set()

        try:
            self.name = _clean_name(self.name)
        except TypeError:
            pass
        else:
            self.alias.add(self.name)

        try:
            birth = self.birth
            self.birth = f'{birth["y"]}-{birth["m"].zfill(2)}-{birth["d"].zfill(2)}'
        except TypeError:
            pass


class Wiki:
    def __init__(self, weight: int):
        self.weight = weight
        self.mask = 1 << weight

    @classmethod
    def search(cls, searchName):
        raise NotImplemented


class Wikipedia(Wiki):

    baseurl = "https://ja.wikipedia.org/wiki"

    @classmethod
    def search(cls, searchName):

        try:
            xpath = cls.xpath
        except AttributeError:
            xpath = cls.xpath = (
                etree.XPath('//a[@title="AV女優" and contains(text(),"AV女優")]'),
                etree.XPath('//caption[@*="name"]/text()'),
                etree.XPath("td//text()"),
            )

        tree = get_response_tree(f"{cls.baseurl}/{searchName}", decoder="lxml")[1]
        if tree is None:
            return

        name = tree.findtext('.//*[@id="firstHeading"]')
        box = tree.find('.//*[@id="mw-content-text"]//table[@class="infobox"]')
        if not name or box is None or not xpath[0](tree):
            return

        birth = None
        alias = xpath[1](box)
        box = ((i.find("th").text_content(), xpath[2](i)) for i in box.findall("tbody/tr[th][td]"))
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = _re_birth.search("".join(v))
            elif "別名" in k:
                alias.extend(j for i in v for j in _split_name(i))

        return SearchResult(name=name, birth=birth, alias=alias)


class MinnanoAV(Wiki):
    baseurl = "http://www.minnano-av.com"

    @classmethod
    def search(cls, searchName):

        try:
            xpath = cls.xpath
        except AttributeError:
            xpath = cls.xpath = (
                etree.XPath('//div[@class="act-profile"]/table//td[span and p]'),
                etree.XPath('//*[@id="main-area"]//table[contains(@class,"actress")]/tr/td[h2/a[@href]]'),
            )

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
        for td in xpath[0](tree):
            title = td.findtext("span").strip()
            if title == "別名":
                alias.append(td.findtext("p"))
            elif title == "生年月日" and not birth:
                birth = _re_birth.search(td.findtext("p"))

        return SearchResult(name=name, birth=birth, alias=alias)

    @classmethod
    def _scan_search_page(cls, searchName, tree):
        """Return if there's only one match."""

        tree = cls.xpath[1](tree)
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
        tree = tree.xpath('//*[@id="entry-01"]//center/table[@summary="AV女優検索結果"]/tbody//td/a[text() and @href]')
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
            name = tree.xpath('h2[contains(text(),"「")]/text()')
            name = re.search(r"「(.+?)」", name[0]).group(1)
            if not name:
                return
            alias = tree.xpath('div/center/table[contains(@summary,"別名")]/tbody//td/text()')
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
            if re.search(r"(\W*(女優名|名前)\W*)+変更", tree.findtext('.//*[@id="content_1"]')):
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
            box = ((i.find("th").text_content(), i.find("td").text_content()) for i in box.xpath(".//tr[th][td]"))
        elif tag:
            box = (i.split("：", 1) for i in box.findtext(".").splitlines() if "：" in i)
        else:
            return SearchResult(name=name)

        birth = None
        alias = []
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = _re_birth.search(v)
            elif re.search(r"旧名義|別名|名前|女優名", k):
                alias.extend(_split_name(v))

        return SearchResult(name=name, birth=birth, alias=alias)


class Msin(Wiki):

    baseurl = "https://db.msin.jp/search/actress"

    @classmethod
    def search(cls, searchName: str):

        try:
            xpath = cls.xpath
            regex = cls.regex
        except AttributeError:
            xpath = cls.xpath = etree.XPath("*[contains(text(), $title)]/following-sibling::*[//text()][1]")
            regex = cls.regex = re.compile(
                r"(?P<y>(19|20)[0-9]{2})\s*-\s*(?P<m>1[0-2]|0?[1-9])\s*-\s*(?P<d>3[01]|[12][0-9]|0?[1-9])"
            )

        tree = get_response_tree(cls.baseurl, params={"str": searchName})[1]
        try:
            tree = tree.find('.//*[@id="content"]/*[@id="actress_view"]//*[@class="act_ditail"]')
            name = _clean_name(tree.findtext('.//*[@class="mv_name"]'))
            if not name:
                return
        except (AttributeError, TypeError):
            return

        try:
            alias = _split_name(xpath(tree, title="別名")[0].text_content())
        except IndexError:
            alias = ()

        nameMask = _get_re_nameMask(searchName).fullmatch
        if nameMask(name) or any(nameMask(_clean_name(i)) for i in alias):
            try:
                birth = regex.search(xpath(tree, title="生年月日")[0].text_content())
            except IndexError:
                birth = None
            return SearchResult(name=name, birth=birth, alias=alias)


class Manko(Wiki):
    baseurl = "http://mankowomiseruavzyoyu.blog.fc2.com"

    @classmethod
    def search(cls, searchName):

        try:
            xpath = cls.xpath
        except AttributeError:
            xpath = cls.xpath = (
                etree.XPath('//*[@id="center"]//div[@class="ently_body"]/div[@class="ently_text"]//tbody'),
                etree.XPath('(tr/td[@align="center" or @align="middle"]/*[self::font or self::span]//text())[1]'),
                etree.XPath('tr[td[1][contains(text(), "別名")]]/td[2]'),
                etree.XPath('tr[td[1][contains(text(), "生年月日")]]/td[2]'),
            )

        tree = get_response_tree(cls.baseurl, params={"q": searchName}, decoder="lxml")[1]
        if tree is None:
            return

        result = None
        nameMask = _get_re_nameMask(searchName)
        for tbody in xpath[0](tree):
            try:
                name = xpath[1](tbody)
                name = _clean_name(name[0])
                if not name:
                    continue
            except Exception:
                continue

            alias = (i.text_content() for i in xpath[2](tbody))
            alias = tuple(j for i in alias for j in _split_name(i))

            if nameMask.fullmatch(name) or any(nameMask.fullmatch(i) for i in alias):
                if result:
                    return
                birth = xpath[3](tbody)
                if birth:
                    birth = _re_birth.search(birth[0].text_content())
                result = SearchResult(name=name, birth=birth, alias=alias)

        return result


class Etigoya(Wiki):
    baseurl = "http://etigoya955.blog49.fc2.com"

    @classmethod
    def search(cls, searchName):

        try:
            xpath = cls.xpath
        except AttributeError:
            xpath = cls.xpath = etree.XPath('.//*[@id="main"]/div[@class="content"]/ul/li/a[contains(text(), "＝")]')

        tree = get_response_tree(cls.baseurl, params={"q": searchName})[1]
        if tree is None:
            return
        nameMask = _get_re_nameMask(searchName)

        result = None
        for a in xpath(tree):
            alias = _split_name(a.text)
            if any(nameMask.fullmatch(_clean_name(i)) for i in alias):
                if result:
                    return
                else:
                    result = SearchResult(alias=alias)
        return result


class Actress:

    # wikiList = tuple(wiki(i) for i, wiki in enumerate((Wikipedia, MinnanoAV, AVRevolution, Seesaawiki, Manko, Etigoya)))
    wikiList = tuple(wiki(i) for i, wiki in enumerate((Wikipedia, MinnanoAV, Seesaawiki, Msin, Manko, Etigoya)))
    wikiDone = 2 ** len(wikiList) - 1

    maxWeight = lambda self, x: max(x.items(), key=lambda y: (len(y[1]), -y[1][0]))[0]
    getWikiName = lambda self, x: self.wikiList[x].__class__.__name__
    is_skipped = lambda self: not self.status & 0b001
    start_and_success = lambda self: self.status & 0b011 == 0b011
    start_but_failed = lambda self: self.status & 0b011 == 0b001
    has_new_info = lambda self: self.status == 0b111

    def __init__(self, basename: str):
        self.basename = self.fullpath = basename
        self.name = self.birth = self.log = self.exception = None
        self.nameDict = self.birthDict = None
        self.visitedNames = self.unvisitedNames = None
        # status: filenameDiff success started
        self.status = 0

    def run(self, ex: ThreadPoolExecutor = None):
        name = re.sub(r"\([0-9]{4}(-[0-9]{1,2}){2}\)|\s+", "", self.basename)
        if contains_cjk(name):
            try:
                self._bfs_search(name, ex)
            except Exception as e:
                self.exception = e
        self._gen_report()

    def _bfs_search(self, name: str, ex: ThreadPoolExecutor):

        self.status |= 0b001
        nameDict = self.nameDict = defaultdict(list)
        birthDict = self.birthDict = defaultdict(list)
        visitedNames = self.visitedNames = {}
        unvisitedNames = self.unvisitedNames = {}
        wikiList = self.wikiList
        wikiDone = self.wikiDone
        wikiStats = 0

        unvisitedNames[name] = 0

        if ex is None:
            ex = ThreadPoolExecutor(max_workers=None)

        while unvisitedNames and wikiStats < wikiDone:

            searchName = max(unvisitedNames, key=unvisitedNames.get)
            visitedNames[searchName] = unvisitedNames.pop(searchName)
            ft_to_wiki = {ex.submit(w.search, searchName): w for w in wikiList if not wikiStats & w.mask}

            for ft in as_completed(ft_to_wiki):

                result = ft.result()
                if not result:
                    continue
                wiki = ft_to_wiki[ft]

                if result.name:
                    nameDict[result.name].append(wiki.weight)

                if result.birth:
                    birthDict[result.birth].append(wiki.weight)

                for i in result.alias:
                    if i in visitedNames:
                        continue
                    v = unvisitedNames.get(i)
                    if v:
                        v[0] += 1
                    else:
                        unvisitedNames[i] = [1, len(i)]

                wikiStats |= wiki.mask

        self.unvisitedNames = sorted(unvisitedNames, key=unvisitedNames.get, reverse=True)

        if nameDict and birthDict:
            for i in (*nameDict.values(), *birthDict.values()):
                i.sort()
            self.name = self.maxWeight(nameDict)
            self.birth = self.maxWeight(birthDict)
            self.status |= 0b010

    def _gen_report(self):
        logs = [("Target", self.fullpath)]

        if self.start_and_success():
            logs.extend(
                (
                    ("Name", f'{self.name} ({", ".join(self.getWikiName(i) for i in self.nameDict[self.name])})'),
                    ("Birth", f'{self.birth} ({", ".join(self.getWikiName(i) for i in self.birthDict[self.birth])})'),
                )
            )

        if self.is_skipped():
            logs.append(("Skipped", "Filename contains no valid actress name."))
        else:
            logs.extend(
                ("Candidate", f'{i} ({", ".join(self.getWikiName(j) for j in self.nameDict[i])})')
                for i in self.nameDict
                if i != self.name
            )
            logs.extend(
                ("Candidate", f'{i} ({", ".join(self.getWikiName(j) for j in self.birthDict[i])})')
                for i in self.birthDict
                if i != self.birth
            )
            if self.visitedNames:
                logs.append(("Visited", ", ".join(self.visitedNames)))
            if self.unvisitedNames:
                logs.append(("Unvisited", ", ".join(self.unvisitedNames)))

        if self.has_new_info():
            logs.append(("Final", self.newfilename))
            printer = printYellow
            sepLine = common.sepChanged
        elif self.start_and_success():
            printer = print
            sepLine = common.sepSuccess
        else:
            printer = printRed
            sepLine = common.sepFailed
            if self.exception:
                logs.append(("Error", self.exception))

        self.log = "".join(f"{k:>10}: {v}\n" for k, v in logs)
        printer(f"{sepLine}{self.log}", end="")


class ActressFolder(Actress):
    def __init__(self, basename: str, fullpath: str, *args, **kwargs):
        super().__init__(basename, *args, **kwargs)
        self.fullpath = fullpath

    def _bfs_search(self, name: str, *args, **kwargs):
        super()._bfs_search(name, *args, **kwargs)
        if self.name and self.birth:
            self.newfilename = f"{self.name}({self.birth})"
            if self.basename != self.newfilename:
                self.status |= 0b100

    def rename(self):
        try:
            newPath = os.path.join(os.path.dirname(self.fullpath), self.newfilename)
            os.rename(self.fullpath, newPath)
        except OSError as e:
            self.exception = f'Renaming "{self.fullpath}" to "{self.newfilename}" failed: {e}'
            return False
        return True


_cjk = 0
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
    _cjk |= (1 << j + 1) - (1 << i)


def contains_cjk(string: str) -> bool:
    return any(1 << ord(c) & _cjk for c in string)


def _split_name(string: str):
    return re.split(r"\s*[\n、/／・,＝]+\s*", string)


@lru_cache(128)
def _get_re_nameMask(searchName: str) -> re.Pattern:
    return re.compile(r"\b\s*{}\s*\b".format(r"\s*".join(searchName)))


@lru_cache(1024)
def _clean_name(string: str) -> str:
    for string in re.split(r"[【（\[(].*?[】）\])]", re.sub(r"[\s 　]+", "", string)):
        string = re.sub(r"[【（\[(].*|.*?[】）\])]", "", string)
        if string:
            return string
    return ""


def _clean_name_list(nameList):
    for i in nameList:
        name = _clean_name(i)
        if len(name) > 1 and contains_cjk(name):
            yield name


def main(target: tuple, quiet=False):

    searchTarget, targetType = target

    if targetType == "keyword":
        Actress(searchTarget).run()
        return
    elif targetType != "dir":
        raise RuntimeError(f"'{searchTarget}' should be either a directory or a keyword.")

    file_pool = []
    inner_ex = ThreadPoolExecutor(max_workers=None)
    with ThreadPoolExecutor(max_workers=None) as ex:
        for basename, fullpath in list_dir(searchTarget):
            aFolder = ActressFolder(basename, fullpath)
            ex.submit(aFolder.run, inner_ex)
            file_pool.append(aFolder)
    inner_ex.shutdown()

    changedList = []
    failedList = []
    totalSuccess = 0
    for aFolder in file_pool:
        if aFolder.start_but_failed():
            failedList.append(aFolder)
        elif aFolder.start_and_success():
            totalSuccess += 1
            if aFolder.has_new_info():
                changedList.append(aFolder)

    totalChanged = len(changedList)
    summary = f"Total: {len(file_pool)}, Success: {totalSuccess}, Failed: {len(failedList)}, Changed: {totalChanged}, Skipped: {len(file_pool) - totalSuccess - len(failedList)}."
    print(common.sepBold, "Actress scan finished.", sep="\n")

    if not totalChanged:
        print(summary, "No change can be made.", sep="\n")
        if failedList:
            print(common.sepBold)
            printRed("Failures:")
            printObjLogs(failedList, printer=printRed)
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
            if changedList:
                printObjLogs(changedList, printer=printYellow)
            else:
                print("Nothing here.")
        elif choice == "3":
            if failedList:
                printObjLogs(failedList, printer=printRed)
            else:
                print("Nothing here.")
        else:
            print("Invalid option.")
        print(common.sepBold)

    printProgressBar(0, totalChanged)
    failedList = []
    sepLine = f"{common.sepSlim}\n"
    with open(common.logFile, "a", encoding="utf-8") as f:
        for i, aFolder in enumerate(changedList, 1):
            if aFolder.rename():
                f.write(f"[{common.epoch_to_str(None)}] Folder Rename\n")
                f.write(aFolder.log)
                f.write(sepLine)
            else:
                failedList.extend(
                    f"{i:>6}: {j}" for i, j in (("Target", aFolder.fullpath), ("Type", aFolder.exception))
                )
            printProgressBar(i, totalChanged)

    if failedList:
        printRed(f"{'Errors':>6}:")
        printRed("\n".join(failedList))
