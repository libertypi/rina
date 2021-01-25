import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from re import compile as re_compile
from typing import Optional

import requests
from lxml.etree import XPath
from lxml.html import HtmlElement, fromstring as html_fromstring
from requests import HTTPError
from urllib3 import Retry

SEP_WIDTH = 50
SEP_BOLD = "=" * SEP_WIDTH
SEP_SLIM = "-" * SEP_WIDTH
SEP_SUCCESS = "SUCCESS".center(SEP_WIDTH, "-")
SEP_FAILED = "FAILED".center(SEP_WIDTH, "-")
SEP_CHANGED = "CHANGED".center(SEP_WIDTH, "-")
HTTP_TIMEOUT = (6.1, 30)

date_searcher = re_compile(
    r"""(?P<y>(?:[1１][9９]|[2２][0０])\d\d)\s*
    (?:(?P<han>年)|(?P<sep>[／/.－-]))\s*
    (?P<m>[1１][0-2０-２]|[0０]?[1-9１-９])\s*
    (?(han)月|(?P=sep))\s*
    (?P<d>[12１２][0-9０-９]|[3３][01０１]|[0０]?[1-9１-９])
    (?(han)\s*日|(?=$|\D))""",
    flags=re.VERBOSE,
).search


def _init_session(retries: int = 5, backoff: float = 0.1):
    session = requests.Session()
    session.headers.update({
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:80.0) Gecko/20100101 Firefox/80.0"
    })
    adapter = requests.adapters.HTTPAdapter(
        max_retries=Retry(total=retries,
                          status_forcelist=frozenset((500, 502, 503, 504)),
                          backoff_factor=backoff))
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def color_printer(*args, red: bool = True, **kwargs):
    print("\033[31m" if red else "\033[33m", end="")
    print(*args, **kwargs)
    print("\033[0m", end="")


def get_choice_as_int(msg: str, max_opt: int) -> int:
    while True:
        try:
            choice = int(input(msg))
        except ValueError:
            pass
        else:
            if 1 <= choice <= max_opt:
                return choice
        color_printer("Invalid option.")


def get_tree(url, *, encoding: str = None, **kwargs) -> Optional[HtmlElement]:
    """Downloads a page and returns lxml.html element tree.

    :param url, **kwargs: url and optional arguments `requests` take
    :param encoding: None (feed bytes to lxml), "auto" (detect by requests), or any
    encodings
    """
    response = session.get(url, timeout=HTTP_TIMEOUT, **kwargs)
    try:
        response.raise_for_status()
    except HTTPError:
        return

    if encoding:
        if encoding != "auto":
            response.encoding = encoding
        content = response.text
    else:
        content = response.content

    return html_fromstring(content, base_url=response.url)


def strptime(string: str, fmt: str) -> float:
    """Parse a string acroding to a format, returns epoch in UTC."""
    return datetime.strptime(string,
                             fmt).replace(tzinfo=timezone.utc).timestamp()


def strftime(epoch: float, fmt: str = "%F") -> Optional[str]:
    """Convert an epoch timestamp in UTC to a string."""
    if isinstance(epoch, (float, int)):
        return time.strftime(fmt, time.gmtime(epoch))


def str_to_epoch(string: str) -> Optional[float]:
    """Search for YYYY-MM-DD like date in a string, returns epoch timestamp in UTC."""
    try:
        m = date_searcher(string)
        return datetime(
            int(m["y"]),
            int(m["m"]),
            int(m["d"]),
            tzinfo=timezone.utc,
        ).timestamp()
    except (TypeError, ValueError):
        pass


@lru_cache(maxsize=None)
def xpath(xpath: str, smart_strings: bool = False) -> XPath:
    """Returns a compiled XPath."""
    return XPath(xpath, smart_strings=smart_strings)


@lru_cache(maxsize=None)
def _cache_re_method(pattern: str, method: str):
    """Returns a cached regex method"""
    return getattr(re_compile(pattern), method)


def re_search(pattern: str, string: str) -> Optional[re.Match]:
    return _cache_re_method(pattern, "search")(string)


def re_sub(pattern: str, repl, string: str) -> str:
    return _cache_re_method(pattern, "sub")(repl, string)


session = _init_session()
