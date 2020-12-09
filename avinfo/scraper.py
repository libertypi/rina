import re
from dataclasses import dataclass
from random import choice as random_choice
from urllib.parse import urljoin

from requests.cookies import create_cookie

from avinfo import common
from avinfo.common import (
    get_tree,
    re_compile,
    re_search,
    re_sub,
    session,
    str_to_epoch,
    text_to_epoch,
    xpath,
)

__all__ = "from_string"

session.cookies.set_cookie(create_cookie(domain="www.javbus.com", name="existmag", value="all"))
_subspace = re_compile(r"\s+").sub


@dataclass
class ScrapeResult:
    productId: str = None
    title: str = None
    publishDate: float = None
    titleSource: str = None
    dateSource: str = None


class Scraper:
    """Base class for scrapers."""

    keyword: str
    source: str
    uncensored_only: bool = False
    _mask = None

    def __init__(self, string: str, match: re.Match) -> None:
        self.string = string
        self.match = match

    def search(self):

        result: ScrapeResult = self._query() or self._javbus() or self._javdb()
        if not result:
            return

        try:
            productId = _subspace("", result.productId)
            title = _subspace(" ", result.title).strip()
        except TypeError:
            return
        if productId and title:
            result.title = title
            result.titleSource = self.source
        else:
            return

        result.productId = self._process_product_id(productId)

        if result.publishDate:
            result.dateSource = self.source

        return result

    @staticmethod
    def _query():
        pass

    def _javbus(self):

        mask = self._get_keyword_mask()

        for base in ("uncensored/",) if self.uncensored_only else ("uncensored/", ""):
            tree = get_tree(f"https://www.javbus.com/{base}search/{self.keyword}", decoder="lxml")
            if tree is None:
                continue

            for span in tree.iterfind('.//div[@id="waterfall"]//a[@class="movie-box"]//span'):
                productId = span.findtext("date[1]")

                if productId and mask(productId):
                    title = span.text
                    if title.startswith("【"):
                        title = re_sub(r"^【(お得|特価)】\s*", "", title)

                    self.source = "javbus.com"
                    return ScrapeResult(
                        productId=productId,
                        title=title,
                        publishDate=text_to_epoch(span.findtext("date[2]")),
                    )

    def _javdb(self):

        try:
            base = random_choice(Scraper._javdb_url)
        except AttributeError:
            base = "https://javdb.com/search"
            tree = get_tree(base, params={"q": self.keyword})
            if tree is None:
                return

            pool = {base}
            pool.update(
                urljoin(s, "search")
                for s in tree.xpath('//nav[@class="sub-header"]/div[contains(text(), "最新域名")]//a/@href')
            )
            Scraper._javdb_url = tuple(pool)
        else:
            tree = get_tree(base, params={"q": self.keyword})
            if tree is None or "/search" not in tree.base_url:
                return

        mask = self._get_keyword_mask()
        for a in tree.iterfind('.//div[@id="videos"]//a[@class="box"]'):
            productId = a.findtext('div[@class="uid"]')
            if productId and mask(productId):
                title = a.findtext('div[@class="video-title"]')
                self.source = "javdb.com"
                return ScrapeResult(
                    productId=productId,
                    title=title,
                    publishDate=text_to_epoch(a.findtext('div[@class="meta"]')),
                )

    def _get_keyword_mask(self):
        if not self._mask:
            self._mask = re_compile(
                r"\s*{}\s*".format(re_sub(r"[\s_-]", r"[\\s_-]?", self.keyword)),
                flags=re.IGNORECASE,
            ).fullmatch
        return self._mask

    def _process_product_id(self, productId: str):

        m = re_search(
            r"^\s?((f?hd|sd|cd|dvd|vol)\s?|(216|108|72|48)0p\s)*(?P<sfx>[0-9]{1,2}|[a-d])\b",
            re_sub(r"[\s()\[\].-]+", " ", self.string[self.match.end() :]),
        )
        if m:
            suffix = m["sfx"]
            if suffix in "abcd":
                suffix = suffix.upper()
            return f"{productId}-{suffix}"
        return productId


