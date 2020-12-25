import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from os import scandir, stat_result
from pathlib import Path
from re import compile as re_compile
from typing import Iterator, List, Optional, Tuple

from bs4 import UnicodeDammit
from lxml.etree import XPath
from lxml.html import HtmlElement, fromstring
from requests import HTTPError, RequestException, Session

log_file = "logfile.log"
sep_width = 50
sep_bold = "=" * sep_width
sep_slim = "-" * sep_width
sep_success = "SUCCESS".center(sep_width, "-") + "\n"
sep_failed = "FAILED".center(sep_width, "-") + "\n"
sep_changed = "CHANGED".center(sep_width, "-") + "\n"
_colors = {"red": "\033[31m", "yellow": "\033[33m"}

session = Session()
session.headers.update(
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0"}
)

date_searcher = re_compile(
    r"""(?P<y>(?:19|20)[0-9]{2})\s*
    (?:(?P<han>年)|(?P<sep>[/.-]))\s*
    (?P<m>1[0-2]|0?[1-9])\s*
    (?(han)月|(?P=sep))\s*
    (?P<d>[12][0-9]|3[01]|0?[1-9])
    (?(han)\s*日|(?=$|[^0-9]))""",
    flags=re.VERBOSE,
).search


def color_printer(*args, color: str, **kwargs):
    print(_colors[color], end="")
    print(*args, **kwargs)
    print("\033[0m", end="")


def walk_dir(top_dir: Path, files_only: bool = False) -> Iterator[Tuple[Path, stat_result, bool]]:
    """Recursively yield 3-tuples of (path, stat, is_dir) in a bottom-top order."""

    with scandir(top_dir) as it:
        for entry in it:
            if entry.name[0] in "#@.":
                continue
            path = Path(entry.path)
            try:
                is_dir = entry.is_dir()
                if is_dir:
                    yield from walk_dir(path, files_only)
                    if files_only:
                        continue
                yield path, entry.stat(), is_dir
            except OSError as e:
                color_printer(f"Error occurred scanning {entry.path}: {e}", color="red")


def list_dir(top_dir: Path) -> Iterator[Path]:
    """List dir paths under top."""

    with scandir(top_dir) as it:
        for entry in it:
            if entry.name[0] not in "#@." and entry.is_dir():
                yield Path(entry.path)
    yield Path(top_dir)


def get_tree(url, *, decoder: str = None, **kwargs) -> Optional[HtmlElement]:
    """Downloads a page and returns lxml.html element tree.

    :param url, **kwargs: url and optional arguments `requests` take
    :param decoder: None (auto detect), lxml, or any encoding as string.
    """
    kwargs.setdefault("timeout", (7, 28))

    for retry in range(3):
        try:
            res = session.get(url, **kwargs)
            break
        except RequestException:
            if retry == 2:
                raise
            time.sleep(1)
    else:
        raise RequestException(url)
    try:
        res.raise_for_status()
    except HTTPError:
        return

    if decoder == "lxml":
        content = res.content
    elif decoder:
        res.encoding = decoder
        content = res.text
    else:
        content = UnicodeDammit(
            res.content,
            override_encodings=("utf-8", "euc-jp"),
            is_html=True,
        ).unicode_markup

    return fromstring(content, base_url=res.url)


def strptime(string: str, fmt: str) -> float:
    """Parse a string acroding to a format, returns epoch in UTC."""
    return datetime.strptime(string, fmt).replace(tzinfo=timezone.utc).timestamp()


def strftime(epoch: float, fmt: str = "%F") -> Optional[str]:
    """Convert an epoch timestamp in UTC to a string."""
    if isinstance(epoch, (float, int)):
        return time.strftime(fmt, time.gmtime(epoch))


def str_to_epoch(string: str) -> Optional[float]:
    """Search for YYYY-MM-DD like date in a string, returns epoch timestamp in UTC."""
    try:
        m = date_searcher(string)
        return datetime(int(m["y"]), int(m["m"]), int(m["d"]), tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        pass


def now(fmt: str = "%F %T") -> str:
    """Returns current local time as a string."""
    return time.strftime(fmt, time.localtime())


@lru_cache(maxsize=None)
def xpath(xpath: str, smart_strings: bool = False) -> XPath:
    """Returns a compiled XPath."""
    return XPath(xpath, smart_strings=smart_strings)


@lru_cache(maxsize=None)
def _re_method_cache(pattern: str, flags: int, method: str):
    """Returns a cached regex method"""
    if flags is None:
        pattern = re_compile(pattern)
    else:
        pattern = re_compile(pattern, flags=flags)
    return getattr(pattern, method)


def re_search(pattern: str, string: str, flags=None) -> Optional[re.Match]:
    return _re_method_cache(pattern, flags, "search")(string)


def re_sub(pattern: str, repl: str, string: str, flags=None) -> str:
    return _re_method_cache(pattern, flags, "sub")(repl, string)


def re_split(pattern: str, string: str, flags=None) -> List[str]:
    return _re_method_cache(pattern, flags, "split")(string)
