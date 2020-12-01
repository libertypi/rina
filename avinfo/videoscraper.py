import re
from dataclasses import dataclass
from random import choice as random_choice
from re import VERBOSE as VERBOSE
from re import compile as re_compile
from re import search as re_search
from re import sub as re_sub
from urllib.parse import urljoin

from avinfo import common
from avinfo.common import get_response_tree, str_to_epoch, xp_compile


@dataclass
class ScrapeResult:
    productId: str = None
    title: str = None
    publishDate: float = None
    titleSource: str = None
    dateSource: str = None


class Scraper:

    standard_id: bool = False
    uncensored_only: bool = False
    source: str
    url: str

    def __init__(self, string: str, date: float = None, keyword: str = None, **kwargs) -> None:

        self.string = string
        self.date = date
        self.keyword = keyword
        self.__dict__.update(kwargs)

    @classmethod
    def run(cls, string: str):
        raise NotImplemented

    def action(self):

        result: ScrapeResult = self._query() or self._javbus() or self._javdb()
        if not result:
            return

        title = result.title
        if title:
            if re_search(r"\w", title):
                result.title = re_sub(r"\s+", " ", title.strip())
                result.titleSource = self.source
            else:
                result.title = None

        if self.date:
            result.publishDate = self.date
            result.dateSource = "Product ID"
        elif result.publishDate:
            result.dateSource = self.source

        productId = result.productId
        if productId:
            productId = productId.strip()
        if self.standard_id:
            result.productId = self._standardize_id() or productId
        else:
            if productId:
                suffix = self._get_video_suffix()
                if suffix:
                    productId = f"{productId}-{suffix}"
            result.productId = productId

        return result

    def _query(self):
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
                    date = span.findtext("date[2]")
                    self.source = "javbus.com"
                    return ScrapeResult(
                        productId=productId,
                        title=span.text,
                        publishDate=str_to_epoch(date) if date else None,
                    )

    def _javdb(self):
        try:
            pool = Scraper._javdb_url_pool
        except AttributeError:
            pool = Scraper._javdb_url_pool = ["https://javdb.com/search"]

        tree = get_response_tree(random_choice(pool), params={"q": self.keyword})[1]
        if tree is None:
            return

        if len(pool) == 1:
            p = (
                urljoin(i, "search")
                for i in tree.xpath('//nav[@class="sub-header"]/div[contains(text(), "最新域名")]//a/@href')
            )
            pool.extend(i for i in p if i not in pool)

        mask = self._get_keyword_mask()
        for a in tree.iterfind('.//div[@id="videos"]//a[@class="box"]'):
            productId = a.findtext('div[@class="uid"]')
            if productId and mask(productId):
                date = a.findtext('div[@class="meta"]')
                self.source = "javdb.com"
                return ScrapeResult(
                    productId=productId,
                    title=a.findtext('div[@class="video-title"]'),
                    publishDate=str_to_epoch(date) if date else None,
                )

    def _get_keyword_mask(self):
        m = getattr(self, "_keyword_mask", None)
        if not m:
            m = self._keyword_mask = re_compile(
                r"\s*{}\s*".format(re_sub("[_-]", "[_-]?", self.keyword)),
                flags=re.I,
            ).fullmatch
        return m

    _id_cleaner = re_compile(r"[\s()\[\]._-]+").sub

    def _standardize_id(self):
        string = self._id_cleaner(" ", self.string)
        i = 0
        for pattern, replace in (
            (r"\b1pon(?:do)?\b", "1pon"),
            (r"\b10mu(?:sume)?\b", "10mu"),
            (r"\bcarib(?:bean|com)*\b", "carib"),
            (r"\bcarib(?:bean|com)*pr\b", "caribpr"),
            (r"\bmura(?:mura)?\b", "mura"),
            (r"\bpaco(?:pacomama)?\b", "paco"),
            (r"\bmesubuta\b", "mesubuta"),
        ):
            studio = re_search(pattern, string)
            if studio:
                i = studio.end()
                studio = replace
                break
        else:
            return

        if studio == "mesubuta":
            uid = re_search(r"\b[0-9]{6} [0-9]{2,5} [0-9]{1,3}\b", string)
        else:
            uid = re_search(r"\b[0-9]{6} [0-9]{2,6}\b", string)
        if uid:
            i = max(i, uid.end()) + 1
            uid = uid[0].replace(" ", "_")
        else:
            return

        result = [uid, studio]
        matcher = re_compile(r"(?:(?:[0-9]|(?:high|mid|low|whole|hd|sd|psp)[0-9]*|(?:2160|1080|720|480)p)\b\s?)+")
        other = matcher.match(string, i)
        if other:
            result.extend(other[0].split())

        return "-".join(result)

    def _get_video_suffix(self):
        string = self._id_cleaner(" ", self.string)
        keyword = self._id_cleaner(" ", self.keyword)

        i = string.find(keyword)
        if i < 0:
            keyword = keyword.rpartition(" ")[2]
            i = string.find(keyword)
            if i < 0:
                return
        i += len(keyword) + 1

        matcher = re_compile(r"(?:(?:f?hd|sd|cd|vol)\s?|(?:2160|1080|720|480)p\s)*(?P<sfx>[0-9]{1,2}|[a-d])\b")
        m = matcher.match(string, i)
        if m:
            suffix = m["sfx"]
            if suffix in "abcd":
                return suffix.upper()
            return suffix


