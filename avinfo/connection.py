from functools import lru_cache
from random import choice as random_choice
from threading import Semaphore
from typing import Optional
from urllib.parse import ParseResult, urlparse

import requests
import urllib3
from lxml.etree import XPath
from lxml.html import HtmlElement, HTMLParser
from lxml.html import fromstring as html_fromstring
from requests.exceptions import HTTPError, RequestException

from avinfo.utils import join_root, stderr_write

xpath = lru_cache(XPath)
HTTP_TIMEOUT = (9.1, 60)
DEFAULT_SETTING = {
    "max_connection": 5,
    "cookies": None,
    "headers": None,
    "encoding": None,
}
SITE_SETTINGS = {
    "www.javbus.com": {
        "max_connection": 10,
        "cookies": {"existmag": "all"},
        "headers": {"Accept-Language": "zh"},
    },
    "javdb.com": {
        "max_connection": 1,
        "cookies": {"over18": "1", "locale": "zh"},
    },
    "adult.contents.fc2.com": {
        "cookies": {"wei6H": "1", "language": "ja"},
        "headers": {"Accept-Language": "ja"},
    },
    "www.mgstage.com": {
        "cookies": {"adc": "1"},
    },
    "www.caribbeancom.com": {
        "encoding": "euc-jp",
    },
    "www.caribbeancompr.com": {
        "encoding": "euc-jp",
    },
    "db.msin.jp": {
        "cookies": {"age": "off"},
    },
}


@lru_cache
def _get_setting(netloc: str):
    domain_settings = SITE_SETTINGS.get(netloc)
    if domain_settings is None:
        return DEFAULT_SETTING
    setting = DEFAULT_SETTING.copy()
    setting.update(domain_settings)
    return setting


def _init_site(netloc: str, setting: dict):
    if setting["cookies"]:
        sc = session.cookies.set_cookie
        cc = requests.cookies.create_cookie
        for k, v in setting["cookies"].items():
            sc(cc(name=k, value=v, domain=netloc))


def _init_session(retries=7, backoff=0.3, uafile="useragents.txt"):
    with open(join_root(uafile), "r", encoding="utf-8") as f:
        useragents = tuple(filter(None, map(str.strip, f)))
    if not useragents:
        raise ValueError(f"Corrupted useragent file: {uafile}")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": random_choice(useragents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
    )
    adapter = requests.adapters.HTTPAdapter(
        max_retries=urllib3.Retry(
            total=retries,
            status_forcelist=frozenset((429, 500, 502, 503, 504, 521, 524)),
            backoff_factor=backoff,
        )
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session, useragents


session, useragents = _init_session()
_semaphores = {}


def get(url: str, /, pr: ParseResult = None, check: bool = True, **kwargs):
    if pr is None:
        pr = urlparse(url)
    netloc = pr.netloc
    setting = _get_setting(netloc)

    headers = setting["headers"]
    if headers:
        headers = headers.copy()
        if "User-Agent" not in headers:
            headers["User-Agent"] = random_choice(useragents)
    else:
        headers = {"User-Agent": random_choice(useragents)}
    headers.setdefault("Referer", f"{pr.scheme}://{netloc}/")
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))

    kwargs.setdefault("timeout", HTTP_TIMEOUT)

    try:
        semaphore = _semaphores[netloc]
    except KeyError:
        _init_site(netloc, setting)
        semaphore = _semaphores[netloc] = Semaphore(setting["max_connection"])

    with semaphore:
        res = session.get(url, headers=headers, **kwargs)
    if check:
        res.raise_for_status()
    return res


_parsers = {}


def get_tree(url: str, **kwargs) -> Optional[HtmlElement]:
    pr = urlparse(url)
    try:
        res = get(url, pr=pr, **kwargs)
    except HTTPError:
        return
    except RequestException as e:
        stderr_write(f"{e}\n")
        return

    encoding = (
        _get_setting(pr.netloc)["encoding"] or res.encoding or res.apparent_encoding
    ).lower()
    try:
        parser = _parsers[encoding]
    except KeyError:
        try:
            parser = _parsers[encoding] = HTMLParser(encoding=encoding)
        except LookupError:
            parser = _parsers[encoding] = None
    return html_fromstring(res.content, base_url=res.url, parser=parser)
