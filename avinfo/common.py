import re
from datetime import datetime, timezone
from functools import lru_cache
from os import scandir, stat_result
from pathlib import Path
from re import compile as re_compile
from re import search as re_search
from re import split as re_split
from re import sub as re_sub
from time import sleep
from typing import Iterator, Optional, Tuple

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
_file_filter = frozenset("#@.")
_colors = {"red": "\033[31m", "yellow": "\033[33m"}

session = Session()
session.headers.update(
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0"}
)

date_searcher = re_compile(
    r"""(?P<y>(?:19|20)[0-9]{2})\s*
    (?:(?P<han>年)|(?P<pun>[/.-]))\s*
    (?P<m>1[0-2]|0?[1-9])\s*
    (?(han)月|(?P=pun))\s*
    (?P<d>3[01]|[12][0-9]|0?[1-9])
    (?(han)\s*日)""",
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
            if entry.name[0] in _file_filter:
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
            try:
                if entry.name[0] not in _file_filter and entry.is_dir():
                    yield Path(entry.path)
            except OSError as e:
                color_printer(f"Error occurred scanning {entry.path}: {e}", color="red")

    if top_dir.name[0] not in _file_filter:
        yield Path(top_dir)


def get_tree(url, *, decoder: str = None, **kwargs) -> Optional[HtmlElement]:
    """Downloads a page and returns lxml.html element tree.

    :param url, **kwargs: url and optional arguments `requests` take
    :param decoder: None (auto detect), lxml, or any encoding as string.
    """
    for retry in range(3):
        try:
            res = session.get(url, **kwargs, timeout=(7, 28))
            break
        except RequestException:
            if retry == 2:
                raise
            sleep(1)
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


def text_to_epoch(string: str) -> Optional[float]:
    try:
        return str_to_epoch(date_searcher(string).expand(r"\g<y> \g<m> \g<d>"), regex=None)
    except (TypeError, AttributeError):
        pass


def str_to_epoch(string: str, fmt: str = "%Y %m %d", regex=re_compile(r"[^0-9]+")) -> float:
    if regex:
        string = regex.sub(" ", string).strip()
    return datetime.strptime(string, fmt).replace(tzinfo=timezone.utc).timestamp()


def epoch_to_str(epoch: float, fmt: str = "%F %T") -> Optional[str]:
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(fmt)
    except TypeError:
        pass


def now(fmt: str = "%F %T") -> str:
    return datetime.now().strftime(fmt)


@lru_cache(maxsize=None)
def xpath(xpath: str) -> XPath:
    """Returns a compiled XPath."""
    return XPath(xpath)
