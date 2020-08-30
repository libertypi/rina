import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from requests.utils import quote as urlquote

from . import common
from .common import get_response_tree, list_dir, printObjLogs, printProgressBar, printRed, printYellow


class Wiki:
    """Wiki.search method should return a tuple of:
    (name, birth, (alias...))
    """

    re_space = re.compile(r"[\s 　]+")
    re_clean_name1 = re.compile(r"[【（\[(].*?[】）\])]")
    re_clean_name2 = re.compile(r"[【（\[(].*|.*?[】）\])]")
    re_birth = re.compile(
        r"(?P<year>(19|20)[0-9]{2})\s*年\s*(?P<month>1[0-2]|0?[1-9])\s*月\s*(?P<day>3[01]|[12][0-9]|0?[1-9])\s*日"
    )

    def __init__(self, precedence: int):
        self.precedence = precedence
        self.mask = 2 ** precedence

    def search(self, searchName):
        reply = self._search(searchName)
        if not reply:
            return None
        name, birth, alias = reply

        name = self._clean_name(name)
        if birth:
            birth = f'{birth["year"]}-{birth["month"].zfill(2)}-{birth["day"].zfill(2)}'

        alias = set(self._clean_name_list(alias))
        if name:
            alias.add(name)

        return name, birth, alias

    def _clean_name(self, string: str) -> str:
        for string in self.re_clean_name1.split(self.re_space.sub("", string)):
            string = self.re_clean_name2.sub("", string)
            if string:
                return string
        return ""

    def _clean_name_list(self, nameList):
        for i in nameList:
            name = self._clean_name(i)
            if len(name) > 1 and contains_cjk(name):
                yield name

    def _split_name(self, string: str, reg=re.compile(r"[\n、/／・,]+")):
        return reg.split(string)

    def _get_re_nameMask(self, searchName):
        return re.compile(r"\b{}\b".format(r"\s*".join(searchName)))


class Wikipedia(Wiki):
    def _search(self, searchName):
        response, tree = get_response_tree(f"https://ja.wikipedia.org/wiki/{searchName}")
        if tree is None:
            return

        name = tree.findtext('.//*[@id="firstHeading"]')
        box = tree.find('.//*[@id="mw-content-text"]//table[@class="infobox"]')
        if not name or box is None or not tree.xpath('//a[@title="AV女優" and contains(text(),"AV女優")]'):
            return

        birth = None
        alias = box.xpath('//caption[@*="name"]/text()')
        box = ((i.find("th").text_content(), i.xpath("td//text()")) for i in box.findall("tbody/tr[th][td]"))
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = self.re_birth.search("".join(v))
            elif "別名" in k:
                alias.extend(j for i in v for j in self._split_name(i))

        return name, birth, alias


class MinnanoAV(Wiki):

    baseurl = "http://www.minnano-av.com"

    def _search(self, searchName):
        response, tree = get_response_tree(
            f"{self.baseurl}/search_result.php", params={"search_scope": "actress", "search_word": searchName}
        )
        if tree is None:
            return

        if "/search_result.php?" in response.url or response.url == self.baseurl:
            tree = self._scan_search_page(searchName, tree)

        try:
            tree = tree.find('.//*[@id="main-area"]')
            name = tree.findtext("section/h1")
            assert name is not None
        except Exception:
            return

        birth = None
        alias = []
        for td in tree.xpath('//div[@class="act-profile"]/table//td[span and p]'):
            title = td.findtext("span").strip()
            if title == "別名":
                alias.append(td.findtext("p"))
            elif title == "生年月日" and not birth:
                birth = self.re_birth.search(td.findtext("p"))

        return name, birth, alias

    def _scan_search_page(self, searchName, tree):

        tree = tree.xpath('//*[@id="main-area"]//table[contains(@class,"actress")][tr[td]]')
        if not tree:
            return
        tree = tree[0]

        ac = tree.xpath('tr/th[text()="AV登録数"][1]')
        if ac:
            ac = f'td[{len(ac[0].xpath("preceding-sibling::th")) + 1}]'
            getCount = lambda tr, td: tr.findtext(ac)
        else:
            getCount = lambda tr, td: td.getnext().text

        re_nameMask = self._get_re_nameMask(searchName)

        records = []
        found = False
        for tr in tree.xpath("tr[td]"):
            td = tr.find("td/h2/a[@href]/../..")
            if td is not None and re_nameMask.fullmatch(self._clean_name(td.find("h2/a").text)):
                if "重複】" in td.text_content():
                    if found:
                        continue
                elif not found:
                    records.clear()
                    found = True

                try:
                    count = int(getCount(tr, td))
                except Exception:
                    for count in td.xpath("following-sibling::td/text()"):
                        if count.strip().isdigit():
                            count = int(count)
                            break
                    else:
                        count = 0

                records.append((count, td.find("h2/a[@href]").get("href")))

        records.sort(key=lambda x: x[0], reverse=True)
        result = None
        for count, href in records:
            response, tree = get_response_tree(f"{self.baseurl}/{href}")
            if tree is None:
                continue
            name = tree.findtext('.//*[@id="main-area"]/section/h1')
            if name is not None and re_nameMask.fullmatch(self._clean_name(name)):
                return tree
            if result is None:
                result = tree

        return result


