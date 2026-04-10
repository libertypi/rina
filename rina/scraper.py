import datetime
import html
import json
import logging
import re
from abc import ABC
from dataclasses import dataclass
from threading import Lock

import requests

from . import network, utils
from .network import get_tree, html_fromstring, xpath
from .utils import str_to_epoch, strptime

logger = logging.getLogger(__name__)

# Regular expressions
RE_Y = utils.two_digit_regex(0, datetime.date.today().year % 100)
RE_M = r"0[1-9]|1[0-2]"
RE_D = r"[12][0-9]|0[1-9]|3[01]"

_brace_re = r"[\s()\[\].-]+"
_id_re = r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*"
_trash_re = (
    r"\b("
    r"([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,4}@|"
    r"[\[(](([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,4}|hd|jav)[\])]|"
    r"([a-z]+2048|\d+sht|thzu?|168x|44x|hotavxxx|nyap2p|3xplanet|sogclub|sis001|sexinsex|hhd800|kfa11)(\.[a-z]{2,4})?|"
    r"dioguitar23|(un|de)censored|nodrm|fhd|1000[\s-]*giri"
    r")\b|\s+"
)


@dataclass(slots=True)
class ScrapeResult:
    source: str
    product_id: str = None
    title: str = None
    date: float = None


class Scraper(ABC):
    """Base class for all scrapers."""

    regex: str
    search_id: str
    uncensored: bool = False
    _id_mask = None

    def __init__(self, match: re.Match) -> None:
        self.match = match
        self.string = match.string

    def search(self):
        for func in self._search, self._javbus:
            result = func()
            if result:
                try:
                    product_id = re.sub(r"\s+", "", result.product_id)
                    title = re.sub(r"\s+", " ", result.title).strip()
                except TypeError:
                    continue
                if re.fullmatch(_id_re, product_id) and re.search(r"\w", title):
                    result.product_id = self._add_suffix(product_id)
                    result.title = title
                    result.date = str_to_epoch(result.date)
                    return result

    def _search(self) -> ScrapeResult | None:
        """
        Abstract method to be implemented by subclasses:
         - Set `self.search_id`
         - Conduct site-specific searches
        """
        raise NotImplementedError

    def _javbus(self):
        try:
            res = network.request(
                f"https://www.javbus.com/uncensored/search/{self.search_id}"
            )
            if "member.php?mod=logging" in res.url:
                logger.warning("JavBus is walled, consider switching network.")
                return
            res.raise_for_status()
            http_ok = True
        except requests.HTTPError:
            if self.uncensored:
                return
            http_ok = False
        except requests.RequestException as e:
            logger.warning(e)
            return

        tree = html_fromstring(res.content)
        if http_ok:
            result = self._parse_javbus(tree)
            if result or self.uncensored:
                return result

        result = xpath(
            'string(//div[@class="search-header"]//li[@role="presentation"][1])'
        )(tree)
        if re.search(r"/\s*0+\s*\)", result):
            return

        tree = get_tree(f"https://www.javbus.com/search/{self.search_id}")
        if tree is not None:
            return self._parse_javbus(tree)

    def _parse_javbus(self, tree: network.HtmlElement):
        mask = self._get_id_mask()
        for span in tree.iterfind(
            './/div[@id="waterfall"]//a[@class="movie-box"]//span'
        ):
            product_id = span.findtext("date[1]", "")
            if mask(product_id):
                title = span.text
                try:
                    if title[0] == "【":
                        title = re.sub(r"^【(お得|特価|4K)】\s*", "", title)
                except IndexError:
                    continue
                return ScrapeResult(
                    product_id=product_id,
                    title=title,
                    date=span.findtext("date[2]"),
                    source="javbus.com",
                )

    # disabled: behind Cloudflare
    # def _javdb(self):
    #     tree = get_tree(f"https://javdb.com/search?q={self.search_id}&f=all")
    #     if tree is None or "/search" not in tree.base_url:
    #         return

    #     mask = self._get_id_mask()
    #     for v in xpath(
    #         './/div[contains(@class, "movie-list")]'
    #         '//a[@class="box"]/div[@class="video-title"]'
    #     )(tree):
    #         product_id = v.findtext("strong", "")
    #         if mask(product_id):
    #             return ScrapeResult(
    #                 product_id=product_id,
    #                 title=xpath("string(text())")(v),
    #                 date=v.findtext('../div[@class="meta"]'),
    #                 source="javdb.com",
    #             )

    def _get_id_mask(self):
        mask = self._id_mask
        if not mask:
            mask = re.sub(
                r"[\s_-]+((?=\d))?",
                lambda m: r"[\s_-]*" if m[1] is None else r"[\s_-]*0*",
                self.search_id,
            )
            mask = self._id_mask = re.compile(rf"\s*{mask}\s*", re.IGNORECASE).fullmatch
        return mask

    def _add_suffix(self, product_id: str) -> str:
        m = self.match
        suffix = re.search(
            r"^\s*(?:(?:f?hd|cd|dvd|vol|[hm]hb|part)\s*|(?:4k|sd|(?:216|108|72|48)0p)\s+)*"
            r"(?P<s>[1-9][0-9]?|[a-d])\b",
            re.sub(_brace_re, " ", self.string[m.end(m.lastindex) :]),
        )
        if suffix:
            return f'{product_id}-{suffix["s"].upper()}'
        return product_id

    def warning(self, msg):
        logger.warning(
            "[Class: %s] [Input: %s] %s", self.__class__.__name__, self.string, msg
        )

    def error(self, msg):
        logger.error(
            "[Class: %s] [Input: %s] %s", self.__class__.__name__, self.string, msg
        )