class Carib(Scraper):

    standard_id: bool = True
    uncensored_only: bool = True
    url: str

    @classmethod
    def run(cls, string: str):
        m = re_search(r"(?:^|[^a-z0-9])carib(?P<com>bean|pr|com)*(?:[^a-z0-9]|$)", string)
        if m:
            n = re_search(r"(?:^|[^a-z0-9])([0-9]{6})[_-]([0-9]{2,4})(?:[^a-z0-9]|$)", string)
            if not n:
                return

            if m["com"] == "pr":
                baseurl = "https://www.caribbeancompr.com/moviepages"
                source = "caribbeancompr.com"
                keyword = "_".join(n.groups())
            else:
                baseurl = "https://www.caribbeancom.com/moviepages"
                source = "caribbeancom.com"
                keyword = "-".join(n.groups())

            return cls(
                string,
                date=str_to_epoch(n[1], "%m%d%y", regex=None),
                source=source,
                keyword=keyword,
                url=f"{baseurl}/{keyword}/",
            ).action()

    def _query(self):
        tree = get_response_tree(self.url, decoder="euc-jp")[1]
        try:
            title = tree.findtext('.//div[@id="moviepages"]//div[@class="heading"]/h1')
        except AttributeError:
            return
        if title:
            return ScrapeResult(title=title)


class Heyzo(Scraper):

    uncensored_only = True
    source = "heyzo.com"

    @classmethod
    def run(cls, string: str):
        m = re_search(r"(?:^|[^a-z0-9])heyzo[^0-9]*([0-9]{4})(?:[^a-z0-9]|$)", string)
        if m:
            uid = m[1]
            return cls(
                string,
                keyword=f"HEYZO-{uid}",
                url=f"https://www.heyzo.com/moviepages/{uid}/",
            ).action()

    def _query(self):
        tree = get_response_tree(self.url, decoder="lxml")[1]

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

    @classmethod
    def run(cls, string: str):
        m = re_search(r"(?:^|[^a-z0-9])hey(?:douga)?[^a-z0-9]*([0-9]{4})[^a-z0-9]*([0-9]{3,})(?:[^a-z0-9]|$)", string)
        if m:
            return cls(
                string,
                keyword=m.expand(r"heydouga-\1-\2"),
                url=f"https://www.heydouga.com/moviepages/{m[1]}/{m[2]}/",
            ).action()

        m = re_search(r"(?:^|[^a-z0-9])honnamatv[^0-9]*([0-9]{3,})(?:[^a-z0-9]|$)", string)
        if m:
            return cls(
                string,
                keyword=f"honnamatv-{m[1]}",
                url=f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{m[1]}/",
            ).action()

    def _query(self):
        tree = get_response_tree(self.url, decoder="utf-8")[1]
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