class StudioMatcher(Scraper):

    uncensored_only = True
    regex = r"(?P<studio>(?P<s1>{m}{d}{y}|(?P<symd>{y}{m}{d})){tail})".format_map(
        {
            "y": r"[0-2][0-9]",
            "m": r"(?:1[0-2]|0[1-9])",
            "d": r"(?:3[01]|[12][0-9]|0[1-9])",
            "tail": r"-(?P<s2>[0-9]{2,4})(?:-(?P<s3>0[0-9]))?",
        }
    )
    studio_re = re_compile(
        r"""\b(?:
        (carib)(?:bean|com)*    # 112220-001-carib
        (pr)?|                  # 101515_391-caribpr
        (1pon)(?:do)?|          # 110411_209-1pon
        (10mu)(?:sume)?|        # 122812_01-10mu
        (paco)(?:pacomama)?|    # 120618_394-paco
        (mura)(?:mura)?|        # 010216_333-mura
        (mesubuta)              # 160122_1020_01-mesubuta
        )\b""",
        flags=re.VERBOSE,
    ).search
    datefmt = "%m%d%y"

    def __init__(self, string: str, match: re.Match) -> None:

        super().__init__(string, match)

        c = "_"
        keyword = match.group("s1", "s2")

        m = self.studio_match = self.studio_re(string)
        if m:
            s = self.studio = m[m.lastindex]
            if s == "carib":
                c = "-"
                self._query = self._carib
                self.source = "caribbeancom.com"
                self.url = "https://www.caribbeancom.com"
            elif s == "pr":
                self.studio = "caribpr"
                self._query = self._carib
                self.source = "caribbeancompr.com"
                self.url = "https://www.caribbeancompr.com"
            elif s == "1pon":
                self._query = self._1pon_10mu
                self.source = "1pondo.tv"
                self.url = "https://www.1pondo.tv"
            elif s == "10mu":
                self._query = self._1pon_10mu
                self.source = "10musume.com"
                self.url = "https://www.10musume.com"
            elif s == "paco":
                self._query = self._paco
                self.source = "pacopacomama.com"
            elif s == "mesubuta":
                if match["s3"]:
                    keyword = match.group("s1", "s2", "s3")
                self.datefmt = "%y%m%d"

        elif match["s3"] and match["symd"]:
            keyword = match.group("s1", "s2", "s3")
            self.datefmt = "%y%m%d"

        self.keyword = c.join(keyword)

    def search(self):
        result = super().search()

        if result and (not result.publishDate or result.dateSource.startswith("jav")):
            try:
                result.publishDate = str_to_epoch(self.match["s1"], self.datefmt, regex=None)
            except ValueError:
                pass
            else:
                result.dateSource = "product id"
        return result

    def _javbus(self):
        result = super()._javbus()

        if not result and not self.studio_match:
            keyword = self.keyword
            self.keyword = keyword.replace("_", "-")

            result = super()._javbus()
            if not result:
                self.keyword = keyword

        return result

    def _carib(self):

        tree = get_tree(f"{self.url}/moviepages/{self.keyword}/", decoder="euc-jp")
        try:
            tree = tree.find('.//div[@id="moviepages"]')
            title = tree.findtext('.//div[@class="heading"]/h1')
        except AttributeError:
            return

        if title:
            date = xpath(
                '//li[@class="movie-spec"]'
                '/span[contains(text(), "配信日") or contains(text(), "販売日")]'
                "/following-sibling::span/text()"
            )(tree)
            return ScrapeResult(
                productId=self.keyword,
                title=title,
                publishDate=text_to_epoch(date[0]) if date else None,
            )

    def _1pon_10mu(self):
        try:
            json = session.get(f"{self.url}/dyn/phpauto/movie_details/movie_id/{self.keyword}.json")
            if json.ok:
                json = json.json()
                return ScrapeResult(
                    productId=json["MovieID"],
                    title=json["Title"],
                    publishDate=text_to_epoch(json["Release"]),
                )
        except (common.RequestException, ValueError, KeyError):
            pass

    def _paco(self):

        tree = get_tree(f"https://www.pacopacomama.com/moviepages/{self.keyword}/")
        try:
            tree = tree.find('.//div[@id="main"]')
            title = tree.findtext("h1")
        except (AttributeError, KeyError):
            return

        if title:
            date = tree.findtext('.//div[@class="detail-info"]//*[@class="date"]')
            return ScrapeResult(
                productId=self.keyword,
                title=title,
                publishDate=text_to_epoch(date),
            )

    def _process_product_id(self, productId: str):

        if not self.studio_match:
            return productId

        result = f"{self.keyword}-{self.studio}"

        i = max(self.match.end(), self.studio_match.end())
        other = re_search(
            r"^\s?(([0-9]|(high|mid|low|whole|hd|sd|psp)[0-9]*|(216|108|72|48)0p)\b\s?)+",
            re_sub(r"[\s()\[\].-]+", " ", self.string[i:]),
        )
        if other:
            other = other[0].split()
            other.insert(0, result)
            return "-".join(other)

        return result