class StudioScraper(Scraper):
    uncensored = True
    regex = r"(?P<studio>(?P<s1>{m}{d}{y}|(?P<s4>{y}{m}{d}))-(?P<s2>[0-9]{{2,4}})(?:-(?P<s3>0[0-9]))?)".format(
        y=rf"(?:{RE_Y})",
        m=rf"(?:{RE_M})",
        d=rf"(?:{RE_D})",
    )
    _std_re = (
        r"\b(?:"
        r"(?P<_caribpr>carib(?:bean(?:com)?)?pr|カリビアンコムプレミアム)|"  # 101515_391-caribpr
        r"(?P<_carib>carib(?:bean(?:com)?)?|カリビアンコム)|"  # 112220-001-carib
        r"(?P<_1pon>1pon(?:do)?|一本道)|"  # 110411_209-1pon
        r"(?P<_10mu>10mu(?:sume)?|天然むすめ)|"  # 122812_01-10mu
        r"(?P<_paco>paco(?:pacomama)?|パコパコママ)|"  # 120618_394-paco
        r"(?P<_mura>mura)(?:mura)?|"  # 010216_333-mura
        r"(?P<_mesubuta>mesubuta|メス豚)"  # 160122_1020_01-mesubuta
        r")\b"
    )
    datefmt: str = "%m%d%y"
    studio: str = None

    def search(self):
        match = self.match
        self.search_id = f'{match["s1"]}_{match["s2"]}'

        m = self.studio_match = re.search(self._std_re, self.string)
        if m:
            self._search = getattr(self, m.lastgroup)
        elif match["s3"] and match["s4"]:
            self._search = self._mesubuta

        result = super().search()

        if result and (result.source.startswith("jav") or not result.date):
            try:
                result.date = strptime(match["s1"], self.datefmt)
            except ValueError as e:
                self.warning(e)
        return result

    def _search(self) -> ScrapeResult | None:
        tree = get_tree(f"https://www.javbus.com/{self.search_id}")

        if tree is None:
            search_id = self.search_id.replace("_", "-")
            tree = get_tree(f"https://www.javbus.com/{search_id}")
            if tree is None:
                return
            self.search_id = search_id

        tree = tree.find('.//div[@class="container"]')
        try:
            title = tree.findtext("h3").strip()
        except AttributeError as e:
            self.error(e)
            return

        product_id = ""
        date = studio = None
        get_value = lambda p: re.sub(r"\s+", "", p.text_content().partition(":")[2])

        for p in xpath(
            './/div[contains(@class, "movie")]'
            '/div[contains(@class, "info")]'
            '/p[span/text() and contains(., ":")]'
        )(tree):
            k = p.findtext("span")
            if "識別碼" in k:
                product_id = get_value(p)
            elif "日期" in k:
                date = get_value(p)
            elif "製作商" in k:
                studio = re.search(self._std_re, get_value(p))
                if product_id and date:
                    break

        if studio:
            result = getattr(self, studio.lastgroup)()
            if result:
                return result

        mask = self._get_id_mask()
        if title and mask(product_id):
            if title.startswith(product_id):
                title = title[len(product_id) :]

            return ScrapeResult(
                product_id=product_id,
                title=title,
                date=date,
                source="javbus.com",
            )

    def _carib(self, url: str = None, source: str = None):
        if not url:
            self.studio = "carib"
            self.search_id = self.search_id.replace("_", "-")
            source = "caribbeancom.com"
            url = "https://www.caribbeancom.com"

        tree = get_tree(f"{url}/moviepages/{self.search_id}/")
        if tree is None:
            return

        tree = tree.find('.//div[@id="moviepages"]')
        try:
            title = tree.findtext('.//div[@class="heading"]/h1')
        except AttributeError as e:
            self.error(e)
            return

        date = xpath(
            'string(.//li[@class="movie-spec"]'
            '/span[contains(text(), "配信日") or contains(text(), "販売日")]'
            '/following-sibling::span[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            product_id=self.search_id,
            title=title,
            date=date,
            source=source,
        )

    def _caribpr(self):
        self.studio = "caribpr"
        return self._carib(
            url="https://www.caribbeancompr.com",
            source="caribbeancompr.com",
        )

    def _1pon(self, url: str = None, source: str = None):
        if not url:
            self.studio = "1pon"
            url = "https://www.1pondo.tv"
            source = "1pondo.tv"
        try:
            data = network.request(
                f"{url}/dyn/phpauto/movie_details/movie_id/{self.search_id}.json"
            )
            data.raise_for_status()
        except requests.HTTPError as e:
            logger.debug(e)
            return
        except requests.RequestException as e:
            logger.warning(e)
            return
        try:
            data = data.json()
            return ScrapeResult(
                product_id=data["MovieID"],
                title=data["Title"],
                date=data["Release"],
                source=source,
            )
        except (ValueError, KeyError) as e:
            self.error(e)

    def _10mu(self):
        self.studio = "10mu"
        return self._1pon(
            url="https://www.10musume.com",
            source="10musume.com",
        )

    def _paco(self):
        self.studio = "paco"
        return self._1pon(
            url="https://www.pacopacomama.com",
            source="pacopacomama.com",
        )

    def _mura(self):
        self.studio = "mura"
        return self._1pon(
            url="https://www.muramura.tv",
            source="muramura.tv",
        )

    def _mesubuta(self) -> None:
        self.studio = "mesubuta"
        self.datefmt = "%y%m%d"
        if self.match["s3"]:
            self.search_id = "_".join(self.match.group("s1", "s2", "s3"))

    def _add_suffix(self, product_id: str) -> str:
        result = [product_id, self.studio] if self.studio else [product_id]

        i = self.match.end()
        if self.studio_match:
            i = max(self.studio_match.end(), i)

        suffix = re.search(
            r"^\s*(([1-9]|(high|mid|low|whole|hd|sd|psp)[0-9]*|(216|108|72|48)0p)($|\s))+",
            re.sub(_brace_re, " ", self.string[i:]),
        )
        if suffix:
            result.extend(suffix[0].split())

        return "-".join(result)


