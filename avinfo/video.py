import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from re import compile as re_compile
from re import search as re_search
from re import sub as re_sub

from avinfo import common
from avinfo.common import color_printer, epoch_to_str
from avinfo.scraper import SCRAPERS


class AVString:

    __slots__ = ("productId", "title", "publishDate", "titleSource", "dateSource", "_report", "_status")

    _str_cleaner_1 = re_compile(r"^(?:\[f?hd\]|[a-z0-9-]+\.[a-z]{2,}@)").sub
    _str_cleaner_2 = re_compile(
        r"""
        \[[a-z0-9.-]+\.[a-z]{2,}\]|
        (?:^|[^a-z0-9])
        (?:168x|44x|3xplanet|sis001|sexinsex|thz|uncensored|nodrm|fhd|tokyo[\s_-]?hot|1000[\s_-]?girl)
        (?:[^a-z0-9]|$)
        """,
        flags=re.VERBOSE,
    ).sub

    def __init__(self, string: str):

        # status: || dateDiff | filenameDiff | success ||
        self._status = 0b000
        self._report = report = {
            "Target": string,
            "ProductId": None,
            "Title": None,
            "PubDate": None,
            "FromDate": None,
            "NewName": None,
            "FromName": None,
            "Source": None,
        }

        string = self._str_cleaner_2(" ", self._str_cleaner_1("", string.lower()))
        try:
            result = next(filter(None, (s(string) for s in SCRAPERS)))
        except StopIteration:
            report["Error"] = "Information not found."
        except Exception as e:
            report["Error"] = str(e)
        else:
            self._status |= 0b001

            self.productId = report["ProductId"] = result.productId
            self.title = report["Title"] = result.title
            self.publishDate = result.publishDate
            self.titleSource = result.titleSource
            self.dateSource = result.dateSource
            report["PubDate"] = epoch_to_str(self.publishDate)
            report["Source"] = f'{self.titleSource or "---"} / {self.dateSource or "---"}'

    @property
    def scrape_failed(self):
        return self._status == 0b000

    @property
    def report(self):
        report = self._report
        if isinstance(report, dict):
            self._report = report = "".join(f'{k + ":":>10} {v}\n' for k, v in report.items() if v)
        return report

    def print(self):
        if self._status == 0b001:
            print(common.sepSuccess, self.report, sep="", end="")
        else:
            if self._status & 0b110:
                color = "yellow"
                sep = common.sepChanged
            else:
                color = "red"
                sep = common.sepFailed
            color_printer(sep, self.report, color=color, sep="", end="")


class AVFile(AVString):

    __slots__ = AVString.__slots__ + ("path", "newfilename", "_atime")

    def __init__(self, path: Path, stat: os.stat_result, namemax: int) -> None:

        super().__init__(path.stem)

        self.path = path
        self._report["Target"] = path

        if not self._status & 0b001:
            return

        if self.productId and self.title:
            name = self._get_filename(namemax)
            if name != path.name:
                self._status |= 0b010
                self.newfilename = name
                self._report.update(NewName=name, FromName=path.name)

        if self.publishDate and self.publishDate != stat.st_mtime:
            self._status |= 0b100
            self._atime = stat.st_atime
            self._report["FromDate"] = epoch_to_str(stat.st_mtime)

    @property
    def has_new_info(self):
        return bool(self._status & 0b110)

    def apply(self):
        path = self.path

        if self._status & 0b010:
            new = path.with_name(self.newfilename)
            os.rename(path, new)
            path = new

        if self._status & 0b100:
            os.utime(path, (self._atime, self.publishDate))

    def _get_filename(self, namemax: int):

        suffix = self.path.suffix.lower()
        namemax = namemax - len(self.productId.encode("utf-8")) - len(suffix.encode("utf-8")) - 1

        title = re_sub(r'[\s<>:"/\\|?* 　]+', " ", self.title)
        title = self._strip_title(title)

        strategy = self._trim_title
        while len(title.encode("utf-8")) >= namemax:
            try:
                title = strategy(title)
            except TypeError:
                strategy = lambda s: s[:-1]
                title = strategy(title)
            title = self._strip_title(title)

        return f"{self.productId} {title}{suffix}"

    @staticmethod
    def _trim_title(title: str):
        return re_search(r"^(.*\w[\s。！】」）…)\].]+).", title)[1]

    @staticmethod
    def _strip_title(title: str):
        return re_sub(r"^[\s._]+|[\s【「（。、\[(.,_]+$", "", title)


def scan_path(target: Path):

    try:
        namemax = os.statvfs(target).f_namemax
    except OSError:
        namemax = 255

    changed = []
    failed = []

    if not target.is_dir():
        avfile = AVFile(target, target.stat(), namemax)
        avfile.print()
        if avfile.has_new_info:
            changed.append(avfile)
        elif avfile.scrape_failed:
            failed.append(avfile)
        return 1, changed, failed

    total = 0
    is_video = re_compile(
        r"\.(?:3gp|asf|avi|bdmv|flv|iso|m(?:2?ts|4p|[24kop]v|p2|p4|pe?g|xf)|rm|rmvb|ts|vob|webm|wmv)",
        flags=re.IGNORECASE,
    ).fullmatch

    with ThreadPoolExecutor(max_workers=None) as ex:

        for ft in as_completed(
            ex.submit(AVFile, path, stat, namemax)
            for path, stat, _ in common.walk_dir(target, filesOnly=True)
            if is_video(path.suffix)
        ):
            total += 1
            avfile = ft.result()
            avfile.print()
            status = avfile._status
            if status & 0b110:  # has_new_info
                changed.append(avfile)
            elif status == 0b000:
                failed.append(avfile)

    return total, changed, failed


def update_dir_mtime(target: Path):
    def _change_mtime(path: Path, stat: os.stat_result):
        try:
            record = records[path]
        except KeyError:
            return False

        mtime = stat.st_mtime
        if record != mtime:
            try:
                os.utime(path, (stat.st_atime, record))
            except OSError as e:
                color_printer(f"Error: {path.name}  ({e})", color="red")
            else:
                print(f"{epoch_to_str(mtime, '%F')}  ==>  {epoch_to_str(record, '%F')}  {path.name}")
                return True

        return False

    print(common.sepBold)
    print("Scanning directory timestamps...")

    records = {}
    total = 1
    success = 0

    for path, stat, is_dir in common.walk_dir(target, filesOnly=False):
        if is_dir:
            total += 1
            success += _change_mtime(path, stat)
        else:
            mtime = stat.st_mtime
            for parent in path.parents:
                if records.get(parent, -1) < mtime:
                    records[parent] = mtime
                if parent == target:
                    break

    success += _change_mtime(target, target.stat())
    print(f"Finished. {total} dirs scanned, {success} modified.")
