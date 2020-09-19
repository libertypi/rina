import os
import re
from concurrent.futures import ThreadPoolExecutor

from avinfo import common
from avinfo.common import epoch_to_str, printProgressBar, printRed
from avinfo.videoscraper import scrape

_re_cleanName = tuple(
    (re.compile(i), j)
    for i, j in ((r'[\s<>:"/\\|?* 　]', " "), (r"[\s._]{2,}", " "), (r"^[\s._-]+|[\s【\[（(.,_-]+$", ""))
)


class AV:

    scrapeKey = frozenset(("productId", "title", "publishDate", "titleSource", "dateSource"))

    def __init__(self, target: str):
        self.target = target
        self.basename = target.lower()
        # status: dateDiff filenameDiff success started
        self.status = 0b0000
        self.keyword = self.exception = self.dFormat = self.log = None
        for k in self.scrapeKey:
            setattr(self, k, None)

    def start_search(self):
        self.status |= 0b0001
        try:
            result = scrape(self)
        except Exception as e:
            self.exception = e
        else:
            if result:
                self.status |= 0b0010
                self._analyze_scrape(result)
        self._gen_report()

    def set_keyword(self, keyword: str):
        self.keyword = keyword

    def set_date_string(self, string: str, dFormat: str):
        self.keyword = string
        self.dFormat = dFormat

    def _analyze_scrape(self, result: dict):
        if not self.scrapeKey.issuperset(result):
            raise ValueError(f'Wrong value returned by scraper: "{result}"')
        for k, v in result.items():
            setattr(self, k, v)

    def _gen_report(self):
        if self._discard_result():
            return

        status = self.status
        logs = [("Target", self.target)]

        if status & 0b0010:
            if self.productId:
                logs.append(("ProductId", self.productId))
            if self.title:
                logs.append(("Title", self.title))
            if self.publishDate:
                logs.append(("Pub Date", epoch_to_str(self.publishDate)))
            if status & 0b1000:
                logs.append(("From Date", epoch_to_str(self.mtime)))
            if status & 0b0100:
                logs.append(("New Name", self.newfilename))
                logs.append(("From Name", self.filename))
            logs.append(
                (
                    "Source",
                    f"{self.titleSource if self.titleSource else '---'} / {self.dateSource if self.dateSource else '---'}",
                )
            )
            sepLine = common.sepSuccess
            printer = print
        else:
            logs.append(("Keyword", self.keyword if self.keyword else "---"))
            if self.exception:
                logs.append(("Error", self.exception))
            sepLine = common.sepFailed
            printer = printRed

        self.log = "".join(f"{k:>10}: {v}\n" for k, v in logs)
        printer(f"{sepLine}{self.log}", end="")

    def _discard_result(self):
        """didn't start at all"""
        return not self.status & 0b0001


class AVFile(AV):

    videoExt = frozenset(
        (
            ".3gp",
            ".asf",
            ".avi",
            ".dsm",
            ".flv",
            ".iso",
            ".m2ts",
            ".m2v",
            ".m4p",
            ".m4v",
            ".mkv",
            ".mov",
            ".mp2",
            ".mp4",
            ".mpeg",
            ".mpg",
            ".mpv",
            ".mts",
            ".mxf",
            ".rm",
            ".rmvb",
            ".ts",
            ".vob",
            ".webm",
            ".wmv",
        )
    )

    def __init__(self, target: str, stat: os.stat_result, namemax: int):
        super().__init__(target)
        self.atime, self.mtime = stat.st_atime, stat.st_mtime
        self.namemax = namemax
        self.dirpath, self.filename = os.path.split(target)
        self.basename, self.ext = os.path.splitext(self.filename.lower())

    def start_search(self):
        if not self.ext in self.videoExt:
            return
        super().start_search()

    def _analyze_scrape(self, result: dict):
        super()._analyze_scrape(result)
        if self.productId and self.title:
            self._set_newfilename()
            if self.newfilename != self.filename:
                self.status |= 0b0100
        if self.publishDate and self.publishDate != self.mtime:
            self.status |= 0b1000

    def _set_newfilename(self):
        self.productId = self.productId.strip()
        self.title = self.title.strip()
        namemax = self.namemax - len(self.ext.encode("utf-8"))

        filename = f"{self.productId} {self.title}"
        for p, r in _re_cleanName:
            filename = p.sub(r, filename)

        while len(filename.encode("utf-8")) >= namemax:
            newname = re.match(r"(.*[^\s。,([])[\s。,([]", filename).group(1)
            if newname == self.productId:
                while True:
                    filename = filename[:-1].rstrip(",.-【（([")
                    if len(filename.encode("utf-8")) < namemax:
                        break
                break
            else:
                filename = newname

        self.newfilename = f"{filename}{self.ext}"

    def _discard_result(self):
        """
        True if: didn't start, started and success but nothing new.
        False if: started and success and something new, started but failed.
        status: 001X or XXX0.
        """
        return self.status & 0b1110 == 0b0010 or super()._discard_result()

    def has_new_info(self):
        """Return True if the search successfully finished and new info was found."""
        return self.status & 0b1100 and self.status & 0b0011 == 0b0011

    def apply(self) -> bool:
        try:
            if self.status & 0b0111 == 0b0111:
                newpath = os.path.join(self.dirpath, self.newfilename)
                os.rename(self.target, newpath)
                self.target = newpath
            if self.status & 0b1011 == 0b1011:
                os.utime(self.target, (self.atime, self.publishDate))
        except Exception as e:
            self.exception = e
            return False
        return True