class HeyzoScraper(Scraper):
    uncensored = True
    source = "heyzo.com"
    regex = r"heyzo[^0-9]*(?P<heyzo>[0-9]{4})"

    def _search(self):
        uid = self.match["heyzo"]
        self.search_id = f"HEYZO-{uid}"

        tree = get_tree(f"https://www.heyzo.com/moviepages/{uid}/")
        if tree is None:
            return
        try:
            data = _load_json_ld(tree)
            return ScrapeResult(
                product_id=self.search_id,
                title=data["name"],
                date=data["dateCreated"],
                source=self.source,
            )
        except TypeError:
            pass
        except (ValueError, KeyError) as e:
            self.warning(e)

        tree = tree.find('.//div[@id="wrapper"]//div[@id="movie"]')
        try:
            title = tree.findtext("h1").rpartition("\t-")
            date = tree.find(
                './/table[@class="movieInfo"]//*[@class="table-release-day"]'
            ).text_content()
        except AttributeError as e:
            self.error(e)
        else:
            return ScrapeResult(
                product_id=self.search_id,
                title=title[0] or title[2],
                date=date,
                source=self.source,
            )


class FC2Scraper(Scraper):
    uncensored = True
    regex = r"fc2(?:[\s-]*ppv)?[\s-]+(?P<fc2>[0-9]{4,10})"
    _paywalled = False
    # Tri-state shared across all instances:
    #   None    -> not yet attempted
    #   True    -> session is live, no need to re-login
    #   False -> credentials missing or login was rejected, give up
    _fc2ppvdb_authed = None
    # Single lock that serializes the ENTIRE fc2ppvdb code path: fetch
    # (prime + AJAX), login, and retry. Three races collapse onto one fix:
    #   1. fc2ppvdb stores "currently visited article" in server-side
    #      session state — two threads interleaving prime+AJAX pairs
    #      clobber each other and one gets an empty 200 back.
    #   2. Concurrent login attempts race on the CSRF cookie/token and
    #      all fail with 419 Page Expired.
    #   3. A login in progress in one thread mustn't be interleaved with
    #      a fetch from another, which would overwrite the post-login
    #      cookies the server expects on the next request.
    # All three reduce to "serialize everything fc2ppvdb does." Throughput
    # cost: fc2ppvdb fetches are now strictly sequential — fine since it's
    # a fallback scraper and the server-side state already forbids any
    # real parallelism.
    _fc2ppvdb_lock = Lock()

    def _search(self):
        uid = self.match["fc2"]
        self.search_id = f"FC2-{uid}"
        return self._fc2_search(uid) or self._fc2ppvdb(uid)

    def _fc2_search(self, uid: str):
        """Search for FC2 video by uid."""
        if self._paywalled:
            return
        tree = get_tree(f"https://adult.contents.fc2.com/article/{uid}/")
        if tree is None:
            return
        if "payarticle" in tree.base_url:
            logger.warning("FC2.com is paywalled. Use a Japanese proxy to bypass.")
            FC2Scraper._paywalled = True
            return
        if tree.find('.//div[@class="items_notfound_wp"]') is not None:
            return

        return ScrapeResult(
            product_id=self.search_id,
            title=(
                xpath(
                    'string(.//div[@class="items_article_MainitemThumb"]//img/@title)'
                )(tree)
                or "".join(
                    xpath('.//div[@class="items_article_headerInfo"]/h3/text()')(tree)
                )
            ),
            date=(
                xpath(
                    'string(.//div[@class="items_article_softDevice"]'
                    '/p[starts-with(normalize-space(text()), "販売日")])'
                )(tree)
                or tree.findtext('.//div[@class="items_article_Releasedate"]/p')
            ),
            source="fc2.com",
        )

    def _fc2ppvdb(self, uid: str):
        """Fetch from fc2ppvdb.com. Logs in once per process if cached
        cookies are stale or absent. Returns None on miss or auth failure.

        The whole flow runs under a single lock — see `_fc2ppvdb_lock`
        for why."""
        # Cheap pre-check before grabbing the lock.
        if FC2Scraper._fc2ppvdb_authed is False:
            return

        with FC2Scraper._fc2ppvdb_lock:
            # Re-check: another thread's login may have flipped this to
            # False while we were queued at the lock.
            if FC2Scraper._fc2ppvdb_authed is False:
                return None

            result, needs_login = self._fc2ppvdb_fetch(uid)
            if result is not None or not needs_login:
                return result

            # Auth failure. Login if we haven't yet succeeded.
            if FC2Scraper._fc2ppvdb_authed is not True:
                if not self._fc2ppvdb_login():
                    FC2Scraper._fc2ppvdb_authed = False
                    return None

            # Retry with the freshly authenticated session.
            result, _ = self._fc2ppvdb_fetch(uid)
            return result

    def _fc2ppvdb_fetch(self, uid: str):
        """Returns (ScrapeResult|None, needs_login: bool). `needs_login` is
        True only when the response indicates an auth failure (redirect to
        /login or AJAX 401); other failure modes return False so we don't
        waste a login.

        Caller must hold `_fc2ppvdb_lock`. The HTML article page is just a
        thin shell — the metadata lives in a JSON AJAX endpoint that gates
        on a CSRF token from the matching HTML page. We must fetch the
        HTML first to prime the session and extract the token, then call
        /articles/article-info."""
        article_url = f"https://fc2ppvdb.com/articles/{uid}"
        # Step 1: prime — fetch the HTML page for the CSRF token.
        try:
            r = network.request(article_url)
            r.raise_for_status()
        except requests.HTTPError as e:
            logger.debug(e)
            return None, False
        except requests.RequestException as e:
            logger.warning(e)
            return None, False
        if "/login" in r.url:
            return None, True
        token = html_fromstring(r.content).xpath(
            'string(//meta[@name="csrf-token"]/@content)'
        )
        if not token:
            logger.warning("fc2ppvdb: no CSRF token on /articles/%s", uid)
            return None, False

        # Step 2: pull the article metadata via the JSON AJAX endpoint.
        try:
            r = network.request(
                "https://fc2ppvdb.com/articles/article-info",
                params={"videoid": uid},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRF-TOKEN": token,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": article_url,
                },
            )
            r.raise_for_status()
        except requests.HTTPError as e:
            # 401 means our session cookie is stale — signal the caller
            # to log in and retry. Other HTTP errors are not.
            if e.response is not None and e.response.status_code == 401:
                return None, True
            logger.warning(e)
            return None, False
        except requests.RequestException as e:
            logger.warning(e)
            return None, False
        if not r.text.strip():
            return None, False
        try:
            art = r.json().get("article")
        except ValueError:
            return None, False
        # Note: fc2ppvdb sets `art["not_found"] = 1` on records whose original
        # FC2 sale page is gone, but the indexed metadata is still real and
        # usable. Don't filter on that flag — only require a non-empty title.
        title = html.unescape((art or {}).get("title") or "").strip()
        if not title:
            return None, False
        return (
            ScrapeResult(
                product_id=self.search_id,
                title=title,
                date=art.get("release_date") or None,
                source="fc2ppvdb.com",
            ),
            False,
        )

    def _fc2ppvdb_login(self) -> bool:
        """POST credentials to fc2ppvdb's /login. On success, persist the
        fresh cookies to profile/cookies.json and flip the class flag."""
        config = utils.get_config()
        if not (config.fc2ppvdb_user and config.fc2ppvdb_pass):
            logger.warning(
                "fc2ppvdb credentials not configured (run `rina set fc2ppvdb`)."
            )
            return False
        try:
            # Get the CSRF token from /login.
            r = network.request("https://fc2ppvdb.com/login")
            r.raise_for_status()
            tree = html_fromstring(r.content, base_url=r.url)
            token = tree.xpath('string(//input[@name="_token"]/@value)')
            if not token:
                logger.warning("fc2ppvdb: no CSRF token on /login")
                return False
            # POST credentials.
            r = network.request(
                "https://fc2ppvdb.com/login",
                method="POST",
                data={
                    "_token": token,
                    "email": config.fc2ppvdb_user,
                    "password": config.fc2ppvdb_pass,
                },
            )
            r.raise_for_status()
            if "/login" in r.url:
                logger.warning("fc2ppvdb: login rejected (bad credentials?)")
                return False
        except requests.RequestException as e:
            logger.warning("fc2ppvdb login error: %s", e)
            return False

        FC2Scraper._fc2ppvdb_authed = True
        # Only persist the session cookie. XSRF-TOKEN is Laravel's CSRF
        # cookie — regenerated on every response and not consulted by the
        # paths we use (we send the CSRF via the meta-tag X-CSRF-TOKEN
        # header, not via X-XSRF-TOKEN).
        network.save_cookies("fc2ppvdb.com", names=("fc2ppvdb_session",))
        logger.info("fc2ppvdb: logged in, cookies persisted.")
        return True

    def _javbus(self):
        pass