class Seesaawiki(Wiki):

    baseurl = "https://seesaawiki.jp/av_neme"
    re_digit = re.compile(r"[0-9]")
    re_nameChange = re.compile(r"(\W*(女優名|名前)\W*)+変更")
    re_actressInfo = re.compile(r"(\b身長|\b出演作品|サイズ)\b")

    def _search(self, searchName, url=None):
        encodeName = urlquote(searchName, encoding="euc-jp")
        if not url:
            url = f"{self.baseurl}/d/{encodeName}"

        response, tree = get_response_tree(url)

        if response.status_code == 404:
            args = self._scan_search_page(searchName, encodeName)
            return self._search(*args) if args else None
        elif tree is None:
            return

        if self.re_nameChange.search(tree.findtext('.//*[@id="content_1"]')):
            a = tree.find('.//*[@id="content_block_1-body"]/span/a[@href]')
            if a is not None and "移動" in a.getparent().text_content():
                return self._search(a.text, a.get("href"))
            return

        name = tree.findtext('.//*[@id="page-header-inner"]/div[@class="title"]//h2')
        if not name:
            return

        box = tree.find('.//*[@id="content_block_2"]')
        tag = getattr(box, "tag", None)
        if tag == "table":
            box = ((i.find("th").text_content(), i.find("td").text_content()) for i in box.xpath(".//tr[th][td]"))
        elif tag:
            box = (i.split("：", 1) for i in box.findtext(".").splitlines() if "：" in i)

        birth = None
        alias = []
        for k, v in box:
            if not birth and "生年月日" in k:
                birth = self.re_birth.search(v)
            elif re.search(r"旧名義|別名|名前|女優名", k):
                alias.extend(self._split_name(v))

        return name, birth, alias

    def _scan_search_page(self, searchName, encodeName, pageMax=10):
        re_actressName = re.compile(f"((?<!仮)名|前)\\b.*?\\b{searchName}\\b")
        re_actressInfo = self.re_actressInfo
        urls = (f"search?keywords={encodeName}",)
        p = 1
        while p <= pageMax and urls:
            response, tree = get_response_tree(f"{self.baseurl}/{urls[0]}")
            if tree is None:
                return
            for box in tree.xpath(
                '//*[@id="page-body-inner"]/div[@class="result-box"]/div[@class="body" and *[@class="keyword"] and p[@class="text"]]'
            ):
                a = box.find('.//*[@class="keyword"]/a')
                if self.re_digit.search(a.text) or not contains_cjk(a.text):
                    continue
                found = 0b100 if a.text == searchName else 0
                for line in box.find('p[@class="text"]').text_content().splitlines():
                    if not found & 0b100 and re_actressName.search(line):
                        found |= 0b100
                    elif not found & 0b010 and re_actressInfo.search(line):
                        found |= 0b010
                    elif not found & 0b001 and "生年月日" in line:
                        found |= 0b001
                    if found == 0b111:
                        return a.text, a.get("href")
            urls = tree.xpath(
                '//*[@id="page-body-inner"]//div[@class="paging-top"]/a[@href][last()][contains(text(), "次の")]/@href'
            )
            p += 1


