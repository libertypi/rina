"""
Functionalities for making HTTP requests and parsing HTML content.

- get: Perform a GET request with site-specific settings and a managed session.
- get_tree: Retrieve and parse the HTML content of a web page into an
  HtmlElement.
"""

import json
import logging
from functools import lru_cache
from random import choice as random_choice
from threading import Semaphore
from typing import Optional, Tuple
from urllib.parse import ParseResult, urlparse

import requests
import urllib3
from lxml.etree import XPath
from lxml.html import HtmlElement, HTMLParser
from lxml.html import fromstring as html_fromstring
from requests.exceptions import HTTPError, RequestException

from .utils import join_root

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = (9.1, 60)  # (connect, read)
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
        "max_connection": 10,
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


def set_alias(name: str, dst: str):
    """Sets an alias for a site's settings, mirroring another site's
    configuration."""
    SITE_SETTINGS[name] = SITE_SETTINGS[dst]


def _init_session(retries=7, backoff=0.3, uafile="useragents.json"):
    """
    Initializes and configures the HTTP session with retry logic and random
    user-agent.
    """
    with open(join_root(uafile), "r", encoding="utf-8") as f:
        useragents = json.load(f)
    assert useragents, f"Empty useragent data: '{uafile}'"
    logger.debug("Load %s user-agents from '%s'", len(useragents), uafile)

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
            status_forcelist={429, 500, 502, 503, 504, 521, 524},
            backoff_factor=backoff,
        )
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session, useragents


def _init_site(netloc: str) -> Tuple[dict, Semaphore]:
    """Initializes the settings and semaphore for a specific domain."""
    result = SITE_SETTINGS.get(netloc)
    if not result:
        setting = DEFAULT_SETTING
    else:
        setting = DEFAULT_SETTING.copy()
        setting.update(result)
        # initialize cookies
        if setting["cookies"]:
            sc = session.cookies.set_cookie
            cc = requests.cookies.create_cookie
            for k, v in setting["cookies"].items():
                sc(cc(name=k, value=v, domain=netloc))
    logger.debug("Initialize '%s': %s", netloc, setting)
    return setting, Semaphore(setting["max_connection"])


_settings = {}  # Cached site settings


def get(url: str, *, pr: ParseResult = None, **kwargs):
    """
    Performs a GET request with site-specific settings.
    """
    logger.debug("GET: %s", url)
    if pr is None:
        pr = urlparse(url)
    try:
        setting, semaphore = _settings[pr.netloc]
    except KeyError:
        setting, semaphore = _settings[pr.netloc] = _init_site(pr.netloc)

    headers = setting["headers"]
    headers = headers.copy() if headers else {}
    headers.setdefault("User-Agent", random_choice(useragents))
    headers.setdefault("Referer", f"{pr.scheme}://{pr.netloc}/")

    with semaphore:
        return session.get(url, headers=headers, timeout=HTTP_TIMEOUT, **kwargs)


_parsers = {}  # Cached HTML parsers based on encoding


def get_tree(url: str, **kwargs) -> Optional[HtmlElement]:
    """
    Fetches a web page and returns its parsed HTML tree.
    """
    pr = urlparse(url)
    try:
        response = get(url, pr=pr, **kwargs)
        response.raise_for_status()
    except HTTPError as e:
        logger.debug(e)
        return
    except RequestException as e:
        logger.warning(e)
        return
    encoding = (
        _settings[pr.netloc][0]["encoding"]
        or response.encoding
        or response.apparent_encoding
    ).lower()
    try:
        parser = _parsers[encoding]
    except KeyError:
        try:
            parser = _parsers[encoding] = HTMLParser(encoding=encoding)
        except LookupError:
            parser = _parsers[encoding] = None
            logger.warning("Invalid encoding: '%s'. URL: '%s'", encoding, response.url)
    return html_fromstring(response.content, base_url=response.url, parser=parser)


session, useragents = _init_session()
xpath = lru_cache(XPath)  # Cached XPath function for performance