def main(target: tuple, quiet=False):

    searchTarget, targetType = target

    if targetType == "keyword":
        AV(searchTarget).start_search()
        return
    elif targetType != "dir" and targetType != "file":
        raise ValueError('TargetType should be "dir", "file" or "keyword".')

    try:
        namemax = os.statvfs(searchTarget).f_namemax
    except Exception as e:
        namemax = 255
        printRed(f"Error: Unable to detect filename length limit, using default value (255). {e}")

    if targetType == "dir":
        files_pool = []
        with ThreadPoolExecutor(max_workers=None) as executor:
            for path, stat, isdir in common.walk_dir(searchTarget, filesOnly=True):
                avFile = AVFile(path, stat, namemax)
                executor.submit(avFile.start_search)
                files_pool.append(avFile)
    else:
        avFile = AVFile(searchTarget, os.stat(searchTarget), namemax)
        files_pool = (avFile,)
        avFile.start_search()

    files_pool = tuple(avFile for avFile in files_pool if avFile.has_new_info())
    print(common.sepBold)

    if not files_pool:
        print("File scan finished, no file can be modified.")
    else:
        print(f"File scan finished.")

        while not quiet:
            msg = f"""{len(files_pool)} files can be modified.
Please choose an option:
1) Apply changes.
2) Reload changes.
3) Quit without applying.
"""
            choice = input(msg)
            if choice == "1":
                break
            elif choice == "3":
                return

            print(common.sepBold)
            if choice == "2":
                common.printObjLogs(files_pool)
            else:
                print("Invalid option.")
            print(common.sepBold)

        print("Applying changes...")
        errors = []
        sepLine = f"{common.sepSlim}\n"
        total = len(files_pool)
        printProgressBar(0, total)

        with open(common.logFile, "a", encoding="utf-8") as f:
            for i, avFile in enumerate(files_pool, 1):
                if avFile.apply():
                    f.write(f"[{epoch_to_str(None)}] File Update\n")
                    f.write(avFile.log)
                    f.write(sepLine)
                else:
                    errors.extend(f"{i:>6}: {j}" for i, j in (("Target", avFile.target), ("Type", avFile.exception)))
                printProgressBar(i, total)

        if errors:
            printRed(f"{'Errors':>6}:")
            printRed("\n".join(errors))

    handle_dirs(target)


def handle_dirs(target: tuple):
    def _change_mtime(path: str, stat: os.stat_result):
        nonlocal success
        record = records.get(path)
        if record and record != stat.st_mtime:
            try:
                os.utime(path, (stat.st_atime, record))
                print(
                    f"{epoch_to_str(stat.st_mtime, '%F')}  ==>  {epoch_to_str(record, '%F')}  {os.path.basename(path)}"
                )
                success += 1
            except Exception as e:
                printRed(f"Error: {os.path.basename(path)}  ({e})")

    searchTarget, targetType = target
    if targetType != "dir":
        return

    dirname = os.path.dirname
    rootLen = len(searchTarget)
    records = {}
    total = 1
    success = 0

    print(common.sepBold)
    print("Scanning directory timestamps...")

    for path, stat, isdir in common.walk_dir(searchTarget, filesOnly=False):
        if isdir:
            total += 1
            _change_mtime(path, stat)
        else:
            parent = dirname(path)
            while len(parent) >= rootLen and parent != path:
                if records.get(parent, -1) < stat.st_mtime:
                    records[parent] = stat.st_mtime
                path = parent
                parent = dirname(parent)
    _change_mtime(searchTarget, os.stat(searchTarget))

    print(f"Finished. {total} dirs scanned, {success} modified.")
