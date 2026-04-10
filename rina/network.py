"""
Functionalities for making HTTP requests and parsing HTML content.

- request: Perform an HTTP request with site-specific settings and a managed
  session.
- get_tree: Retrieve and parse the HTML content of a web page into an
  HtmlElement.
- save_cookies: Persist cookies for a domain to profile/cookies.json.
"""

import json
import logging
import random
from functools import cache, lru_cache
from threading import Lock, Semaphore
from urllib.parse import urlparse

import requests
import urllib3
from lxml.etree import XPath
from lxml.html import HtmlElement, HTMLParser
from lxml.html import fromstring as html_fromstring

from .utils import Settings, cookies_file, get_config

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
    "proxy_country": None,
    "proxies": None,
}
SITE_SETTINGS = {
    "www.javbus.com": {
        "max_connection": 8,
        "cookies": {"existmag": "all"},
        "headers": {"Accept-Language": "zh-CN"},
    },
    # "javdb.com": {
    #     "max_connection": 1,
    #     "cookies": {"over18": "1", "locale": "zh"},
    # },
    "adult.contents.fc2.com": {
        "cookies": {"wei6H": "1", "language": "ja"},
        "headers": {"Accept-Language": "ja"},
        "proxy_country": "JP",
    },
    "www.mgstage.com": {
        "max_connection": 10,
        "cookies": {"adc": "1"},
        "proxy_country": "JP",
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
        "proxy_country": "JP",
    },
    "etigoya955.blog.fc2.com": {
        "cookies": {"age_check": "1"},
        "proxy_country": "JP",
    },
}

# ---------------------------------------------------------------------------
# Session & site initialization
# ---------------------------------------------------------------------------

_site_settings = {}
# Serializes lazy `_init_site` calls so concurrent worker threads don't each
# resolve their own proxy / build their own Semaphore for the same netloc.
# A single global lock is intentional: it lets `@cache`'d `_resolve_proxy`
# act as a true memoizer (the second thread sees the first thread's result),
# whereas per-netloc locks would re-introduce concurrent NordVPN API calls
# for the same country.
_init_lock = Lock()


