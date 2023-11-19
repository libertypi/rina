import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Generator

from avinfo.scandir import get_scanner, FileScanner
from avinfo.scraper import ScrapeResult, _has_word, scrape
from avinfo.utils import AVInfo, Status, re_search, re_sub, re_subn, strftime

_NAMEMAX = 255


class AVString(AVInfo):
    """
    Handles keyword-based media sources.
    """

    keywidth = 10

    def __init__(self, source: str, result: ScrapeResult, error: Exception = None):
        self.source = source
        if result:
            self.status = Status.SUCCESS
            self.result = {
                "Target": source,
                "ProductID": result.product_id,
                "Title": result.title,
                "PubDate": strftime(result.publish_date),
                "NewName": None,
                "FromDate": None,
                "FromName": None,
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
        entry: os.DirEntry = None,
    ) -> None:
        if not isinstance(source, Path):
            source = Path(source)
        super().__init__(source, result, error)
        if not result:
            return

        # Handling file renaming
        if result.product_id and result.title:
            new_name = self._get_filename(result.product_id, result.title)
            if new_name and new_name != source.name:
                self.newpath = source.with_name(new_name)
                self.result.update(NewName=new_name, FromName=source.name)
                self.status = Status.UPDATED

        # Handling file timestamp updating
        if result.publish_date:
            stat = (entry or source).stat()
            if result.publish_date != stat.st_mtime:
                self.newdate = (stat.st_atime, result.publish_date)
                self.result["FromDate"] = strftime(stat.st_mtime)
                self.status = Status.UPDATED

    def apply(self):
        """
        Implements file operations such as renaming and updating timestamps
        based on scrape results.
        """
        source = self.source
        if self.newpath:
            os.rename(source, self.newpath)
            source = self.newpath
        if self.newdate:
            os.utime(source, self.newdate)

    def _get_filename(self, product_id: str, title: str):
        """
        Generates a valid filename based on product ID, title, and specific
        naming rules.
        """
        suffix = self.source.suffix.lower()
        namemax = _NAMEMAX - len(product_id.encode()) - len(suffix.encode()) - 1
        if namemax <= 0:
            return

        # Replace forbidden characters with a whitespace
        title = re_sub(r'[\x00-\x1f\x7f\s<>:"/\\|?* 　]+', " ", title)

        # Replace empty brackets with a space, and eliminate repeating spaces
        # opening brackets: [【「『｛（《\[(]
        # closing brackets: [】」』｝）》\])]
        m = True
        while m:
            title, m = re_subn(r"[【「『｛（《\[(]\s*[】」』｝）》\])]|\s{2,}", " ", title)

        # Strip certain leading and trailing characters
        strip_re = r"^[-_\s。.,、？！!…]+|[-_\s。.,、]+$"
        title = re_sub(strip_re, "", title)

        while len(title.encode("utf-8")) > namemax:
            # Truncate title:
            # Preserve trailing punctuations: `】」』｝）》\])？！!…`
            # Remove other non-word characters
            # ...]...   |   ...、...
            # ...]↑     |   ...↑
            m = re_search(r".*?\w.*(?:[】」』｝）》\])？！!…](?=.)|(?=\W))", title)
            if m:
                title = re_sub(strip_re, "", m[0])
            else:
                # No suitable breakpoint is found, do a hard cut
                title = title.encode("utf-8")[:namemax].decode("utf-8", "ignore")
                if _has_word(title):
                    break
                return

        return f"{product_id} {title}{suffix}"


def from_string(string: str):
    """Analyze a string, returns an AVString object."""
    try:
        result = scrape(string)
        error = None
    except Exception as e:
        result = None
        error = e
    return AVString(string, result, error)


def from_path(path: str, entry: os.DirEntry = None):
    """Analyze a path, returns an AVFile object."""
    path = Path(path)
    try:
        result = scrape(path.stem)
        error = None
    except Exception as e:
        result = None
        error = e
    return AVFile(path, result, error, entry)


EXTS = {
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


def from_dir(root, scanner: FileScanner = None) -> Generator[AVFile, None, None]:
    """Scan a directory and yield AVFile objects."""
    if scanner is None:
        scanner = FileScanner(exts=EXTS)

    with ThreadPoolExecutor() as ex:
        for ft in as_completed(
            ex.submit(from_path, entry.path, entry)
            for entry in scanner.scandir(root, "file")
        ):
            yield ft.result()


def from_args(args):
    """:type args: argparse.Namespace"""
    return from_dir(args.source, get_scanner(args, exts=EXTS))