class H4610(Scraper):
    """h4610, c0930, h0930"""

    uncensored_only = True

    @classmethod
    def run(cls, string: str):
        m = re_search(r"(?:^|[^a-z0-9])(h4610|[ch]0930)[^a-z0-9]+([a-z]+[0-9]+)(?:[^a-z0-9]|$)", string)
        if m:
            return cls(
                string,
                keyword=m.expand(r"\1-\2"),
                source=f"{m[1]}.com",
                url=f"https://www.{m[1]}.com/moviepages/{m[2]}/",
            ).action()

    def _query(self):
        tree = get_response_tree(self.url)[1]
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


class X1X(Scraper):
    """x1x-111815"""

    uncensored_only = True
    source = "x1x.com"

    @classmethod
    def run(cls, string: str):
        m = re_search(r"(?:^|[^a-z0-9])x1x[\s_-]+([0-9]{6})(?:[^a-z0-9]|$)", string)
        if m:
            uid = m[1]
            return cls(
                string,
                keyword=f"x1x-{uid}",
                url=f"http://www.x1x.com/title/{uid}",
            ).action()

    def _query(self):
        tree = get_response_tree(self.url)[1]
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

    @classmethod
    def run(cls, string: str):
        m = re_search(r"(?:^|[^a-z0-9])sm[\s_-]*miracle[\s_-]*(?:no)?[\s_.-]+e?([0-9]{4})(?:[^a-z0-9]|$)", string)
        if m:
            uid = f"e{m[1]}"
            return cls(
                string,
                keyword=uid,
                url=f"http://sm-miracle.com/movie/{uid}.dat",
            ).action()

    def _query(self):
        try:
            response = common.session.get(self.url)
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


class FC2(Scraper):

    source = "fc2.com"
    uid: str

    @classmethod
    def run(cls, string: str):
        m = re_search(r"(?:^|[^a-z0-9])fc2[\s_-]*(?:ppv)?[\s_-]*([0-9]{2,10})(?:[^a-z0-9]|$)", string)
        if m:
            uid = m[1]
            return cls(
                string,
                uid=uid,
                keyword=f"FC2-{uid}",
            ).action()

    def _query(self):
        title = date = None

        tree = get_response_tree(f"https://adult.contents.fc2.com/article/{self.uid}/")[1]
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
            tree = get_response_tree(f"http://video.fc2.com/a/search/video/?keyword={self.uid}")[1]
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

        return ScrapeResult(productId=self.keyword, title=title, publishDate=date)


class Mesubuta(Scraper):
    """160122_1020_01_Mesubuta"""

    standard_id = True
    uncensored_only = True

    @classmethod
    def run(cls, string: str):
        if re_search(r"(?:^|[^a-z0-9])mesubuta(?:[^a-z0-9]|$)", string):
            m = re_search(r"(?:^|[^a-z0-9])([0-9]{6})[_-]([0-9]{2,4})[_-]([0-9]{2,4})(?:[^a-z0-9]|$)", string)
            if m:
                return cls(
                    string,
                    date=str_to_epoch(m[1], "%y%m%d", regex=None),
                    keyword="-".join(m.group(1, 2, 3)),
                ).action()


class UncensoredMatcher(Scraper):

    uncensored_only = True

    @classmethod
    def run(cls, string: str):
        try:
            regex = cls.regex
        except AttributeError:
            regex = (
                # tokyo-hot
                r"""(?:^|[^a-z0-9])
                ((?:n|k|kb|jpgc|shiroutozanmai|hamesamurai)[0-3][0-9]{3}|
                (?:bouga|ka|sr|tr|sky)[0-9]{3,4})
                (?:[^a-z0-9]|$)""",
                # 1000-girl
                r"""(?:^|[^a-z0-9])
                ([12][0-9](?:1[0-2]|0[1-9])(?:3[01]|[12][0-9]|0[1-9]))
                [\s_-]?
                ([a-z]{3,}(?:_[a-z]{3,})?)
                (?:[^a-z0-9]|$)""",
                # th101
                r"""(?:^|[^a-z0-9])
                (th101)
                [\s_-]
                ([0-9]{3})
                [\s_-]
                ([0-9]{6})
                (?:[^a-z0-9]|$)""",
            )
            regex = cls.regex = tuple(re_compile(p, flags=VERBOSE).search for p in regex)

        for matcher in regex:
            m = matcher(string)
            if m:
                return cls(
                    string,
                    keyword="-".join(m.groups()),
                ).action()


