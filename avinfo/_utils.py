import re
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from random import choice as random_choice
from re import compile as re_compile
from re import search as re_search
from re import sub as re_sub
from typing import Optional

import requests
from lxml.etree import XPath
from lxml.html import HtmlElement
from lxml.html import fromstring as html_fromstring
from requests.exceptions import HTTPError, RequestException
from urllib3 import Retry

SEP_WIDTH = 50
SEP_BOLD = "=" * SEP_WIDTH
SEP_SLIM = "-" * SEP_WIDTH
SEP_SUCCESS = " SUCCESS ".center(SEP_WIDTH, "-")
SEP_FAILED = " FAILED ".center(SEP_WIDTH, "-")
SEP_CHANGED = " CHANGED ".center(SEP_WIDTH, "-")
HTTP_TIMEOUT = (9.1, 60)

join_root = Path(__file__).parent.joinpath
stderr_write = sys.stderr.write
date_searcher = re_compile(
    r"""(?P<y>(?:[1１][9９]|[2２][0０])\d\d)\s*
    (?:(?P<han>年)|(?P<sep>[／/.－-]))\s*
    (?P<m>[1１][0-2０-２]|[0０]?[1-9１-９])\s*
    (?(han)月|(?P=sep))\s*
    (?P<d>[12１２][0-9０-９]|[3３][01０１]|[0０]?[1-9１-９])
    (?(han)\s*日|(?=$|\D))""",
    flags=re.VERBOSE,
).search


def _init_session(retries=5, backoff=0.3, uafile="useragents.txt"):
    with open(join_root(uafile), "r", encoding="utf-8") as f:
        useragents = tuple(filter(None, map(str.strip, f)))
    if not useragents:
        raise ValueError("The user-agent list must not be empty.")

    session = requests.Session()
    session.headers["User-Agent"] = random_choice(useragents)
    adapter = requests.adapters.HTTPAdapter(
        max_retries=Retry(
            total=retries,
            status_forcelist=frozenset((429, 500, 502, 503, 504, 524)),
            backoff_factor=backoff,
        )
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session, useragents


def set_cookie(domain: str, name: str, value: str):
    session.cookies.set_cookie(
        requests.cookies.create_cookie(domain=domain, name=name, value=value)
    )


if sys.stdout.isatty():

    def color_printer(*args, sep=None, end=None, red: bool = True):
        """Print text to stdout in red or yellow color."""
        print("\033[31m" if red else "\033[33m", end="")
        print(*args, sep=sep, end=end)
        print("\033[0m", end="", flush=True)

else:

    def color_printer(*args, sep=None, end=None, red: bool = True):
        print(*args, sep=sep, end=end)


def get_choice_as_int(msg: str, max_opt: int) -> int:
    while True:
        stderr_write(msg)
        try:
            choice = int(input())
        except ValueError:
            pass
        else:
            if 1 <= choice <= max_opt:
                return choice
        stderr_write("Invalid option.\n")


def get_tree(url, *, encoding: str = None, **kwargs) -> Optional[HtmlElement]:
    """Downloads a page and returns lxml.html element tree.

    :param url, **kwargs: url and optional arguments `requests` take
    :param encoding: None (feed bytes to lxml), "auto" (detect by requests), or any
    encodings
    """
    try:
        response = session.get(
            url,
            headers={"User-Agent": random_choice(useragents)},
            timeout=HTTP_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
    except HTTPError:
        return
    except RequestException as e:
        stderr_write(f"{e}\n")
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
    return datetime.strptime(string, fmt).replace(tzinfo=timezone.utc).timestamp()


def strftime(epoch: float, fmt: str = "%F") -> Optional[str]:
    """Convert an epoch timestamp in UTC to a string."""
    if isinstance(epoch, (float, int)):
        return time.strftime(fmt, time.gmtime(epoch))


def str_to_epoch(string: str) -> Optional[float]:
    """Search for YYYY-MM-DD like date in a string, returns UTC epoch timestamp."""
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


xpath = lru_cache(XPath)
session, useragents = _init_session()
