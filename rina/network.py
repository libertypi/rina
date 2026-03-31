"""
Functionalities for making HTTP requests and parsing HTML content.

- get: Perform a GET request with site-specific settings and a managed session.
- get_tree: Retrieve and parse the HTML content of a web page into an
  HtmlElement.
"""

import json
import logging
import random
from functools import lru_cache
from threading import Semaphore
from urllib.parse import urlparse

import requests
import urllib3
from lxml.etree import XPath
from lxml.html import HtmlElement, HTMLParser
from lxml.html import fromstring as html_fromstring

from .utils import join_root

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & per-site configuration
# ---------------------------------------------------------------------------

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
        "headers": {"Accept-Language": "zh-CN"},
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
    "www.kin8tengoku.com": {
        "cookies": {"adc": "1"},
        "headers": {"Accept": "text/html", "Rsc": "1"},
    },
    "mankowomiseruavzyoyu.blog.fc2.com": {
        "cookies": {"age_check": "1"},
    },
    "etigoya955.blog.fc2.com": {
        "cookies": {"age_check": "1"},
    },
}

# ---------------------------------------------------------------------------
# Session & site initialization
# ---------------------------------------------------------------------------

_site_settings = {}


def _init_session(retries=5, backoff=0.3, uafile="useragents.json"):
    """
    Initializes and configures the HTTP session with retry logic and random
    user-agent.
    """
    with open(join_root(uafile), "r", encoding="utf-8") as f:
        useragents = json.load(f)
    if not useragents:
        raise ValueError(f"Empty useragent file: '{uafile}'")
    logger.info("Load %s user-agents from '%s'", len(useragents), uafile)

    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": random.choice(useragents),
            "Accept-Language": "ja,zh;q=0.8,en-US;q=0.5,en;q=0.3",
        }
    )
    adapter = requests.adapters.HTTPAdapter(
        max_retries=urllib3.Retry(
            total=retries,
            status_forcelist={429, 500, 502, 503, 504, 521, 522, 523, 524},
            backoff_factor=backoff,
        )
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def _init_site(netloc: str) -> tuple[dict, Semaphore]:
    """Initializes the settings and semaphore for a specific domain."""
    setting = DEFAULT_SETTING.copy()
    site_setting = SITE_SETTINGS.get(netloc)
    if site_setting:
        setting.update(site_setting)
        # initialize cookies
        if setting["cookies"]:
            sc = session.cookies.set_cookie
            cc = requests.cookies.create_cookie
            for k, v in setting["cookies"].items():
                sc(cc(name=k, value=v, domain=netloc))
    logger.debug("Initialize '%s': %s", netloc, setting)
    return setting, Semaphore(setting["max_connection"])


def set_settings(netloc: str, **kwargs):
    """Updates the settings for a specific domain."""
    if netloc not in _site_settings:
        _site_settings[netloc] = _init_site(netloc)
    _site_settings[netloc][0].update(kwargs)


# ---------------------------------------------------------------------------
# HTML fetching & parsing
# ---------------------------------------------------------------------------


def get(url: str, *, pr=None, **kwargs):
    """
    Performs a GET request with site-specific settings.
    """
    logger.debug("GET: %s", url)
    if pr is None:
        pr = urlparse(url)
    try:
        setting, semaphore = _site_settings[pr.netloc]
    except KeyError:
        setting, semaphore = _site_settings[pr.netloc] = _init_site(pr.netloc)

    headers = setting["headers"]
    headers = headers.copy() if headers else {}
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    headers.setdefault("Referer", f"{pr.scheme}://{pr.netloc}/")

    with semaphore:
        return session.get(
            url,
            headers=headers,
            timeout=HTTP_TIMEOUT,
            **kwargs,
        )


_parsers = {}  # Cached HTML parsers


def get_tree(url: str, **kwargs) -> HtmlElement | None:
    """
    Fetches a web page and returns its parsed HTML tree.
    """
    pr = urlparse(url)
    try:
        r = get(url, pr=pr, **kwargs)
        r.raise_for_status()
    except requests.HTTPError as e:
        logger.debug(e)
        return
    except requests.RequestException as e:
        logger.warning(e)
        return
    encoding = (
        _site_settings[pr.netloc][0]["encoding"]
        or (r.encoding or r.apparent_encoding).lower()
    )
    try:
        parser = _parsers[encoding]
    except KeyError:
        try:
            parser = _parsers[encoding] = HTMLParser(encoding=encoding)
        except LookupError:
            parser = _parsers[encoding] = None
            logger.warning("Invalid encoding: '%s'. URL: '%s'", encoding, r.url)
    return html_fromstring(r.content, base_url=r.url, parser=parser)


# ---------------------------------------------------------------------------
# Module-level initialization
# ---------------------------------------------------------------------------

session = _init_session()
xpath = lru_cache(XPath)