class NumberMatcher(Scraper):

    standard_id = True
    uncensored_only = True

    @classmethod
    def run(cls, string: str):
        m = re_search(
            r"(?:^|[^a-z0-9])((?:1[0-2]|0[1-9])(?:3[01]|[12][0-9]|0[1-9])[0-2][0-9])[_-]+([0-9]{2,4})(?:[^a-z0-9]|$)",
            string,
        )
        if m:
            return cls(
                string,
                keyword=m.expand(r"\1-\2"),
                date=str_to_epoch(m[1], "%m%d%y", regex=None),
            ).action()


class PrefixMatcher(Scraper):
    @classmethod
    def run(cls, string: str):

        try:
            regex = cls.regex
        except AttributeError:
            regex = (
                # mkbd_s24
                r"""
                (?:^|[^a-z0-9])
                (?P<prefix>mkbd|bd)
                [\s_-]?
                (?P<id>[sm]?[0-9]+)
                (?:[^a-z0-9]|$)
                """,
                r"""
                (?:^|[^a-z0-9])
                (?P<prefix>kin8tengoku|xxx[\s_-]?av|[a-z]{1,4}(?:3d2?|2d|2m)+[a-z]{1,4})
                [\s_-]*
                (?P<id>[0-9]{2,6})
                (?:[^a-z0-9]|$)
                """,
                # MX-64
                # 259-LUXU123
                # 003ppd00123hhb1
                r"""
                (?:^|[^a-z0-9])
                [0-9]{,3}
                (?P<prefix>[a-z]{2,8})
                [\s_-]*
                (?P<z>0)*
                (?P<id>(?(z)[0-9]{3,6}|[0-9]{2,6}))
                (?:hhb[0-9]?)?(?:[^a-z0-9]|$)
                """,
            )
            regex = cls.regex = tuple(re_compile(p, flags=VERBOSE).finditer for p in regex)

        for matcher in regex:
            for m in matcher(string):
                result = cls(string, keyword=m.expand(r"\g<prefix>-\g<id>")).action()
                if result:
                    return result


class DateMatcher(Scraper):

    source = "File name"

    @classmethod
    def run(cls, string: str):

        try:
            regex = cls.regex
        except AttributeError:
            start = r"(?:^|[^a-z0-9])"
            end = r"(?:[^a-z0-9]|$)"
            sep = r"[\s,._-]+"
            regs = {
                "y": r"(?:20)?(?P<y>[12][0-9])",
                "m": r"(?P<m>1[0-2]|0[1-9])",
                "d": r"(?P<d>3[01]|[12][0-9]|0[1-9])",
                "b": r"(?P<b>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            }
            regex = cls.regex = tuple(
                (
                    re_compile(f"{start}{sep.join(map(regs.get, fmt))}{end}").search,
                    " ".join(f"\\g<{f}>" for f in fmt),
                    " ".join("%" + f for f in fmt),
                )
                for fmt in (
                    "dby",  # 23.Jun.(20)14
                    "bdy",  # Dec.23.(20)14
                    "ymd",  # (20)19.03.15
                    "dmy",  # 23.02.(20)19
                )
            )

        for matcher, temp, format in regex:
            m = matcher(string)
            if m:
                return ScrapeResult(
                    publishDate=str_to_epoch(m.expand(temp), format, regex=None),
                    dateSource=cls.source,
                )

    def _query(self):
        raise NotImplemented


scrapers = (
    Carib,
    Heyzo,
    Heydouga,
    H4610,
    X1X,
    SM_Miracle,
    FC2,
    Mesubuta,
    UncensoredMatcher,
    NumberMatcher,
    PrefixMatcher,
    DateMatcher,
)