class Heyzo(Scraper):

    uncensored_only = True
    source = "heyzo.com"
    regex = r"heyzo[^0-9]*(?P<heyzo>[0-9]{4})"

    def _query(self):
        uid = self.match["heyzo"]
        self.keyword = f"HEYZO-{uid}"

        tree = get_tree(f"https://www.heyzo.com/moviepages/{uid}/", decoder="lxml")
        try:
            title = tree.findtext('.//div[@id="wrapper"]//div[@id="movie"]/h1')
            if not title:
                return
        except AttributeError:
            return

        date = tree.find('.//div[@id="movie"]//table[@class="movieInfo"]//*[@class="table-release-day"]')
        if date is not None:
            date = text_to_epoch(date.text_content())

        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=date,
        )


class FC2(Scraper):

    source = "fc2.com"
    regex = r"fc2(?:[\s-]*ppv)?[\s-]+(?P<fc2>[0-9]{2,10})"

    def _query(self):

        uid = self.match["fc2"]
        self.keyword = f"FC2-{uid}"

        title = date = None

        tree = get_tree(f"https://adult.contents.fc2.com/article/{uid}/")
        try:
            tree = tree.find('.//section[@id="top"]//section[@class="items_article_header"]')
            title = tree.findtext('.//div[@class="items_article_headerInfo"]/h3')
        except AttributeError:
            pass

        if title:
            date = tree.findtext('.//div[@class="items_article_Releasedate"]/p')
            date = text_to_epoch(date)

        else:
            tree = get_tree(f"http://video.fc2.com/a/search/video/?keyword={uid}")
            try:
                tree = tree.find('.//div[@id="pjx-search"]//ul/li[1]//a[@title]')
                title = tree.text
            except AttributeError:
                return
            try:
                date = re_search(r"(?<=/)20[0-9]{6}", tree.get("href"))
                date = str_to_epoch(date[0], "%Y%m%d")
            except (TypeError, ValueError):
                pass

        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=date,
        )


class Heydouga(Scraper):

    uncensored_only = True
    source = "heydouga.com"
    regex = (
        r"hey(?:douga)?(?a:\W*)(?P<h1>4[0-9]{3})[^0-9]+(?P<heydouga>[0-9]{3,6})",
        r"honnamatv[^0-9]*(?P<honnamatv>[0-9]{3,})",
    )

    def _query(self):
        m = self.match

        if m["heydouga"]:
            self.keyword = m.expand(r"heydouga-\g<h1>-\g<heydouga>")
            url = m.expand(r"https://www.heydouga.com/moviepages/\g<h1>/\g<heydouga>/")
        else:
            self.keyword = f"honnamatv-{m['honnamatv']}"
            url = f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{m['honnamatv']}/"

        tree = get_tree(url, decoder="utf-8")
        try:
            title = tree.findtext(".//title").rpartition(" - ")[0]
        except AttributeError:
            return

        date = xpath('//div[@id="movie-info"]//span[contains(text(),"配信日")]/following-sibling::span/text()')(tree)
        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=text_to_epoch(date[0]) if date else None,
        )


