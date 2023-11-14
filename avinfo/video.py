import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator

from avinfo._utils import (
    SEP_CHANGED,
    SEP_FAILED,
    SEP_SUCCESS,
    color_printer,
    stderr_write,
    strftime,
)
from avinfo.scraper import ScrapeResult, _has_word, _subspace, scrape

__all__ = ("from_string", "from_path", "scan_dir")
_NAMEMAX = 255


class AVString:
    __slots__ = (
        "target",
        "product_id",
        "title",
        "publish_date",
        "source",
        "status",
        "_report",
    )

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
        """Print report to stdout."""
        if self.status == "ok":
            print(SEP_SUCCESS, self.report, sep="\n")
        elif self.status == "changed":
            color_printer(SEP_CHANGED, self.report, sep="\n", red=False)
        else:
            color_printer(SEP_FAILED, self.report, sep="\n")

    @property
    def report(self):
        report = self._report
        if isinstance(report, dict):
            report = self._report = "\n".join(
                f"{k:>10}: {v}" for k, v in report.items() if v
            )
        return report


class AVFile(AVString):
    __slots__ = ("new_name", "_atime")
    target: Path

    def __init__(
        self,
        target: Path,
        result: ScrapeResult,
        error: str,
        stat: os.stat_result = None,
    ):
        super().__init__(target, result, error)
        self.new_name = self._atime = None

        if not result:
            return

        if self.product_id and self.title:
            name = self._get_filename()
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

    def _get_filename(self):
        suffix = self.target.suffix.lower()
        namemax = _NAMEMAX - len(self.product_id.encode()) - len(suffix.encode()) - 1
        if namemax <= 0:
            return

        # Replace forbidden characters with a whitespace
        title = re.sub(r'[\x00-\x1f\x7f\s<>:"/\\|?* 　]+', " ", self.title)

        # Replace empty brackets with a space
        # opening brackets: [【「『｛（《\[(]
        # closing brackets: [】」』｝）》\])]
        while True:
            title, m = re.subn(r"[【「『｛（《\[(]\s*[】」』｝）》\])]", " ", title)
            if not m:
                break
            title = _subspace(" ", title)

        # Strip certain leading and trailing characters
        strip_re = re.compile(r"^[-_\s。.,、？！!…]+|[-_\s。.,、]+$").sub
        title = strip_re("", title)

        while len(title.encode("utf-8")) > namemax:
            # Truncate title:
            # Preserve trailing punctuations: `】」』｝）》\])？！!…`
            # Remove other non-word characters
            # ...]...   |   ...、...
            # ...]↑     |   ...↑
            m = re.search(r".*?\w.*(?:[】」』｝）》\])？！!…](?=.)|(?=\W))", title)
            if m:
                title = strip_re("", m[0])
            else:
                # No suitable breakpoint is found, do a hard cut
                title = title.encode("utf-8")[:namemax].decode("utf-8", "ignore")
                if _has_word(title):
                    break
                return

        return f"{self.product_id} {title}{suffix}"

    def apply(self):
        """Apply changes to file, returns the new path.

        If there is no changed attributes, skips silently.
        """
        path = self.target
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


def from_path(path, stat: os.stat_result = None):
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
    )


def scan_dir(top_dir: Path, newer: float = None) -> Iterator[AVFile]:
    """Recursively scans a dir, yields AVFile objects."""

    with ThreadPoolExecutor() as ex:
        if newer is None:
            ft = (
                ex.submit(from_path, path, stat)
                for path, stat in _probe_videos(top_dir)
            )
        else:
            ft = (
                ex.submit(from_path, path, stat)
                for path, stat in _probe_videos(top_dir)
                if stat.st_mtime >= newer
            )
        for ft in as_completed(ft):
            yield ft.result()


def _probe_videos(root):
    ext = {
        "3g2",
        "3gp",
        "amv",
        "asf",
        "avi",
        "divx",
        "f4a",
        "f4b",
        "f4p",
        "f4v",
        "flv",
        "hevc",
        "iso",
        "m2ts",
        "m2v",
        "m4p",
        "m4v",
        "mkv",
        "mov",
        "mp2",
        "mp4",
        "mpe",
        "mpeg",
        "mpg",
        "mpv",
        "mts",
        "mxf",
        "ogv",
        "qt",
        "rm",
        "rmvb",
        "svi",
        "swf",
        "ts",
        "viv",
        "vob",
        "webm",
        "wmv",
        "yuv",
    }
    stack = [root]
    while stack:
        root = stack.pop()
        try:
            with os.scandir(root) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name[0] not in "#@":
                                stack.append(entry.path)
                        else:
                            name = entry.name.rpartition(".")
                            if name[0] and name[2].lower() in ext:
                                yield entry.path, entry.stat()
                    except OSError:
                        pass
        except OSError as e:
            stderr_write(f'error occurred scanning "{root}": {e}\n')
