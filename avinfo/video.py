import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator

from avinfo._utils import (SEP_CHANGED, SEP_FAILED, SEP_SUCCESS, color_printer,
                           re_compile, re_search, strftime)
from avinfo.scraper import ScrapeResult, _has_word, scrape

__all__ = ("from_string", "from_path", "scan_dir")
_fn_regex = None


class AVString:

    __slots__ = ("target", "product_id", "title", "publish_date", "source",
                 "status", "_report")

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
        return (
            f'{self.__class__.__name__}(target="{self.target}", status="{self.status}")'
        )

    def print(self):
        if self.status == "ok":
            print(SEP_SUCCESS, self.report, sep="\n")
        elif self.status == "changed":
            color_printer(SEP_CHANGED, self.report, red=False, sep="\n")
        else:
            color_printer(SEP_FAILED, self.report, sep="\n")

    @property
    def report(self):
        report = self._report
        if isinstance(report, dict):
            report = self._report = "\n".join(
                f'{k + ":":>10} {v}' for k, v in report.items() if v)
        return report


class AVFile(AVString):

    __slots__ = ("new_name", "_atime")
    target: Path

    def __init__(self,
                 target: Path,
                 result: ScrapeResult,
                 error: str,
                 stat: os.stat_result = None,
                 namemax: int = None):

        super().__init__(target, result, error)
        self.new_name = self._atime = None

        if not result:
            return

        if self.product_id and self.title:
            name = self._get_filename(namemax or _get_namemax(target))
            if name and name != target.name:
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

        suffix = self.target.suffix.lower()
        namemax -= len(self.product_id.encode()) + len(suffix.encode()) + 1
        if namemax <= 0:
            return

        try:
            clean, strip = _fn_regex
        except TypeError:
            clean = re_compile(r'[\s<>:"/\\|?* 　]+').sub
            strip = re_compile(r"^[\s._]+|[【「『｛（《\[(\s。.,、_]+$").sub
            _fn_regex = clean, strip
        title = strip("", clean(" ", self.title))

        while len(title.encode()) >= namemax:
            # Title is too long for a filename. Trying to find a reasonable
            # delimiter in order of:
            # 1) title[cut..., title]cut..., title!cut...
            # 2) title cut..., title,cut...
            m = re_search(
                r".*?\w.*(?:(?=[【「『｛（《\[(])|[】」』｝）》\])？！!…。.](?=.))|"
                r".*?\w.*[\s〜～●・,、_](?=.)",
                title,
            )
            if m:
                title = strip("", m[0])

            else:
                # no delimiter was found by re.search, we have to forcefully
                # delete some characters until title is shorter than namemax
                lo = 0
                hi = namemax
                while lo < hi:
                    mid = (lo + hi) // 2
                    if len(title[:mid + 1].encode()) < namemax:
                        lo = mid + 1
                    else:
                        hi = mid
                title = title[:lo]

                # check if it can still be called a title
                if _has_word(title):
                    break
                return

        return f"{self.product_id} {title}{suffix}"

    def apply(self):
        """Apply changes to file (rename and change timestamp).

        If no change was necessary, skips silently. Returns the new path.
        """
        path = self.target

        if self.status == "changed":

            if self.new_name:
                new = path.with_name(self.new_name)
                os.rename(path, new)
                path = new

            if self._atime:
                os.utime(path, (self._atime, self.publish_date))

        return path


def from_string(string: str):
    """Analyze a string, returns an AVString object."""

    try:
        result = scrape(string)
        error = None
    except Exception as e:
        if not isinstance(string, str):
            raise TypeError(f"expected str object, not {type(string)!r}")
        result = None
        error = str(e)

    return AVString(string, result, error)


def from_path(path, stat: os.stat_result = None, namemax: int = None):
    """Analyze a path, returns an AVFile object."""

    path = Path(path)

    try:
        result = scrape(path.stem)
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


def scan_dir(top_dir: Path, newer: float = None) -> Iterator[AVFile]:
    """Recursively scans a dir, yields AVFile objects."""

    namemax = _get_namemax(top_dir)

    with ThreadPoolExecutor() as ex:
        if newer is None:
            ft = (ex.submit(from_path, path, stat, namemax)
                  for path, stat in _probe_videos(top_dir))
        else:
            ft = (ex.submit(from_path, path, stat, namemax)
                  for path, stat in _probe_videos(top_dir)
                  if stat.st_mtime >= newer)
        for ft in as_completed(ft):
            yield ft.result()


def _probe_videos(root):
    ext = {
        "3gp", "asf", "avi", "bdmv", "flv", "iso", "m2ts", "m2v", "m4p", "m4v",
        "mkv", "mov", "mp2", "mp4", "mpeg", "mpg", "mpv", "mts", "mxf", "rm",
        "rmvb", "ts", "vob", "webm", "wmv"
    }
    stack = [root]
    while stack:
        root = stack.pop()
        try:
            with os.scandir(root) as it:
                for entry in it:
                    name = entry.name
                    if name[0] in "#@.":
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            name = name.rpartition(".")
                            if name[0] and name[2].lower() in ext:
                                yield entry.path, entry.stat()
                    except OSError:
                        pass
        except OSError as e:
            print(f'error occurred scanning "{root}": {e}', file=sys.stderr)


if os.name == "posix":

    def _get_namemax(path: Path):
        try:
            return os.statvfs(path).f_namemax
        except OSError as e:
            import warnings
            warnings.warn(f"getting filesystem namemax failed: {e}")
            return 255
else:

    def _get_namemax(path: Path):
        return 255


def update_dir_mtime(top_dir: Path):

    total = success = 0

    def probe_dir(root):

        nonlocal total, success

        total += 1
        newest = 0
        dirs = []

        with os.scandir(root) as it:
            for entry in it:
                if entry.name[0] in "#@.":
                    continue
                if entry.is_dir(follow_symlinks=False):
                    dirs.append(entry)
                else:
                    mtime = entry.stat().st_mtime
                    if mtime > newest:
                        newest = mtime

        for entry in dirs:
            mtime = probe_dir(entry)
            if mtime > newest:
                newest = mtime

        if newest:
            stat = root.stat()
            if newest != stat.st_mtime:
                try:
                    os.utime(root, (stat.st_atime, newest))
                except OSError as e:
                    print(e, file=sys.stderr)
                else:
                    success += 1
                    print("{} => {}: {}".format(strftime(stat.st_mtime),
                                                strftime(newest),
                                                os.fspath(root)))
        return newest

    print("Updating directory timestamps...")

    if not isinstance(top_dir, Path):
        top_dir = Path(top_dir)
    try:
        probe_dir(top_dir)
    except OSError as e:
        print(f"error occurred scanning {top_dir}: {e}", file=sys.stderr)
    else:
        print(f"Finished. {total} dirs scanned, {success} updated.")
