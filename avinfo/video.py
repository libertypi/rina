import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator

from avinfo import common
from avinfo.common import color_printer, epoch_to_str, re_search, re_sub, sep_changed, sep_failed, sep_success
from avinfo.scraper import from_string


class AVString:

    __slots__ = ("productId", "title", "publishDate", "source", "_report", "_status")

    def __init__(self, string: str):

        # status: || dateDiff | filenameDiff | ok ||
        self._status = 0
        self.productId = self.title = self.publishDate = self.source = None
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

        try:
            result = from_string(string)
        except Exception as e:
            report["Error"] = str(e)
            return

        if not result:
            report["Error"] = "Information not found."
            return

        self._status |= 0b001
        self.productId = report["ProductId"] = result.productId
        self.title = report["Title"] = result.title
        self.publishDate = result.publishDate
        report["PubDate"] = epoch_to_str(self.publishDate)
        self.source = report["Source"] = result.source

    def print(self):
        if self._status == 0b001:
            print(sep_success, self.report, sep="", end="")
        elif self._status & 0b110:
            color_printer(sep_changed, self.report, color="yellow", sep="", end="")
        else:
            color_printer(sep_failed, self.report, color="red", sep="", end="")

    @property
    def report(self):
        report = self._report
        if isinstance(report, dict):
            self._report = report = "".join(f'{k + ":":>10} {v}\n' for k, v in report.items() if v)
        return report

    @property
    def ok(self):
        return not not self._status & 0b001


class AVFile(AVString):

    __slots__ = ("path", "newfilename", "_atime")

    def __init__(self, path: Path, stat: os.stat_result = None, namemax: int = None):

        super().__init__(path.stem)

        self.path = self._report["Target"] = path
        self.newfilename = None

        if not self._status & 0b001:
            return

        if self.productId and self.title:
            name = self._get_filename(namemax or _get_namemax(path))
            if name != path.name:
                self._status |= 0b010
                self.newfilename = name
                self._report.update(NewName=name, FromName=path.name)

        if self.publishDate:
            if not stat:
                stat = path.stat()
            if self.publishDate != stat.st_mtime:
                self._status |= 0b100
                self._atime = stat.st_atime
                self._report["FromDate"] = epoch_to_str(stat.st_mtime)

    def _get_filename(self, namemax: int):

        title = _strip_title(re_sub(r'[\s<>:"/\\|?* 　]+', " ", self.title))
        suffix = self.path.suffix.lower()
        namemax = namemax - len(self.productId.encode("utf-8")) - len(suffix.encode("utf-8")) - 1

        strategy = _trim_title
        while len(title.encode("utf-8")) >= namemax:
            try:
                title = strategy(title)
            except TypeError:
                strategy = lambda s: s[:-1]
                title = strategy(title)
            title = _strip_title(title)

        return f"{self.productId} {title}{suffix}"

    def apply(self):
        path = self.path

        if self._status & 0b011 == 0b011:
            new = path.with_name(self.newfilename)
            os.rename(path, new)
            path = new

        if self._status & 0b101 == 0b101:
            os.utime(path, (self._atime, self.publishDate))

    @property
    def has_new_info(self):
        return not not self._status & 0b110


def _strip_title(s: str):
    return re_sub(r"^[\s._]+|[【「『｛（《\[(\s。.,、_]+$", "", s)


def _trim_title(string: str):
    return (
        re_search(r"^.*?\w.*(?:(?=[【「『｛（《\[(])|[】」』｝）》\])？！!…。.](?=.))", string)
        or re_search(r"^.*?\w.*[\s〜～●・,、_](?=.)", string)
    )[0]


def _get_namemax(path: Path):
    try:
        return os.statvfs(path).f_namemax
    except OSError:
        return 255


def scan_path(target: Path, is_dir: bool = None) -> Iterator[AVFile]:

    if is_dir is None:
        is_dir = target.is_dir()

    if not is_dir:
        yield AVFile(target)
        return

    namemax = _get_namemax(target)
    video_ext = {
        ".3gp",
        ".asf",
        ".avi",
        ".bdmv",
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
    }

    with ThreadPoolExecutor(max_workers=None) as ex:
        for ft in as_completed(
            ex.submit(AVFile, path, stat, namemax)
            for path, stat, _ in common.walk_dir(target, files_only=True)
            if path.suffix.lower() in video_ext
        ):
            yield ft.result()


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

    print(common.sep_bold)
    print("Updating directory timestamps...")

    records = {}
    total = 1
    success = 0

    for path, stat, is_dir in common.walk_dir(target, files_only=False):
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
