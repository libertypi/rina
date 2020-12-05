import re
from dataclasses import dataclass
from random import choice as random_choice
from urllib.parse import urljoin

from avinfo import common
from avinfo.common import get_response_tree, re_compile, re_search, re_sub, str_to_epoch, xp_compile

__all__ = "from_string"


@dataclass
class ScrapeResult:
    productId: str = None
    title: str = None
    publishDate: float = None
    titleSource: str = None
    dateSource: str = None


class Scraper:

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
            productId = result.productId.strip()
            title = re_sub(r"\s+", " ", result.title.strip())
        except AttributeError:
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
            tree = get_response_tree(f"https://www.javbus.com/{base}search/{self.keyword}", decoder="lxml")[1]
            if tree is None:
                continue

            for span in tree.iterfind('.//div[@id="waterfall"]//a[@class="movie-box"]//span'):
                productId = span.findtext("date[1]")

                if productId and mask(productId):
                    title = span.text
                    if not title:
                        continue

                    date = span.findtext("date[2]")
                    self.source = "javbus.com"

                    return ScrapeResult(
                        productId=productId,
                        title=title,
                        publishDate=str_to_epoch(date) if date else None,
                    )

    def _javdb(self):

        try:
            url = random_choice(Scraper._javdb_url)
        except AttributeError:
            url = "https://javdb.com/search"
            tree = get_response_tree(url, params={"q": self.keyword})[1]
            if tree is None:
                return

            pool = {url}
            pool.update(
                urljoin(i, "search")
                for i in tree.xpath('//nav[@class="sub-header"]/div[contains(text(), "最新域名")]//a/@href')
            )
            Scraper._javdb_url = tuple(pool)
        else:
            tree = get_response_tree(url, params={"q": self.keyword})[1]
            if tree is None:
                return

        mask = self._get_keyword_mask()

        for a in tree.iterfind('.//div[@id="videos"]//a[@class="box"]'):
            productId = a.findtext('div[@class="uid"]')
            if productId and mask(productId):

                title = a.findtext('div[@class="video-title"]')
                if not title:
                    continue

                date = a.findtext('div[@class="meta"]')
                self.source = "javdb.com"

                return ScrapeResult(
                    productId=productId,
                    title=title,
                    publishDate=str_to_epoch(date) if date else None,
                )

    def _get_keyword_mask(self):

        mask = self._mask
        if not mask:
            mask = self._mask = re_compile(
                r"\s*{}\s*".format(re_sub(r"[\s_-]", r"[\\s_-]?", self.keyword)),
                flags=re.IGNORECASE,
            ).fullmatch
        return mask

    def _process_product_id(self, productId: str):

        string = re_sub(r"[\s()\[\]._-]+", " ", self.string[self.match.end() :])
        m = re_search(r"^\s?((f?hd|sd|cd|dvd|vol)\s?|(216|108|72|48)0p\s)*(?P<sfx>[0-9]{1,2}|[a-d])\b", string)
        if m:
            suffix = m["sfx"]
            if suffix in "abcd":
                suffix = suffix.upper()
            return f"{productId}-{suffix}"
        return productId


