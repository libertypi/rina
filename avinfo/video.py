import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator

from avinfo._utils import (
    color_printer,
    re_compile,
    re_search,
    sep_bold,
    sep_changed,
    sep_failed,
    sep_success,
    strftime,
)
from avinfo.scraper import ScrapeResult, scrape

__all__ = ("from_string", "from_path", "scan_dir")


class AVString:

    __slots__ = ("target", "product_id", "title", "publish_date", "source", "status", "_report")

    def __init__(self, target: str, result: ScrapeResult, error: str):

        self.target = target

        if result:
            self.status = "ok"
            self.product_id = result.product_id
            self.title = result.title
            self.publish_date = result.publish_date
            self.source = result.source
            self._report = {
                "Target": target,
                "ProductId": self.product_id,
                "Title": self.title,
                "NewName": None,
                "FromName": None,
                "PubDate": strftime(self.publish_date),
                "FromDate": None,
                "Source": self.source,
            }
        else:
            self.status = "failed"
            self.product_id = self.title = self.publish_date = self.source = None
            self._report = {
                "Target": target,
                "Error": error or "Information not found.",
            }

    def __repr__(self):
        return f'{self.__class__.__name__}(target="{self.target}", status="{self.status}")'

    def print(self):
        if self.status == "ok":
            print(sep_success, self.report, sep="", end="")
        elif self.status == "changed":
            color_printer(sep_changed, self.report, color="yellow", sep="", end="")
        else:
            color_printer(sep_failed, self.report, color="red", sep="", end="")

    @property
    def report(self):
        report = self._report
        if isinstance(report, dict):
            report = self._report = "".join(f'{k + ":":>10} {v}\n' for k, v in report.items() if v)
        return report


_fn_regex = None


class AVFile(AVString):

    __slots__ = ("new_name", "_atime")
    target: Path

    def __init__(self, target: Path, result: ScrapeResult, error, stat=None, namemax=None):

        super().__init__(target, result, error)
        self.new_name = self._atime = None

        if not result:
            return

        if self.product_id and self.title:
            name = self._get_filename(namemax or _get_namemax(target))
            if name != target.name:
                self.new_name = name
                self._report.update(NewName=name, FromName=target.name)
                self.status = "changed"

        if self.publish_date:
            if not stat:
                stat = target.stat()
            if self.publish_date != stat.st_mtime:
                self._atime = stat.st_atime
                self._report["FromDate"] = strftime(stat.st_mtime)
                self.status = "changed"

    def _get_filename(self, namemax: int):

        global _fn_regex

        try:
            clean, strip = _fn_regex
        except TypeError:
            clean = re_compile(r'[\s<>:"/\\|?* 　]+').sub
            strip = re_compile(r"^[\s._]+|[【「『｛（《\[(\s。.,、_]+$").sub
            _fn_regex = clean, strip

        title = strip("", clean(" ", self.title))
        suffix = self.target.suffix.lower()
        namemax -= len(self.product_id.encode("utf-8")) + len(suffix.encode("utf-8")) + 1
        strategy = self._trim_title

        while len(title.encode("utf-8")) >= namemax:
            try:
                title = strategy(title)
            except TypeError:
                strategy = lambda s: s[:-1]
                title = strategy(title)
            title = strip("", title)

        return f"{self.product_id} {title}{suffix}"

    @staticmethod
    def _trim_title(string: str):
        return (
            re_search(r"^.*?\w.*(?:(?=[【「『｛（《\[(])|[】」』｝）》\])？！!…。.](?=.))", string)
            or re_search(r"^.*?\w.*[\s〜～●・,、_](?=.)", string)
        )[0]

    def apply(self):
        path = self.target

        if self.new_name is not None:
            new = path.with_name(self.new_name)
            os.rename(path, new)
            path = new

        if self._atime is not None:
            os.utime(path, (self._atime, self.publish_date))


def _get_namemax(path):
    if os.name == "posix":
        try:
            return os.statvfs(path).f_namemax
        except OSError:
            pass
    return 255


def _walk_dir(top_dir: Path, files_only: bool = False):
    """Recursively yield 3-tuples of (path, stat, is_dir) in a bottom-top order."""

    with os.scandir(top_dir) as it:
        for entry in it:
            if entry.name[0] in "#@.":
                continue
            path = Path(entry.path)
            is_dir = entry.is_dir()
            if is_dir:
                yield from _walk_dir(path, files_only)
                if files_only:
                    continue
            try:
                yield path, entry.stat(), is_dir
            except OSError as e:
                import warnings

                warnings.warn(f"Error occurred scanning {entry.path}:\n{e}")


def from_string(string: str):
    """Analyze a string, returns an AVString object."""

    try:
        result = scrape(string)
        error = None
    except Exception as e:
        result = None
        error = str(e)

    return AVString(string, result, error)


def from_path(path: Path, stat: os.stat_result = None, namemax: int = None):
    """Analyze a file, returns an AVFile object."""

    try:
        stem = path.stem
    except AttributeError:
        path = Path(path)
        stem = path.stem
    try:
        result = scrape(stem)
        error = None
    except Exception as e:
        result = None
        error = str(e)

    return AVFile(
        path,
        result,
        error,
        stat=stat,
        namemax=namemax,
    )


def scan_dir(top_dir: Path) -> Iterator[AVFile]:
    """Recursively scans a dir, yields AVFile objects."""

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
    namemax = _get_namemax(top_dir)

    with ThreadPoolExecutor(max_workers=None) as ex:
        for ft in as_completed(
            ex.submit(from_path, path, stat, namemax)
            for path, stat, _ in _walk_dir(top_dir, files_only=True)
            if path.suffix.lower() in video_ext
        ):
            yield ft.result()


def update_dir_mtime(target: Path):
    def _process_dir(path: Path, stat: os.stat_result):
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
                print(f"{strftime(mtime)}  ==>  {strftime(record)}  {path.name}")
                return True
        return False

    print(sep_bold)
    print("Updating directory timestamps...")

    records = {}
    records_get = records.get
    total = 1
    success = 0

    for path, stat, is_dir in _walk_dir(target, files_only=False):
        if is_dir:
            total += 1
            success += _process_dir(path, stat)
        else:
            mtime = stat.st_mtime
            for parent in path.parents:
                if records_get(parent, -1) < mtime:
                    records[parent] = mtime
                if parent == target:
                    break

    success += _process_dir(target, target.stat())
    print(f"Finished. {total} dirs scanned, {success} modified.")