class X1X(Scraper):

    uncensored_only = True
    source = "x1x.com"
    regex = r"x1x[\s-]+(?P<x1x>[0-9]{6})"

    def _query(self):

        uid = self.match["x1x"]
        self.keyword = f"x1x-{uid}"

        tree = get_tree(f"http://www.x1x.com/title/{uid}")
        try:
            title = tree.findtext(".//title")
        except AttributeError:
            return

        if title:
            date = xpath(
                '//div[@id="main_content"]//div[@class="movie_data_rt"]'
                '//dt[contains(text(), "配信日")]/following-sibling::dd[1]/text()'
            )(tree)
            return ScrapeResult(
                productId=self.keyword,
                title=title,
                publishDate=text_to_epoch(date[0]) if date else None,
            )


class SM_Miracle(Scraper):

    uncensored_only = True
    source = "sm-miracle.com"
    regex = r"sm[\s-]*miracle(?:[\s-]+no)?[\s.-]+e?(?P<sm>[0-9]{4})"

    def _query(self):

        self.keyword = "e" + self.match["sm"]
        try:
            response = session.get(f"http://sm-miracle.com/movie/{self.keyword}.dat")
            response.raise_for_status()
        except common.RequestException:
            return

        response.encoding = "utf-8"
        try:
            return ScrapeResult(
                productId=f"sm-miracle-{self.keyword}",
                title=re_search(r'(?<=[\n,])\s*title:\W*([^\n\'"]+)', response.text)[1],
            )
        except TypeError:
            pass


class H4610(Scraper):

    uncensored_only = True
    regex = r"(?P<h41>h4610|[ch]0930)\W+(?P<h4610>[a-z]+[0-9]+)"

    def _query(self):

        m1, m2 = self.match.group("h41", "h4610")
        self.keyword = f"{m1}-{m2}"
        self.source = f"{m1}.com"

        tree = get_tree(f"https://www.{m1}.com/moviepages/{m2}/")
        if not tree:
            return

        title = tree.findtext('.//div[@id="moviePlay"]//div[@class="moviePlay_title"]/h1/span')
        if not title:
            return

        date = xpath('//div[@id="movieInfo"]//section//dt[contains(text(),"公開日")]/following-sibling::dd/text()')(tree)
        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=text_to_epoch(date[0]) if date else None,
        )


class UncensoredMatcher(Scraper):

    uncensored_only = True
    regex = (
        r"((?:n|k|kb|jpgc|shiroutozanmai|hamesamurai)[0-2][0-9]{3}|(?:bouga|ka|sr|tr|sky)[0-9]{3,4})",
        r"(kin8(?:tengoku)?|xxx[\s-]?av|[a-z]{1,4}(?:3d2?|2d|2m)+[a-z]{1,4})[\s-]*([0-9]{2,6})",
        r"(mkbd|bd)[\s-]?([sm]?[0-9]{2,4})",
        r"(th101)[\s-]([0-9]{3})[\s-]([0-9]{6})",
    )

    def __init__(self, string: str, match: re.Match) -> None:
        super().__init__(string, match)
        self.keyword = "-".join(filter(None, match.groups()))


class ThousandGirl(Scraper):

    uncensored_only = True
    regex = r"(?P<kg>(?P<kg1>[12][0-9](?:1[0-2]|0[1-9])(?:3[01]|[12][0-9]|0[1-9]))[\s-]?(?P<kg2>[a-z]{3,8})(?:-(?P<kg3>[a-z]{3,6}))?)"

    def __init__(self, string: str, match: re.Match) -> None:
        super().__init__(string, match)
        if match["kg3"]:
            self.keyword = match.expand(r"\g<kg1>-\g<kg2>_\g<kg3>")
        else:
            self.keyword = match.expand(r"\g<kg1>-\g<kg2>")


class PatternSearcher(Scraper):

    regex = r"[0-9]{,3}(?P<p1>[a-z]{2,8})-?(?P<z>0)*(?P<p2>(?(z)[0-9]{3,6}|[0-9]{2,6}))(?:hhb[0-9]?)?"

    def __init__(self, string: str, match: re.Match) -> None:
        super().__init__(string, match)
        self.keyword = match.expand(r"\g<p1>-\g<p2>")