def _init_session(retries=5, backoff=0.5):
    """Initializes and configures the HTTP session with retry logic."""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            ),
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

    # Load persisted cookies
    if cookies_file.exists():
        try:
            with open(cookies_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning("Failed to load %s: %s", cookies_file, e)
        else:
            for domain, cookies in data.items():
                for name, value in cookies.items():
                    s.cookies.set(name, value, domain=domain, path="/")
    return s


def _init_site(netloc: str) -> tuple[dict, Semaphore]:
    """Initializes the settings and semaphore for a specific domain."""
    setting = DEFAULT_SETTING.copy()
    site_setting = SITE_SETTINGS.get(netloc)
    if site_setting:
        setting.update(site_setting)
        # initialize cookies
        if setting["cookies"]:
            for k, v in setting["cookies"].items():
                session.cookies.set(k, v, domain=netloc)
    # Resolve effective proxy: site overrides global -p flag.
    country = setting["proxy_country"] or Settings.PROXY
    if country:
        proxies = _resolve_proxy(country)
        if proxies:
            setting["proxies"] = proxies
        elif proxies is False and Settings.PROXY:
            # User explicitly asked for -p but no credentials available. Warn
            # once and continue.
            _warn_no_proxy_credentials()
    logger.debug("Initialize '%s': %s", netloc, setting)
    return setting, Semaphore(setting["max_connection"])


def set_settings(netloc: str, **kwargs):
    """Updates the settings for a specific domain."""
    if netloc not in _site_settings:
        with _init_lock:
            if netloc not in _site_settings:
                _site_settings[netloc] = _init_site(netloc)
    _site_settings[netloc][0].update(kwargs)


# ---------------------------------------------------------------------------
# HTML fetching & parsing
# ---------------------------------------------------------------------------


def request(url: str, *, method="GET", pr=None, **kwargs):
    """
    Performs an HTTP request with site-specific settings.
    """
    method = method.upper()
    logger.debug("%s: %s", method, url)
    if pr is None:
        pr = urlparse(url)
    site_state = _site_settings.get(pr.netloc)
    if site_state is None:
        with _init_lock:
            site_state = _site_settings.get(pr.netloc)
            if site_state is None:
                site_state = _site_settings[pr.netloc] = _init_site(pr.netloc)
    setting, semaphore = site_state

    headers = setting["headers"]
    headers = headers.copy() if headers else {}
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    headers.setdefault("Referer", f"{pr.scheme}://{pr.netloc}/")

    kwargs.setdefault("proxies", setting["proxies"])
    with semaphore:
        return session.request(
            method,
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
        r = request(url, pr=pr, **kwargs)
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
# Proxy resolution (NordVPN, vendored from drivers/nordvpn.py)
# ---------------------------------------------------------------------------

_NORDVPN_API = "https://api.nordvpn.com/v1"
_NORDVPN_PORT = 89


@cache
def _nordvpn_country_ids() -> dict[str, int]:
    data = session.get(f"{_NORDVPN_API}/servers/countries", timeout=HTTP_TIMEOUT).json()
    return {c["code"].upper(): c["id"] for c in data}


@cache
def _resolve_proxy(country: bool | str) -> dict[str, str] | bool | None:
    """Resolve a proxy spec to a `requests` `proxies=` dict. `country=True`
    means any country (top-20 global), a string is a specific code (e.g.
    "JP"). Cached per spec so all sites in a run share one exit IP. Returns
    None on API failure (also cached) or False if NordVPN credentials are
    missing."""
    config = get_config()
    user = config.nordvpn_user
    pwd = config.nordvpn_pass
    if not (user and pwd):
        return False  # credentials missing
    try:
        params = "filters[servers_technologies][identifier]=proxy_ssl&limit=10"
        if isinstance(country, str):
            cid = _nordvpn_country_ids().get(country.upper())
            if not cid:
                raise ValueError(f"unknown country code: {country}")
            params += f"&filters[country_id]={cid}"
        servers = session.get(
            f"{_NORDVPN_API}/servers/recommendations?{params}",
            timeout=HTTP_TIMEOUT,
            proxies=None,
        ).json()
        if not servers:
            raise RuntimeError(f"no proxy_ssl servers found for {country}")
        host = random.choice(servers)["hostname"]
    except Exception as e:
        logger.warning("NordVPN proxy resolution failed (country=%s): %s", country, e)
        return
    logger.info(
        "NordVPN proxy resolved (country=%s)",
        country if isinstance(country, str) else "any",
    )
    url = f"https://{user}:{pwd}@{host}:{_NORDVPN_PORT}"
    return {"http": url, "https": url}


@cache
def _warn_no_proxy_credentials() -> None:
    """One-shot warning fired when `-p` is given but NordVPN credentials
    aren't configured. `@cache` on a no-arg function makes the body run
    exactly once across the process."""
    logger.warning(
        "NordVPN credentials not configured (run `rina set nordvpn`); "
        "the -p flag will be ignored."
    )


# ---------------------------------------------------------------------------
# Cookie persistence (profile/cookies.json)
# ---------------------------------------------------------------------------


def save_cookies(domain: str, names: tuple[str, ...] | None = None) -> None:
    """Persist current cookies for `domain` to profile/cookies.json. If
    `names` is given, only those cookies are kept (use this to skip
    ephemeral cookies like Laravel's `XSRF-TOKEN`, which Laravel regenerates
    on every response). Cookies for other domains in the file are preserved."""
    try:
        data = json.loads(cookies_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (FileNotFoundError, ValueError):
        data = {}
    data[domain] = {
        c.name: c.value
        for c in session.cookies
        if c.domain.lstrip(".") == domain and (names is None or c.name in names)
    }
    cookies_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookies_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Module-level initialization
# ---------------------------------------------------------------------------

session = _init_session()
xpath = lru_cache(XPath)