class HeydougaScraper(Scraper):
    uncensored = True
    source = "heydouga.com"
    regex = r"heydouga[^0-9]*(?P<h1>[0-9]{4})[^0-9]+(?P<heydou>[0-9]{3,6})"

    def _search(self, url: str = None):
        if not url:
            m1, m2 = self.match.group("h1", "heydou")
            self.search_id = f"heydouga-{m1}-{m2}"
            url = f"https://www.heydouga.com/moviepages/{m1}/{m2}/"

        tree = get_tree(url)
        if tree is None:
            return

        title = tree.findtext(".//title").rpartition(" - ")
        date = xpath(
            'string(.//div[@id="movie-info"]'
            '//span[contains(., "配信日")]'
            '/following-sibling::span[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            product_id=self.search_id,
            title=title[0] or title[2],
            date=date,
            source=self.source,
        )


class MadonnaScraper(Scraper):
    uncensored = False
    source = "madonna-av.com"
    regex = r"(?P<md1>ju(?:fd|sd|ms|vr|[cxylqr])|roe|oba|ure|achj|mdon|mdne|mrec)-?(?P<madonna>[0-9]{3})"

    def _search(self):
        prefix = self.match["md1"].upper()
        num = self.match["madonna"]
        self.search_id = f"{prefix}-{num}"

        tree = get_tree(f"https://madonna-av.com/works/detail/{prefix}{num}")
        if tree is None:
            return

        product_id = date = None
        for th in xpath('.//div[@class="p-workPage__table"]//div[@class="th"]')(tree):
            label = th.text_content().strip()
            item = th.getparent()
            if label == "品番":
                p = item.find(".//p")
                if p is not None:
                    pid = re.sub(r"^DVD", "", p.text_content().strip())
                    product_id = re.sub(r"(?<=[A-Z])(?=\d)", "-", pid)
            elif label == "発売日":
                date = item.text_content()
                if product_id:
                    break

        # Title from first <h2> (robust against proxy stripping <title>)
        h2 = tree.find(".//h2")
        title = h2.text_content().strip() if h2 is not None else ""

        return ScrapeResult(
            product_id=product_id,
            title=title,
            date=date,
            source=self.source,
        )