class StudioMatcher(Scraper):

    uncensored_only = True
    studio_list = re_compile(
        r"""\b(?:
        (carib(?:bean|com)*)|   # 112220-001-carib
        (carib(?:bean|com)*pr)| # 101515_391-caribpr
        (1pon(?:do)?)|          # 110411_209-1pon
        (paco(?:pacomama)?)|    # 120618_394-paco
        (10mu(?:sume)?)|        # 122812_01-10mu
        (mura(?:mura)?)|        # 010216_333-mura
        (mesubuta)              # 160122_1020_01-mesubuta
        )\b""",
        flags=re.VERBOSE,
    ).search
    studio_list = (studio_list, "carib", "caribpr", "1pon", "paco", "10mu", "mura", "mesubuta")
    datefmt = "%m%d%y"

    def __init__(self, string: str, match: re.Match) -> None:

        super().__init__(string, match)

        c = "_"
        keyword = match.group("s1", "s2")

        m = self.studio_match = self.studio_list[0](string)
        if m:
            s = self.studio = self.studio_list[m.lastindex]
            if s == "carib":
                c = "-"
                self._query = self._carib
                self.source = "caribbeancom.com"
                self.url = "https://www.caribbeancom.com/moviepages"
            elif s == "caribpr":
                self._query = self._carib
                self.source = "caribbeancompr.com"
                self.url = "https://www.caribbeancompr.com/moviepages"
            elif s == "mesubuta":
                keyword = match.group("s1", "s2", "s3")
                self.datefmt = "%y%m%d"

        self.keyword = c.join(keyword)

    def search(self):
        result = super().search()
        if result:
            try:
                result.publishDate = str_to_epoch(self.match["s1"], self.datefmt, regex=None)
            except ValueError:
                pass
            else:
                result.dateSource = "product id"
        return result

    def _carib(self):

        tree = get_response_tree(f"{self.url}/{self.keyword}/", decoder="euc-jp")[1]
        try:
            title = tree.findtext('.//div[@id="moviepages"]//div[@class="heading"]/h1')
        except AttributeError:
            return
        if title:
            return ScrapeResult(
                productId=self.keyword,
                title=title,
            )

    def _process_product_id(self, productId: str):

        if not self.studio_match:
            return productId

        result = f"{self.keyword}-{self.studio}"

        i = max(self.match.end(), self.studio_match.end())
        string = re_sub(r"[\s()\[\]._-]+", " ", self.string[i:])
        other = re_search(r"^\s?(([0-9]|(high|mid|low|whole|hd|sd|psp)[0-9]*|(216|108|72|48)0p)\b\s?)+", string)
        if other:
            other = other[0].split()
            other.insert(0, result)
            return "-".join(other)

        return result


class Heyzo(Scraper):

    uncensored_only = True
    source = "heyzo.com"

    def _query(self):
        uid = self.match["heyzo"]
        self.keyword = f"HEYZO-{uid}"

        tree = get_response_tree(f"https://www.heyzo.com/moviepages/{uid}/", decoder="lxml")[1]

        try:
            title = tree.findtext('.//div[@id="wrapper"]//div[@id="movie"]/h1')
            if not title:
                return
        except AttributeError:
            return

        date = xp_compile(
            '//*[@id="wrapper"]//*[@id="movie"]//table[@class="movieInfo"]'
            '//td[contains(text(),"公開日")]/following-sibling::td/text()'
        )(tree)
        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=str_to_epoch(date[0]) if date else None,
        )


class Heydouga(Scraper):

    uncensored_only = True
    source = "heydouga.com"

    def _query(self):
        m = self.match

        if m["heydouga"]:
            self.keyword = m.expand(r"heydouga-\g<h1>-\g<h2>")
            url = m.expand(r"https://www.heydouga.com/moviepages/\g<h1>/\g<h2>/")
        else:
            self.keyword = f"honnamatv-{m['honnamatv']}"
            url = f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{m['honnamatv']}/"

        tree = get_response_tree(url, decoder="utf-8")[1]
        try:
            title = tree.findtext(".//title").rpartition(" - ")[0]
        except AttributeError:
            return

        date = xp_compile('//*[@id="movie-info"]//span[contains(text(),"配信日")]/following-sibling::span/text()')(tree)
        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=str_to_epoch(date[0]) if date else None,
        )


class FC2(Scraper):

    source = "fc2.com"

    def _query(self):

        uid = self.match["fc2"]
        self.keyword = f"FC2-{uid}"

        title = date = None

        tree = get_response_tree(f"https://adult.contents.fc2.com/article/{uid}/")[1]
        try:
            tree = tree.find('.//*[@id="top"]//section[@class="items_article_header"]')
            title = tree.findtext('.//div[@class="items_article_headerInfo"]/h3')
        except AttributeError:
            pass

        if title:
            try:
                date = tree.findtext('.//div[@class="items_article_Releasedate"]/p')
                date = re_search(r"\b20[0-9]{2}\W[0-9]{2}\W[0-9]{2}\b", date)
                date = str_to_epoch(date[0])
            except TypeError:
                pass
        else:
            tree = get_response_tree(f"http://video.fc2.com/a/search/video/?keyword={uid}")[1]
            try:
                tree = tree.find('.//*[@id="pjx-search"]//ul/li[1]//a[@title]')
                title = tree.text
            except AttributeError:
                return
            try:
                date = re_search(r"(?<=/)20[0-9]{6}", tree.get("href"))
                date = str_to_epoch(date[0], "%Y%m%d")
            except TypeError:
                pass

        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=date,
        )