class Manko(Wiki):
    baseurl = "http://mankowomiseruavzyoyu.blog.fc2.com"

    def _search(self, searchName):
        response, tree = get_response_tree(self.baseurl, decoder="lxml", params={"q": searchName})
        if tree is None:
            return
        re_nameMask = self._get_re_nameMask(searchName)

        for tbody in tree.xpath('//*[@id="center"]//div[@class="ently_body"]/div[@class="ently_text"]//tbody'):
            name = tbody.xpath('(tr/td[@align="center" or @align="middle"]/*[self::font or self::span]//text())[1]')
            if name:
                name = name[0]
            if not name:
                continue
            alias = tuple(i.text_content() for i in tbody.xpath('tr[td[1][contains(text(), "別名")]]/td[2]'))
            if re_nameMask.search(name) or any(re_nameMask.search(i) for i in alias):
                birth = tbody.xpath('tr[td[1][contains(text(), "生年月日")]]/td[2]')
                if birth:
                    birth = self.re_birth.search(birth[0].text_content())
                alias = (j for i in alias for j in self._split_name(i))
                return name, birth, alias


class Actress:

    wikiList = tuple(wiki(i) for i, wiki in enumerate((Wikipedia, MinnanoAV, Seesaawiki, Manko)))
    wikiDone = int("1" * len(wikiList), base=2)

    re_nameCleaner = re.compile(r"\([0-9]{4}(-[0-9]{1,2}){2}\)|\s+")
    bestOpt = lambda self, x: max(x.items(), key=lambda y: (len(y[1]), -y[1][0]))[0]
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

    def run(self):
        name = self.re_nameCleaner.sub("", self.basename)
        if contains_cjk(name):
            try:
                self._bfs_search(name)
            except Exception as e:
                self.exception = e
        self._gen_report()

    def _bfs_search(self, name: str):

        self.status |= 0b001
        nameDict = self.nameDict = defaultdict(list)
        birthDict = self.birthDict = defaultdict(list)
        visitedNames = self.visitedNames = dict()
        unvisitedNames = self.unvisitedNames = dict()
        wikiList = self.wikiList
        wikiDone = self.wikiDone
        wikiStats = 0

        unvisitedNames[name] = 0

        while unvisitedNames and wikiStats < wikiDone:

            searchName = max(unvisitedNames, key=unvisitedNames.get)
            visitedNames[searchName] = unvisitedNames.pop(searchName)

            for wiki in (w for w in wikiList if not wikiStats & w.mask):
                result = wiki.search(searchName)
                if result:
                    name, birth, alias = result
                    if name:
                        nameDict[name].append(wiki.precedence)
                    if birth:
                        birthDict[birth].append(wiki.precedence)
                    for i in alias.difference(visitedNames):
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
            self.name = self.bestOpt(nameDict)
            self.birth = self.bestOpt(birthDict)
            self.status |= 0b010

    def _gen_report(self):
        logs = [("Target", self.fullpath)]

        if self.start_and_success():
            logs.extend(
                (
                    ("Name", f'{self.name} ({", ".join(self.getWikiName(i) for i in self.nameDict[self.name])})'),
                    ("Birth", f'{self.birth} ({", ".join(self.getWikiName(i) for i in self.birthDict[self.birth])})',),
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
    def __init__(self, basename: str, fullpath: str):
        super().__init__(basename)
        self.fullpath = fullpath

    def _bfs_search(self, name: str):
        super()._bfs_search(name)
        if self.name and self.birth:
            self.newfilename = f"{self.name}({self.birth})"
            if self.basename != self.newfilename:
                self.status |= 0b100

    def rename(self):
        if not self.fullpath or not self.newfilename:
            raise RuntimeError(f"Dest file missing.")

        try:
            newPath = os.path.join(os.path.dirname(self.fullpath), self.newfilename)
            os.rename(self.fullpath, newPath)
        except Exception as e:
            self.exception = f'Renaming "{self.fullpath}" to "{newPath}" failed: {e}'
            return False
        return True


def contains_cjk(string: str) -> bool:
    return any(
        i <= c <= j
        for c in (ord(s) for s in string)
        for i, j in (
            (4352, 4607),
            (11904, 42191),
            (43072, 43135),
            (44032, 55215),
            (63744, 64255),
            (65072, 65103),
            (65381, 65500),
            (131072, 196607),
        )
    )


def main(target: tuple, quiet=False):

    searchTarget, targetType = target

    if targetType == "keyword":
        Actress(searchTarget).run()
        return
    elif targetType != "dir":
        raise RuntimeError(f"'{searchTarget}' should be either a directory or a keyword.")

    file_pool = []
    with ThreadPoolExecutor(max_workers=None) as executor:
        for basename, fullpath in list_dir(searchTarget):
            aFolder = ActressFolder(basename, fullpath)
            executor.submit(aFolder.run)
            file_pool.append(aFolder)

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