class AV9898Scraper(HeydougaScraper):
    regex = r"av9898[^0-9]+(?P<av98>[0-9]{3,})"

    def _search(self):
        uid = self.match["av98"]
        self.search_id = f"AV9898-{uid}"
        return super()._search(
            f"https://av9898.heydouga.com/monthly/av9898/moviepages/{uid}/"
        )


# Site closed (サイト閉鎖)
# class HonnamatvScraper(HeydougaScraper):
#     regex = r"honnamatv[^0-9]*(?P<honna>[0-9]{3,})"

#     def _search(self):
#         uid = self.match["honna"]
#         self.search_id = f"honnamatv-{uid}"
#         return super()._search(
#             f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{uid}/"
#         )


class X1XScraper(Scraper):
    uncensored = True
    source = "x1x.com"
    regex = r"x1x(?:\.com)?[\s-]+(?P<x1x>[0-9]{6})"

    def _search(self):
        uid = self.match["x1x"]
        self.search_id = f"x1x-{uid}"

        tree = get_tree(f"http://www.x1x.com/title/{uid}")
        if tree is None:
            tree = get_tree(f"http://www.x1x.com/ppv/title/{uid}")
            if tree is None:
                return

        tree = tree.find('.//div[@id="main_content"]')
        try:
            date = xpath(
                'string(.//div[@class="movie_data_rt"]'
                '//dt[contains(., "配信日")]'
                '/following-sibling::dd[contains(., "20")])'
            )(tree)
        except TypeError as e:
            self.error(e)
        else:
            return ScrapeResult(
                product_id=self.search_id,
                title="".join(xpath("h2[1]/text()")(tree)),
                date=date,
                source=self.source,
            )