class X1X(Scraper):

    uncensored_only = True
    source = "x1x.com"

    def _query(self):

        uid = self.match["x1x"]
        self.keyword = f"x1x-{uid}"

        tree = get_response_tree(f"http://www.x1x.com/title/{uid}")[1]
        try:
            title = tree.find(".//title").text
        except AttributeError:
            return

        date = xp_compile(
            '//div[@id="main_content"]//div[@class="movie_data_rt"]'
            '//dt[contains(text(), "配信日")]/following-sibling::dd[1]/text()'
        )(tree)
        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=str_to_epoch(date[0]) if date else None,
        )


class SM_Miracle(Scraper):

    uncensored_only = True
    source = "sm-miracle.com"

    def _query(self):

        self.keyword = "e" + self.match["sm"]
        try:
            response = common.session.get(f"http://sm-miracle.com/movie/{self.keyword}.dat")
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

    def _query(self):

        m1, m2 = self.match.group("h41", "h42")
        self.keyword = f"{m1}-{m2}"
        self.source = f"{m1}.com"

        tree = get_response_tree(f"https://www.{m1}.com/moviepages/{m2}/")[1]
        try:
            title = tree.findtext('.//*[@id="moviePlay"]//div[@class="moviePlay_title"]/h1/span')
            if not title:
                return
        except AttributeError:
            return

        date = xp_compile('//*[@id="movieInfo"]//section//dt[contains(text(),"公開日")]/following-sibling::dd[1]/text()')(
            tree
        )
        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=str_to_epoch(date[0]) if date else None,
        )


class UncensoredMatcher(Scraper):

    uncensored_only = True

    def __init__(self, string: str, match: re.Match) -> None:
        super().__init__(string, match)
        self.keyword = "-".join(filter(None, match.groups()))


class PrefixSearcher(Scraper):

    regex = r"(?P<p1>[a-z]{2,8})[\s_-]*(?P<z>0)*(?P<p2>(?(z)[0-9]{3,6}|[0-9]{2,6}))(?:hhb[0-9]?)?"

    def __init__(self, string: str, match: re.Match) -> None:
        super().__init__(string, match)
        self.keyword = match.expand(r"\g<p1>-\g<p2>")


class DateSearcher(Scraper):

    __slots__ = ("string", "match")
    source = "file name"
    fmt = {}

    @staticmethod
    def get_regex():
        fmt = {
            "sep1": r"[\s,._-]*",
            "sep2": r"[\s,._-]+",
            "year": r"(?:20)?([12][0-9])",
            "mon": r"(1[0-2]|0[1-9])",
            "day1": r"(3[01]|[12][0-9]|0?[1-9])",
            "day2": r"(3[01]|[12][0-9]|0[1-9])",
            "b": r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
        }
        return (
            p.format_map(fmt)
            for p in (
                r"(?P<dby>{day1}{sep1}{b}{sep1}{year})",  # 23.Jun.(20)14
                r"(?P<bdy>{b}{sep1}{day1}{sep1}{year})",  # Dec.23.(20)14
                r"(?P<ymd>{year}{sep2}{mon}{sep2}{day2})",  # (20)19.03.15
                r"(?P<dmy>{day2}{sep2}{mon}{sep2}{year})",  # 23.02.(20)19
            )
        )

    def search(self):

        m = self.match
        i = m.lastindex + 1

        try:
            fmt = self.fmt[m.lastgroup]
        except KeyError:
            fmt = self.fmt[m.lastgroup] = " ".join("%" + f for f in m.lastgroup)

        return ScrapeResult(
            publishDate=str_to_epoch(
                string=" ".join(m.group(i, i + 1, i + 2)),
                fmt=fmt,
                regex=None,
            ),
            dateSource=self.source,
        )