class DateSearcher:

    source = "file name"

    def _init_regex():
        fmt = {
            "sep": r"[\s,.-]*",
            "sepF": r"[\s,.-]+",
            "year": r"(?:20)?([12][0-9])",
            "yearF": r"(20[12][0-9])",
            "mon": r"(1[0-2]|0[1-9])",
            "day": r"(3[01]|[12][0-9]|0?[1-9])",
            "dayF": r"(3[01]|[12][0-9]|0[1-9])",
            "b": r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
        }
        regex = tuple(
            p.format_map(fmt)
            for p in (
                r"(?P<dby>{day}(?P<s1>{sep}){b}(?P=s1){year})",  # 23.Jun.(20)14
                r"(?P<bdy>{b}(?P<s2>{sep}){day}(?P=s2){year})",  # Dec.23.(20)14
                r"(?P<ymd>{year}(?P<s3>{sepF}){mon}(?P=s3){dayF})",  # (20)19.03.15
                r"(?P<dmy>{dayF}(?P<s4>{sepF}){mon}(?P=s4){year})",  # 23.02.(20)19
                r"(?P<Ymd>{yearF}(?P<s5>{sep}){mon}(?P=s5){dayF})",  # 20170102
            )
        )
        fmt.clear()
        return regex, fmt

    regex, fmt = _init_regex()

    @classmethod
    def search(cls, match: re.Match):

        i = match.lastindex + 1

        try:
            fmt = cls.fmt[match.lastgroup]
        except KeyError:
            fmt = cls.fmt[match.lastgroup] = " ".join("%" + f for f in match.lastgroup)

        return ScrapeResult(
            publishDate=str_to_epoch(
                string=" ".join(match.group(i, i + 2, i + 3)),
                fmt=fmt,
                regex=None,
            ),
            dateSource=cls.source,
        )


def _combine_scraper_regex(*args: Scraper, b=r"\b") -> re.Pattern:
    """Combine multiple scraper regexes to a single pattern, without duplicates."""

    item = {}
    for scraper in args:
        if isinstance(scraper.regex, str):
            item[scraper.regex] = None
        else:
            for k in scraper.regex:
                item[k] = None

    result = "|".join(item)
    assert "_" not in result, f'"_" in regex: {result}'

    if len(item) == 1:
        result = f"{b}{result}{b}"
    else:
        result = f"{b}(?:{result}){b}"

    return re_compile(result)


_search_map = {
    "studio": StudioMatcher,
    "heyzo": Heyzo,
    "fc2": FC2,
    "heydouga": Heydouga,
    "honnamatv": Heydouga,
    "x1x": X1X,
    "sm": SM_Miracle,
    "h4610": H4610,
    None: UncensoredMatcher,
    "kg": ThousandGirl,
}
_search_re = _combine_scraper_regex(*_search_map.values()).search
_iter_re = _combine_scraper_regex(PatternSearcher).finditer
_date_re = _combine_scraper_regex(DateSearcher).search
_clean_re = re_compile(
    r"""
    \s*\[(?:[a-z0-9.-]+\.[a-z]{2,4}|f?hd)\]\s*|
    (?:[\s\[_-]+|\b)(?:    
    [a-z0-9.-]+\.[a-z]{2,4}@|
    (?:[a-z]+2048|hotavxxx|nyap2p)\.com|
    168x|44x|3xplanet|
    sis001|sexinsex|thz|dioguitar23|
    uncensored|nodrm|fhd|
    tokyo[\s_-]?hot|1000[\s_-]?girl
    )(?:[\s\]_-]+|\b)|
    \s+
    """,
    flags=re.VERBOSE,
).sub


def from_string(string: str):

    string = _clean_re(" ", string.lower()).replace("_", "-")

    match = _search_re(string)
    if match:
        result: ScrapeResult = _search_map[match.lastgroup](string, match).search()
        if result:
            return result

    for match in _iter_re(string):
        result = PatternSearcher(string, match).search()
        if result:
            return result

    match = _date_re(string)
    if match:
        return DateSearcher.search(match)