# Site closed
# class SMMiracleScraper(Scraper):
#     uncensored = True
#     source = "sm-miracle.com"
#     regex = r"sm[\s-]*miracle(?:[\s-]+no)?[\s.-]+e?(?P<sm>[0-9]{4})"

#     def _search(self):
#         uid = "e" + self.match["sm"]
#         self.search_id = f"sm-miracle-{uid}"

#         try:
#             data = get(f"https://sm-miracle.com/movie/{uid}.dat")
#             data.raise_for_status()
#         except requests.HTTPError as e:
#             logger.debug(e)
#             return
#         except requests.RequestException as e:
#             logger.warning(e)
#             return

#         return ScrapeResult(
#             product_id=self.search_id,
#             title=re.search(
#                 r'[{,]\s*title\s*:\s*(?P<q>[\'"])(?P<title>.+?)(?P=q)\s*[,}]',
#                 data.content.decode(errors="ignore"),
#             )["title"],
#             source=self.source,
#         )


class H4610Scraper(Scraper):
    uncensored = True
    regex = r"(?P<h41>h4610|[ch]0930)\W+(?P<h4610>[a-z]+[0-9]+)"

    def _search(self):
        m1, m2 = self.match.group("h41", "h4610")
        self.search_id = f"{m1.upper()}-{m2}"

        tree = get_tree(f"https://www.{m1}.com/moviepages/{m2}/")
        if tree is None:
            return

        title = tree.findtext(
            './/div[@id="moviePlay"]//div[@class="moviePlay_title"]/h1/span'
        )
        try:
            date = _load_json_ld(tree)["dateCreated"]
        except (TypeError, ValueError, KeyError) as e:
            date = xpath(
                'string(.//div[@id="movieInfo"]//section'
                '//dt[contains(., "公開日")]'
                '/following-sibling::dd[contains(., "20")])'
            )(tree)
            if isinstance(e, (ValueError, KeyError)):
                self.warning(e)

        return ScrapeResult(
            product_id=self.search_id,
            title=title,
            date=date,
            source=f"{m1}.com",
        )


class Kin8Scraper(Scraper):
    uncensored = True
    source = "kin8tengoku.com"
    regex = r"kin8(?:tengoku)?[^0-9]*(?P<kin8>[0-9]{4})"

    _re_movie = (
        r'"movie_id":"(?P<id>\d+)".*?"name_utf8":"(?P<title>[^"]+)"'
        r'.*?"ecp_start_date":"\$D(?P<date>\d{4}-\d{2}-\d{2})'
    )

    def _search(self):
        uid = self.match["kin8"]
        self.search_id = f"kin8-{uid}"

        try:
            response = network.request(f"https://www.kin8tengoku.com/movie/{uid}")
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.debug(e)
            return
        except requests.RequestException as e:
            logger.warning(e)
            return

        m = re.search(self._re_movie, response.content.decode())
        if not m:
            return

        return ScrapeResult(
            product_id=self.search_id,
            title=m["title"],
            date=m["date"],
            source=self.source,
        )


class GirlsDeltaScraper(Scraper):
    uncensored = True
    source = "girlsdelta.com"
    regex = r"girls[\s-]?delta[^0-9]*(?P<gd>[0-9]{3,4})"

    def _search(self):
        uid = self.match["gd"]
        self.search_id = f"GirlsDelta-{uid}"

        tree = get_tree(f"https://girlsdelta.com/product/{uid}")
        if tree is None or "/product/" not in tree.base_url:
            return

        date = xpath(
            'string(.//div[@class="product-detail"]'
            '//li/*[contains(text(), "公開日")]'
            '/following-sibling::*/text()[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            product_id=self.search_id,
            title=xpath(
                'string(.//div[@class="product-detail"]'
                '//li/*[contains(text(), "モデル名")]'
                "/following-sibling::*)"
            )(tree),
            date=date,
            source=self.source,
        )


