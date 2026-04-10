import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .files import get_scanner
from .scraper import ScrapeResult, scrape
from .utils import AVInfo, Status, dryrun_method, strftime

NAMEMAX = 255
EXTS = {
    "3g2", "3gp", "3gp2", "3gpp", "amv", "asf", "avi", "divx", "dpg", "drc",
    "evo", "f4a", "f4b", "f4p", "f4v", "flv", "ifo", "k3g", "m1v", "m2t",
    "m2ts", "m2v", "m4b", "m4p", "m4v", "mkv", "mov", "mp2v", "mp4", "mpe",
    "mpeg", "mpeg2", "mpg", "mpv2", "mts", "mxf", "nsr", "nsv", "ogm", "ogv",
    "ogx", "qt", "ram", "rm", "rmvb", "rpm", "skm", "swf", "tp", "tpr", "ts",
    "vid", "viv", "vob", "webm", "wm", "wmp", "wmv", "wtv"
}  # fmt: skip


class AVString(AVInfo):
    """Handles keyword-based media sources."""

    keywidth = 10

    def __init__(self, source: str, result: ScrapeResult, error: Exception = None):
        self.source = source
        if result:
            self.status = Status.SUCCESS
            self.result = {
                "Target": source,
                "ProductID": result.product_id,
                "Title": result.title,
                "NewName": None,
                "OldName": None,
                "PubDate": strftime(result.date),
                "OldDate": None,
                "Source": result.source,
            }
        elif error is None:
            self.status = Status.FAILURE
            self.result = {
                "Target": source,
                "Result": "Information not found.",
            }
        else:
            self.status = Status.ERROR
            self.result = {
                "Target": source,
                "Error": error,
            }


class AVFile(AVString):
    """
    Manages file-based media sources, including file operations like renaming
    and timestamp updating.
    """

    source: Path
    newpath: Path = None
    newdate: tuple = None

    def __init__(
        self,
        source: Path,
        result: ScrapeResult,
        error: Exception = None,
    ) -> None:

        if not isinstance(source, Path):
            source = Path(source)
        super().__init__(source, result, error)
        if not result:
            return

        # Handling file renaming
        if result.product_id and result.title:
            newname = self._build_filename(
                result.product_id, result.title, source.suffix
            )
            if newname and newname != source.name:
                self.newpath = source.with_name(newname)
                self.result.update(OldName=source.name, NewName=self.newpath.name)
                self.status = Status.UPDATED

        # Handling file timestamp updating
        if result.date:
            stat = source.stat()
            if abs(result.date - stat.st_mtime) > 1:
                self.newdate = (stat.st_atime, result.date)
                self.result["OldDate"] = strftime(stat.st_mtime)
                self.status = Status.UPDATED

    @dryrun_method
    def apply(self):
        """Rename file and update timestamps based on scrape results."""
        source = self.source
        if self.newpath:
            os.rename(source, self.newpath)
            source = self.newpath
        if self.newdate:
            os.utime(source, self.newdate)

    @staticmethod
    def _build_filename(product_id: str, title: str, ext: str):
        """Generates a valid filename based on product ID, title, and ext."""
        namemax = NAMEMAX - len(product_id.encode()) - len(ext.encode()) - 1
        if namemax <= 0:
            return

        # Remove characters
        title = re.sub(r"[\x00-\x1f\x7f*]+", "", title)
        # Replace with '-'
        title = re.sub(r'[<>:"/\\|?-]+', "-", title)
        # Replace empty brackets with a space, and compress all spaces
        # opening brackets: [【「『｛（《\[(]
        # closing brackets: [】」』｝）》\])]
        title = re.sub(r"\s*[【「『｛（《\[(]\s*[】」』｝）》\])]\s*|\s+", " ", title)
        # Strip certain leading and trailing characters
        strip_chars = " -_。.,、"
        title = title.lstrip(" -_。.,、？！!…").rstrip(strip_chars)

        if len(title.encode("utf-8")) > namemax:
            # Remove spaces before and after non-word characters
            title = re.sub(r"\s+(?=[^\w\s])|(?<=[^\w\s])\s+", "", title)

            while len(title.encode("utf-8")) > namemax:
                # Truncate title:
                # Preserve trailing punctuations: `】」』｝）》\])？！!…`
                # Remove other non-word characters
                # ...]...   |   ...、...
                # ...]↑     |   ...↑
                m = re.search(r".*?\w.*(?:[】」』｝）》\])？！!…](?=.)|(?=\W))", title)
                if m:
                    title = m[0].rstrip(strip_chars)
                else:
                    # No suitable breakpoint is found, do a hard cut
                    title = title.encode("utf-8")[:namemax].decode("utf-8", "ignore")
                    break

        if re.search(r"\w", title):
            return f"{product_id} {title}{ext.lower()}"


def from_string(string: str):
    """Analyze a string, returns an AVString object."""
    try:
        return AVString(string, scrape(string))
    except Exception as e:
        return AVString(string, None, e)


def from_path(path):
    """Analyze a path, returns an AVFile object."""
    path = Path(path)
    try:
        return AVFile(path, scrape(path.stem))
    except Exception as e:
        return AVFile(path, None, e)


def from_args(args):
    """
    Scan a directory or file based on the provided arguments.
    :type args: argparse.Namespace
    """
    if args.type == "file":
        yield from_path(args.source)
        return

    scanner = get_scanner(args, exts=EXTS)
    with ThreadPoolExecutor() as ex:
        for ft in as_completed(
            ex.submit(from_path, e.path) for e in scanner.scandir(args.source)
        ):
            yield ft.result()