def _re_combine(reg, begin=r"(?:^|[^a-z0-9])", end=r"(?:[^a-z0-9]|$)") -> re.Pattern:
    if isinstance(reg, str):
        return re_compile(f"{begin}{reg}{end}")
    return re_compile(f'{begin}(?:{"|".join(reg)}){end}')


_re_map = {
    "studio": StudioMatcher,
    "heyzo": Heyzo,
    "heydouga": Heydouga,
    "honnamatv": Heydouga,
    "fc2": FC2,
    "x1x": X1X,
    "sm": SM_Miracle,
    "h4610": H4610,
    None: UncensoredMatcher,
}
_search_re = (
    r"(?P<studio>(?P<s1>{m}{d}{y}|{y}{m}{d}){tail})".format_map(
        {
            "y": r"[0-2][0-9]",
            "m": r"(?:1[0-2]|0[1-9])",
            "d": r"(?:3[01]|[12][0-9]|0[1-9])",
            "tail": r"[_-](?P<s2>[0-9]{2,5})(?:[_-](?P<s3>[0-9]{1,3}))?",
        }
    ),
    r"heyzo[^0-9]*(?P<heyzo>[0-9]{4})",
    r"(?P<heydouga>hey(?:douga)?[^a-z0-9]*(?P<h1>[0-9]{4})[^a-z0-9]*(?P<h2>[0-9]{3,}))",
    r"honnamatv[^0-9]*(?P<honnamatv>[0-9]{3,})",
    r"fc2[\s_-]*(?:ppv)?[\s_-]*(?P<fc2>[0-9]{2,10})",
    r"x1x[\s_-]+(?P<x1x>[0-9]{6})",
    r"sm[\s_-]*miracle[\s_-]*(?:no)?[\s_.-]+e?(?P<sm>[0-9]{4})",
    r"(?P<h4610>(?P<h41>h4610|[ch]0930)[^a-z0-9]+(?P<h42>[a-z]+[0-9]+))",
    r"((?:n|k|kb|jpgc|shiroutozanmai|hamesamurai)[0-2][0-9]{3}|(?:bouga|ka|sr|tr|sky)[0-9]{3,4})",
    r"(mkbd|bd)[\s_-]?([sm]?[0-9]+)",
    r"(kin8tengoku|xxx[\s_-]?av|[a-z]{1,4}(?:3d2?|2d|2m)+[a-z]{1,4})[\s_-]*([0-9]{2,6})",
    r"(th101)[\s_-]([0-9]{3})[\s_-]([0-9]{6})",
    r"([12][0-9](?:1[0-2]|0[1-9])(?:3[01]|[12][0-9]|0[1-9]))[\s_-]?([a-z]{3,8}(?:_[a-z]{3,6})?)",
)

_search_re = _re_combine(_search_re).search
_iter_re = (
    (_re_combine(PrefixSearcher.regex).finditer, PrefixSearcher),
    (_re_combine(DateSearcher.get_regex()).finditer, DateSearcher),
)

_str_cleaner = re_compile(
    r"""\b(?:
    \[(?:[a-z0-9.-]+\.[a-z]{2,5}|f?hd)\]|
    [a-z0-9-]+\.[a-z]{2,5}@|
    168x|44x|3xplanet|
    sis001|sexinsex|thz|
    uncensored|nodrm|fhd|
    tokyo[\s_-]?hot|1000[\s_-]?girl
    \b)""",
    flags=re.VERBOSE,
).sub


def from_string(string: str):

    string = _str_cleaner("", string.lower())

    match = _search_re(string)
    if match:
        result: ScrapeResult = _re_map[match.lastgroup](string, match).search()
        if result:
            return result

    for matcher, scraper in _iter_re:
        for match in matcher(string):
            result = scraper(string, match).search()
            if result:
                return result