class UncensoredScraper(Scraper):
    uncensored = True
    regex = (
        r"((?:gs|jiro|ka|kosatsu|mldo|ot|red|sg|sky|sr|tr|wl)[0-9]{3})",
        r"((?:(?:ham|liv)esamurai|it|jpgc|jup|kb?|lb|ma|n|pf|pp|sp|tar|wald)[0-2][0-9]{3})",
        r"((?:bouga|crazyasia|eyu|gedo|nukimax|peworld|shi(?:kai|ma|routozanmai)|ubt)[0-9]{2,8})",
        r"(xxx)[\s-]*(av)[^0-9]*([0-9]{4,5})",
        r"(th101)[\s-]*([0-9]{3})[\s-]([0-9]{6})",
        r"(mkb?d)[\s-]?(s?[0-9]{2,4})",
        r"(bd)[\s-]?([gm][0-9]{2,4})",
        r"(roselip)[\s-]*([0-9]{4})",
        r"([a-z]{1,4}(?:3d2?|2d|2m)+[a-z]{1,4}|r18|t28)[\s-]*([0-9]{2,6})",
    )

    def _search(self):
        self.search_id = "-".join(filter(None, self.match.groups()))


class OneKGiriScraper(Scraper):
    uncensored = True
    regex = rf"((?:{RE_Y})(?:{RE_M})(?:{RE_D}))[\s-]+([a-z]{{3,8}})(?:-(?P<kg>[a-z]{{3,6}}))?"

    def _search(self):
        m = self.match
        i = m.lastindex
        self.search_id = f"{m[i-2]}-{m[i-1]}_{m[i]}"


class CensoredScraper(Scraper):
    uncensored = False
    regex = r"(t[23]8)-(?P<cen>[0-9]{2,4})"

    def _search(self):
        m = self.match
        self.search_id = f"{m[m.lastindex-1]}-{m['cen']}"


class MGSScraper(Scraper):
    # This regex is compiled as is and matched with finditer. <hhb> matches
    # empty string so it does not consume the sequence number.
    regex = r"\b(?:[0-9]{,2}|(?P<num>[0-9]{3,5}))(?P<pre>[a-z]{2,9})-?(?=0{0,7}[1-9])(?P<sfx>[0-9]{2,8})(?:[a-d]?|(?P<hhb>)[hm]hb[0-9]{,2})\b"
    mgs_get = None

    @classmethod
    def _load_mgs(cls, filename: str = "mgs.json"):
        with open(utils.join_root(filename), "r", encoding="utf-8") as f:
            mgs = json.load(f)
        assert mgs, f"Empty MGS data: '{filename}'"
        logger.info("Load %s MGS entries from '%s'", len(mgs), filename)
        cls.mgs_get = mgs.get

    def _search(self):
        num, pre, sfx = self.match.group("num", "pre", "sfx")

        if len(sfx) > 3:
            sfx = sfx.lstrip("0").zfill(3)  # 00079 -> 079
        self.search_id = f"{pre.upper()}-{sfx}"

        try:
            nums = self.mgs_get(pre)
        except TypeError:
            self._load_mgs()
            nums = self.mgs_get(pre)

        if num and self.match["hhb"] is None:
            nums = (num, *(i for i in nums if num != i)) if nums else (num,)
        elif not nums:
            return

        xp = xpath(
            'string(.//table/tr/th[contains(., $title)]/following-sibling::td[contains(., "20")])'
        )
        for num in nums:
            tree = get_tree(
                f"https://www.mgstage.com/product/product_detail/{num}{self.search_id}/"
            )
            if tree is None or self.search_id not in tree.base_url:
                continue

            tree = tree.find(
                './/article[@id="center_column"]/div[@class="common_detail_cover"]'
            )
            try:
                title = re.sub(
                    r"^(\s*【.*?】)+|【[^】]*映像付】|\+\d+分\b",
                    "",
                    tree.findtext("h1"),
                )
            except (AttributeError, TypeError) as e:
                self.error(e)
                return

            date = xp(tree, title="発売日") or xp(tree, title="開始日")
            return ScrapeResult(
                product_id=self.search_id,
                title=title,
                date=date,
                source="mgstage.com",
            )


class DateSearcher:
    """Search for date in text."""

    source = "File Name"
    regex = None
    fmt = {}

    @classmethod
    def _init_regex(cls):
        template = [
            r"(?P<{0}>{{{0[0]}}}\s*?(?P<s{0}>[\s.-])\s*{{{0[1]}}}\s*?(?P=s{0})\s*{{{0[2]}}})".format(
                f
            )
            for f in (
                "ymd",  # (20)19.03.15
                "dmy",  # 23.02.(20)19
                "mdy",  # 10.15.(20)19
            )
        ]
        template.extend(
            r"(?P<{0}>{{{0[0]}}}\s*([.,-]?)\s*{{{0[1]}}}\s*?[\s.,-]{1}\s*{{{0[2]}}})".format(
                f, r
            )
            for f, r in (
                ("dby", "?"),  # 23Jun(20)14
                ("dBy", "?"),  # 19June(20)14
                ("bdy", ""),  # Dec.23.(20)14
                ("Bdy", ""),  # June.19.(20)14
                ("ybd", "?"),  # (20)12Feb3
                ("yBd", "?"),  # (20)12March3
            )
        )
        template.append(r"(?P<Ymd>{Y}(){mm}{dd})")  # 20170102
        fmt = {
            "y": rf"(?:20)?({RE_Y})",
            "Y": rf"(20(?:{RE_Y}))",
            "m": r"(1[0-2]|0?[1-9])",
            "mm": rf"({RE_M})",
            "d": r"([12][0-9]|3[01]|0?[1-9])",
            "dd": rf"({RE_D})",
            "b": r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            "B": r"(january|february|march|april|may|june|july|august|september|october|november|december)",
        }
        cls.regex = re.compile(
            r"\b(?:{})\b".format("|".join(t.format_map(fmt) for t in template)), re.I
        )

    @classmethod
    def search(cls, text: str, return_obj=None):
        """Search for date in text and return timestamp or a return_obj with
        date and source."""
        try:
            m = cls.regex.search(text)
        except AttributeError:
            cls._init_regex()
            m = cls.regex.search(text)
        if not m:
            return

        try:
            fmt = cls.fmt[m.lastgroup]
        except KeyError:
            fmt = cls.fmt[m.lastgroup] = " ".join("%" + f for f in m.lastgroup)

        i = m.lastindex + 1
        try:
            date = strptime(" ".join(m.group(i, i + 2, i + 3)), fmt)
        except ValueError as e:
            logger.error("Failed to parse date: %s", e)
            return

        if return_obj is None:
            return date
        return return_obj(date=date, source=cls.source)


def _load_json_ld(tree: network.HtmlElement):
    """Loads JSON-LD from tree.

    Raise TypeError if there is no json-ld, ValueError if parsing failed.
    """
    data = re.sub(
        r"[\t\n\r\f\v]", " ", tree.findtext('.//script[@type="application/ld+json"]')
    )
    try:
        return json.loads(data)
    except ValueError:
        dumps = json.dumps
        data = re.sub(
            r'(?<=[{,])\s*("[^"]+")\s*:\s*"(.*?)"\s*(?=[,}])',
            lambda m: f"{m[1]}:{dumps(m[2], ensure_ascii=False)}",
            data,
        )
        return json.loads(data)


def _combine_regex(*args: Scraper) -> re.Pattern:
    """Combine one or more scraper regexes to form a single pattern."""
    item = []
    for scraper in args:
        regex = scraper.regex
        assert regex, f"empty regex attribute: {scraper}"
        if isinstance(regex, str):
            item.append(regex)
        else:
            item.extend(regex)

    result = "|".join(item)
    if len(item) == 1:
        result = rf"\b{result}\b"
    else:
        result = rf"\b(?:{result})\b"

    assert "_" not in result, f'"_" in regex: {result}'
    logger.debug("Combined regex: '%s'", result)
    return re.compile(result)


_maker_re = _general_re = None


def _sanitize(string: str) -> str:
    """Sanitize string for regex matching."""
    return re.sub(_trash_re, " ", re.sub(r"[-_+]+", "-", string.lower()))


def scrape(string: str) -> ScrapeResult | None:
    """Scrape JAV info from string"""
    global _maker_re, _general_re

    string = _sanitize(string)
    try:
        m = _maker_re.search(string)
    except AttributeError:
        _maker_re = _combine_regex(*_scraper_map.values())
        m = _maker_re.search(string)
    if m:
        result = _scraper_map[m.lastgroup](m).search()
        if result:
            return result
    else:
        try:
            it = _general_re.finditer(string)
        except AttributeError:
            _general_re = re.compile(MGSScraper.regex)
            it = _general_re.finditer(string)
        for m in it:
            result = MGSScraper(m).search()
            if result:
                return result

    return DateSearcher.search(string, ScrapeResult)


_scraper_map = {
    "studio": StudioScraper,
    "heyzo": HeyzoScraper,
    "fc2": FC2Scraper,
    "heydou": HeydougaScraper,
    "madonna": MadonnaScraper,
    "av98": AV9898Scraper,
    "x1x": X1XScraper,
    # "sm": SMMiracleScraper,
    "h4610": H4610Scraper,
    # "honna": HonnamatvScraper,
    "kin8": Kin8Scraper,
    "gd": GirlsDeltaScraper,
    None: UncensoredScraper,
    "kg": OneKGiriScraper,
    "cen": CensoredScraper,
}
