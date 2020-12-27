import re
from dataclasses import dataclass
from json import loads as json_loads
from random import choice as random_choice
from typing import Optional
from urllib.parse import urljoin

from requests.cookies import create_cookie

from avinfo.common import (
    HtmlElement,
    RequestException,
    get_tree,
    re_compile,
    re_search,
    re_sub,
    session,
    str_to_epoch,
    strptime,
    xpath,
)

session.cookies.set_cookie(create_cookie(domain="www.javbus.com", name="existmag", value="all"))
_subspace = re_compile(r"\s+").sub
_subbraces = re_compile(r"[\s()\[\].-]+").sub


@dataclass
class ScrapeResult:
    source: str
    productId: str = None
    title: str = None
    publishDate: float = None


class Scraper:
    """Base class for scrapers."""

    __slots__ = ("string", "match", "keyword", "_mask")
    regex: str
    keyword: str
    uncensored_only: bool = False

    def __init__(self, string: str, match: re.Match) -> None:
        self.string = string
        self.match = match
        self._mask = None

    def search(self):

        for func in self._query, self._javbus, self._javdb:
            result = func()
            if result:
                try:
                    productId = _subspace("", result.productId)
                    title = _subspace(" ", result.title).strip()
                except TypeError:
                    continue
                if productId and title:
                    break
        else:
            return

        result.title = title
        result.productId = self._process_product_id(productId)
        assert isinstance(result.publishDate, float) or result.publishDate is None

        return result

    def _query(self) -> Optional[ScrapeResult]:
        pass

    def _javbus(self):

        for base in ("uncensored/",) if self.uncensored_only else ("uncensored/", ""):

            tree = get_tree(f"https://www.javbus.com/{base}search/{self.keyword}")
            if tree is None:
                continue
            try:
                tree = tree.find('.//div[@id="waterfall"]').iterfind('.//a[@class="movie-box"]//span')
            except AttributeError as e:
                self._warn(e)
                continue

            mask = self._get_keyword_mask()
            for span in tree:

                productId = span.findtext("date[1]", "")
                if mask(productId):

                    title = span.text
                    try:
                        if title[0] == "【":
                            title = re_sub(r"^【(お得|特価)】\s*", "", title)
                    except IndexError:
                        continue

                    return ScrapeResult(
                        productId=productId,
                        title=title,
                        publishDate=str_to_epoch(span.findtext("date[2]")),
                        source="javbus.com",
                    )

    def _javdb(self):

        try:
            base = random_choice(Scraper._javdb_url)
        except AttributeError:
            base = "https://javdb.com/search?q="
            tree = get_tree(base + self.keyword, encoding="auto")
            if tree is None:
                return
            alt = tree.xpath(
                'string(.//nav[@class="sub-header"]//text()[contains(., "最新域名")]'
                '/following::a[starts-with(@href, "http")][1]/@href)',
                smart_string=False,
            )
            if alt:
                Scraper._javdb_url = (base, urljoin(alt, "search?q="))
            else:
                Scraper._javdb_url = (base,)
        else:
            tree = get_tree(base + self.keyword, encoding="auto")
            if tree is None:
                return

        if "/search" not in tree.base_url:
            return

        tree = tree.find('.//div[@id="videos"]')
        if tree is None:
            return

        mask = self._get_keyword_mask()
        for a in tree.iterfind('.//a[@class="box"]'):

            productId = a.findtext('div[@class="uid"]', "")
            if mask(productId):

                return ScrapeResult(
                    productId=productId,
                    title=a.findtext('div[@class="video-title"]'),
                    publishDate=str_to_epoch(a.findtext('div[@class="meta"]')),
                    source="javdb.com",
                )

    def _get_keyword_mask(self):

        mask = self._mask
        if not mask:
            mask = self._mask = re_compile(
                r"\s*{}\s*".format(re_sub(r"[\s_-]", r"[\\s_-]?", self.keyword)),
                flags=re.IGNORECASE,
            ).fullmatch
        return mask

    def _process_product_id(self, productId: str) -> str:

        suffix = re_search(
            r"^\s*((f?hd|sd|cd|dvd|vol)\s?|(216|108|72|48)0p\s)*(?P<s>[1-9][0-9]?|[a-d])\b",
            _subbraces(" ", self.string[self.match.end() :]),
        )
        if suffix:
            suffix = suffix["s"]
            if suffix in "abcd":
                suffix = suffix.upper()
            return f"{productId}-{suffix}"
        return productId

    def _warn(self, e: Exception):
        import warnings

        warnings.warn(f'Exception raised when processing "{self.string}":\n{e}')


class StudioMatcher(Scraper):

    uncensored_only = True
    regex = r"(?P<studio>(?P<s1>{m}{d}{y}|(?P<s4>{y}{m}{d})){tail})".format(
        y=r"[0-2][0-9]",
        m=r"(?:0[1-9]|1[0-2])",
        d=r"(?:[12][0-9]|0[1-9]|3[01])",
        tail=r"-(?P<s2>[0-9]{2,4})(?:-(?P<s3>0[0-9]))?",
    )
    _search_studio = re_compile(
        r"""\b(?:
        (?P<_carib>carib(?:bean(?:com)?)?|カリビアンコム)|  # 112220-001-carib
        (?P<_caribpr>carib(?:bean(?:com)?)?pr|カリビアンコムプレミアム)|    # 101515_391-caribpr
        (?P<_1pon>1pon(?:do)?|一本道)|  # 110411_209-1pon
        (?P<_10mu>10mu(?:sume)?|天然むすめ)|    # 122812_01-10mu
        (?P<_paco>paco(?:pacomama)?|パコパコママ)|  # 120618_394-paco
        (?P<_mura>mura)(?:mura)?|   # 010216_333-mura
        (?P<_mesubuta>mesubuta|メス豚)  # 160122_1020_01-mesubuta
        )\b""",
        flags=re.VERBOSE,
    ).search
    datefmt: str = "%m%d%y"
    studio: str = None

    def search(self):

        match = self.match
        self.keyword = f'{match["s1"]}_{match["s2"]}'

        m = self.studio_match = self._search_studio(self.string)
        if m:
            self._query = getattr(self, m.lastgroup)
        elif match["s3"] and match["s4"]:
            self._query = self._mesubuta

        result = super().search()

        if result and (result.source.startswith("jav") or not result.publishDate):
            try:
                result.publishDate = strptime(self.match["s1"], self.datefmt)
            except ValueError as e:
                self._warn(e)
        return result

    def _query(self) -> Optional[ScrapeResult]:

        tree = get_tree(f"https://www.javbus.com/{self.keyword}")

        if tree is None:
            keyword = self.keyword.replace("_", "-")
            tree = get_tree(f"https://www.javbus.com/{keyword}")
            if tree is None:
                return
            self.keyword = keyword

        tree = tree.find('.//div[@class="container"]')
        try:
            title = tree.findtext("h3").strip()
        except AttributeError as e:
            self._warn(e)
            return

        productId = date = studio = None
        get_value = lambda p: _subspace("", p.text_content().partition(":")[2])

        for p in xpath(
            './/div[contains(@class, "movie")]'
            '/div[contains(@class, "info")]'
            '/p[span/text() and contains(.,  ":")]'
        )(tree):

            k = p.findtext("span")
            if "識別碼" in k:
                productId = get_value(p)
            elif "日期" in k:
                date = get_value(p)
            elif "製作商" in k:
                studio = self._search_studio(get_value(p))
                if productId and date:
                    break

        if studio:
            result = getattr(self, studio.lastgroup)()
            if result:
                return result

        if title and productId:
            if title.startswith(productId):
                title = title[len(productId) :]

            return ScrapeResult(
                productId=productId,
                title=title,
                publishDate=str_to_epoch(date),
                source="javbus.com",
            )

    def _carib(self, url: str = None, source: str = None):

        if not url:
            self.studio = "carib"
            self.keyword = self.keyword.replace("_", "-")
            source = "caribbeancom.com"
            url = "https://www.caribbeancom.com"

        tree = get_tree(f"{url}/moviepages/{self.keyword}/", encoding="euc-jp")
        if tree is None:
            return

        tree = tree.find('.//div[@id="moviepages"]')
        try:
            title = tree.findtext('.//div[@class="heading"]/h1')
        except AttributeError as e:
            self._warn(e)
            return

        date = xpath(
            'string(.//li[@class="movie-spec"]'
            '/span[contains(text(), "配信日") or contains(text(), "販売日")]'
            '/following-sibling::span[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=str_to_epoch(date),
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
            json = session.get(f"{url}/dyn/phpauto/movie_details/movie_id/{self.keyword}.json")
            json.raise_for_status()
            json = json.json()
            return ScrapeResult(
                productId=json["MovieID"],
                title=json["Title"],
                publishDate=str_to_epoch(json["Release"]),
                source=source,
            )
        except RequestException:
            pass
        except (ValueError, KeyError) as e:
            self._warn(e)

    def _10mu(self):
        self.studio = "10mu"
        return self._1pon(
            url="https://www.10musume.com",
            source="10musume.com",
        )

    def _paco(self):
        self.studio = "paco"

        tree = get_tree(f"https://www.pacopacomama.com/moviepages/{self.keyword}/", encoding="euc-jp")
        if tree is None:
            return

        tree = tree.find('.//div[@id="main"]')
        try:
            title = tree.findtext("h1")
        except AttributeError as e:
            self._warn(e)
            return

        date = tree.findtext('.//div[@class="detail-info"]//*[@class="date"]')
        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=str_to_epoch(date),
            source="pacopacomama.com",
        )

    def _mura(self):
        self.studio = "mura"

        tree = get_tree(f"https://www.muramura.tv/moviepages/{self.keyword}/", encoding="euc-jp")
        if tree is None:
            return

        tree = tree.find('.//div[@id="detail-main"]')
        try:
            date = xpath('string(ul[@class="info"]/li[contains(.,"更新日")]/text()[contains(.,"20")])')(tree)
        except TypeError as e:
            self._warn(e)
            return

        return ScrapeResult(
            productId=self.keyword,
            title="".join(xpath("h1[1]/text()")(tree)),
            publishDate=str_to_epoch(date),
            source="muramura.tv",
        )

    def _mesubuta(self) -> None:
        self.studio = "mesubuta"
        self.datefmt = "%y%m%d"
        if self.match["s3"]:
            self.keyword = "_".join(self.match.group("s1", "s2", "s3"))

    def _process_product_id(self, productId: str) -> str:

        if not self.studio:
            return productId

        if self.studio_match:
            i = max(self.studio_match.end(), self.match.end())
        else:
            i = self.match.end()

        suffix = re_search(
            r"^\s*(([1-9]|(high|mid|low|whole|hd|sd|psp)[0-9]*|(216|108|72|48)0p)($|\s))+",
            _subbraces(" ", self.string[i:]),
        )
        if suffix:
            return f'{self.keyword}-{self.studio}-{suffix[0].strip().replace(" ", "-")}'

        return f"{self.keyword}-{self.studio}"


class Heyzo(Scraper):

    __slots__ = ()
    uncensored_only = True
    source = "heyzo.com"
    regex = r"heyzo[^0-9]*(?P<heyzo>[0-9]{4})"

    def _query(self):
        uid = self.match["heyzo"]
        self.keyword = f"HEYZO-{uid}"

        tree = get_tree(f"https://www.heyzo.com/moviepages/{uid}/")
        if tree is None:
            return

        try:
            json = _load_json_ld(tree)
            return ScrapeResult(
                productId=self.keyword,
                title=json["name"],
                publishDate=str_to_epoch(json["dateCreated"]),
                source=self.source,
            )
        except TypeError:
            pass
        except (ValueError, KeyError) as e:
            self._warn(e)

        tree = tree.find('.//div[@id="wrapper"]//div[@id="movie"]')
        try:
            title = tree.findtext("h1").rpartition("\t-")
            date = tree.find('.//table[@class="movieInfo"]//*[@class="table-release-day"]').text_content()
        except AttributeError as e:
            self._warn(e)
        else:
            return ScrapeResult(
                productId=self.keyword,
                title=title[0] or title[2],
                publishDate=str_to_epoch(date),
                source=self.source,
            )


class FC2(Scraper):

    __slots__ = ()
    uncensored_only = True
    source = "fc2.com"
    regex = r"fc2(?:[\s-]*ppv)?[\s-]+(?P<fc2>[0-9]{4,10})"

    def _query(self):

        uid = self.match["fc2"]
        self.keyword = f"FC2-{uid}"
        title = date = None

        tree = get_tree(f"https://adult.contents.fc2.com/article/{uid}/")
        if tree is not None:
            tree = tree.find('.//section[@id="top"]//section[@class="items_article_header"]')
            if tree is not None:
                title = tree.findtext('.//div[@class="items_article_headerInfo"]/h3')
                date = str_to_epoch(tree.findtext('.//div[@class="items_article_Releasedate"]/p'))

        if not title:
            tree = get_tree("https://video.fc2.com/a/search/video/", params={"keyword": f"aid={uid}"})
            try:
                tree = tree.find('.//div[@id="pjx-search"]//ul/li//a[@title][@href]')
                title = tree.text
                date = strptime(re_search(r"/(20[12][0-9]{5})", tree.get("href"))[1], "%Y%m%d")
            except AttributeError:
                return
            except (TypeError, ValueError) as e:
                self._warn(e)

        return ScrapeResult(
            productId=self.keyword,
            title=title,
            publishDate=date,
            source=self.source,
        )

    def _javdb(self):
        try:
            json = session.get(
                f"https://javdb.com/videos/search_autocomplete.json?q={self.keyword}",
            ).json()
        except (RequestException, ValueError):
            return

        mask = self._get_keyword_mask()
        try:
            for item in json:
                if not mask(item["number"]):
                    continue
                if item["title"].endswith("..."):
                    return
                return ScrapeResult(
                    productId=item["number"],
                    title=re_sub(r"^\s*\[.*?\]\s*", "", item["title"]),
                    publishDate=str_to_epoch(item["meta"].rpartition("發布時間:")[2]),
                    source="javdb.com",
                )
        except KeyError as e:
            self._warn(e)


class Heydouga(Scraper):

    __slots__ = ()
    uncensored_only = True
    source = "heydouga.com"
    regex = r"heydouga[^0-9]*(?P<h1>[0-9]{4})[^0-9]+(?P<heydou>[0-9]{3,6})"

    def _query(self, url: str = None):

        if not url:
            m1, m2 = self.match.group("h1", "heydou")
            self.keyword = f"heydouga-{m1}-{m2}"
            url = f"https://www.heydouga.com/moviepages/{m1}/{m2}/"

        tree = get_tree(url, encoding="auto")
        if tree is None:
            return

        title = tree.findtext(".//title").rpartition(" - ")
        date = xpath(
            'string(.//div[@id="movie-info"]'
            '//span[contains(., "配信日")]'
            '/following-sibling::span[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            productId=self.keyword,
            title=title[0] or title[2],
            publishDate=str_to_epoch(date),
            source=self.source,
        )


class AV9898(Heydouga):

    __slots__ = ()
    regex = r"av9898[^0-9]+(?P<av98>[0-9]{3,})"

    def _query(self):
        uid = self.match["av98"]
        self.keyword = f"AV9898-{uid}"
        return super()._query(f"https://av9898.heydouga.com/monthly/av9898/moviepages/{uid}/")


class Honnamatv(Heydouga):

    __slots__ = ()
    regex = r"honnamatv[^0-9]*(?P<honna>[0-9]{3,})"

    def _query(self):
        uid = self.match["honna"]
        self.keyword = f"honnamatv-{uid}"
        return super()._query(f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{uid}/")


class X1X(Scraper):

    __slots__ = ()
    uncensored_only = True
    source = "x1x.com"
    regex = r"x1x(?:\.com)?[\s-]+(?P<x1x>[0-9]{6})"

    def _query(self):

        uid = self.match["x1x"]
        self.keyword = f"x1x-{uid}"

        tree = get_tree(f"http://www.x1x.com/title/{uid}")
        if tree is None:
            tree = get_tree(f"http://www.x1x.com/ppv/title/{uid}")
            if tree is None:
                return

        tree = tree.find('.//div[@id="main_content"]')
        try:
            date = xpath(
                'string(.//div[@class="movie_data_rt"]//dt[contains(., "配信日")]'
                '/following-sibling::dd[contains(., "20")])'
            )(tree)
        except TypeError as e:
            self._warn(e)
        else:
            return ScrapeResult(
                productId=self.keyword,
                title="".join(xpath("h2[1]/text()")(tree)),
                publishDate=str_to_epoch(date),
                source=self.source,
            )


class SM_Miracle(Scraper):

    __slots__ = ()
    uncensored_only = True
    source = "sm-miracle.com"
    regex = r"sm[\s-]*miracle(?:[\s-]+no)?[\s.-]+e?(?P<sm>[0-9]{4})"

    def _query(self):

        uid = "e" + self.match["sm"]
        self.keyword = f"sm-miracle-{uid}"
        try:
            res = session.get(f"http://sm-miracle.com/movie/{uid}.dat")
            res.raise_for_status()
        except RequestException:
            return

        try:
            return ScrapeResult(
                productId=self.keyword,
                title=re_search(
                    r'[\n{,]\s*title:\s*(?P<q>[\'"])(?P<title>.+?)(?P=q)',
                    res.content.decode("utf-8"),
                )["title"],
                source=self.source,
            )
        except TypeError as e:
            self._warn(e)


class H4610(Scraper):

    __slots__ = ()
    uncensored_only = True
    regex = r"(?P<h41>h4610|[ch]0930)\W+(?P<h4610>[a-z]+[0-9]+)"

    def _query(self):

        m1, m2 = self.match.group("h41", "h4610")
        self.keyword = f"{m1.upper()}-{m2}"

        tree = get_tree(f"https://www.{m1}.com/moviepages/{m2}/")
        if tree is None:
            return

        try:
            json = _load_json_ld(tree)
            return ScrapeResult(
                productId=self.keyword,
                title=json["name"],
                publishDate=str_to_epoch(json["dateCreated"]),
                source=f"{m1}.com",
            )
        except TypeError:
            pass
        except (ValueError, KeyError) as e:
            self._warn(e)

        date = xpath(
            'string(.//div[@id="movieInfo"]//section//dt[contains(., "公開日")]'
            '/following-sibling::dd[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            productId=self.keyword,
            title=tree.findtext('.//div[@id="moviePlay"]//div[@class="moviePlay_title"]/h1/span'),
            publishDate=str_to_epoch(date),
            source=f"{m1}.com",
        )


class Kin8(Scraper):

    __slots__ = ()
    uncensored_only = True
    source = "kin8tengoku.com"
    regex = r"kin8(?:tengoku)?[^0-9]*(?P<kin8>[0-9]{4})"

    def _query(self):
        uid = self.match["kin8"]
        self.keyword = f"kin8-{uid}"

        tree = get_tree(f"https://www.kin8tengoku.com/moviepages/{uid}/index.html")
        if tree is None:
            return

        title = xpath('normalize-space(.//div[@id="sub_main"]/p[contains(@class,"sub_title")])')(tree)
        title = title.partition("限定配信 ")
        date = xpath(
            'string(.//div[@id="main"]/div[contains(@id,"detail_box")]'
            '//td[contains(.,"更新日")]/following-sibling::td[contains(.,"20")])'
        )(tree)

        return ScrapeResult(
            productId=self.keyword,
            title=title[2] or title[0],
            publishDate=str_to_epoch(date),
            source=self.source,
        )


class GirlsDelta(Scraper):

    __slots__ = ()
    uncensored_only = True
    source = "girlsdelta.com"
    regex = r"girls[\s-]?delta[^0-9]*(?P<gd>[0-9]{3,4})"

    def _query(self):
        uid = self.match["gd"]
        self.keyword = f"GirlsDelta-{uid}"

        tree = get_tree(f"https://girlsdelta.com/product/{uid}")
        if tree is None or "/product/" not in tree.base_url:
            return

        date = xpath(
            'string(.//div[@class="product-detail"]//li'
            '/*[contains(text(), "公開日")]'
            '/following-sibling::*/text()[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            productId=self.keyword,
            title=tree.findtext(".//title").partition("｜")[0],
            publishDate=str_to_epoch(date),
            source=self.source,
        )


class UncensoredMatcher(Scraper):

    __slots__ = ()
    uncensored_only = True
    regex = (
        r"((?:gs|jiro|ka|kosatsu|mldo|ot|red|sg|sky|sr|tr|wl)[0-9]{3})",
        r"((?:(?:ham|liv)esamurai|it|jpgc|jup|kb?|lb|ma|n|pf|pp|sp|tar|wald)[0-2][0-9]{3})",
        r"((?:bouga|crazyasia|eyu|gedo|nukimax|peworld|shi(?:kai|ma|routozanmai)|ubt)[0-9]{2,8})",
        r"(xxx)[\s-]*(av)[^0-9]*([0-9]{4,5})",
        r"(th101)[\s-]*([0-9]{3})[\s-]([0-9]{6})",
        r"(mkb?d|bd)[\s-]?([sm]?[0-9]{2,4})",
        r"([a-z]{1,4}(?:3d2?|2d|2m)+[a-z]{1,4}|r18|t28)[\s-]*([0-9]{2,6})",
    )

    def _query(self):
        self.keyword = "-".join(filter(None, self.match.groups()))


class OneKGiri(Scraper):

    __slots__ = ()
    uncensored_only = True
    regex = r"([12][0-9](?:0[1-9]|1[0-2])(?:[12][0-9]|0[1-9]|3[01]))[\s-]+([a-z]{3,8})(?:-(?P<kg>[a-z]{3,6}))?"

    def _query(self):
        m = self.match
        i = m.lastindex
        self.keyword = f"{m[i-2]}-{m[i-1]}_{m[i]}"


class PatternSearcher(Scraper):

    __slots__ = ()
    regex = r"[0-9]{,3}(?P<p1>[a-z]{2,10})-?(?P<z>0)*(?P<p2>(?(z)[0-9]{3,8}|[0-9]{2,8}))(?:hhb[0-9]{,2})?"

    def _query(self):
        m = self.match
        self.keyword = f'{m["p1"]}-{m["p2"]}'


class DateSearcher:

    source = "date string"

    def _init_regex():
        template = [
            r"(?P<{0}>{{{1}}}\s*?(?P<s{0}>[\s.-])\s*{{{2}}}\s*?(?P=s{0})\s*{{{3}}})".format(f, *f)
            for f in (
                "mdy",  # 10.15.(20)19
                "ymd",  # (20)19.03.15
                "dmy",  # 23.02.(20)19
            )
        ]
        template.append(r"(?P<Ymd>{Y}(){mm}{dd})")  # 20170102
        template.extend(
            r"(?P<{0}>{{{1}}}\s*([.,-]?)\s*{{{2}}}\s*?[\s.,-]{4}\s*{{{3}}})".format(f, *f, r)
            for f, r in (
                ("dby", "?"),  # 23Jun(20)14
                ("dBy", "?"),  # 19June(20)14
                ("bdy", ""),  # Dec.23.(20)14
                ("Bdy", ""),  # June.19.(20)14
                ("ybd", "?"),  # (20)12Feb3
                ("yBd", "?"),  # (20)12March3
            )
        )
        fmt = {
            "y": r"(?:20)?([12][0-9])",
            "Y": r"(20[12][0-9])",
            "m": r"(1[0-2]|0?[1-9])",
            "mm": r"(1[0-2]|0[1-9])",
            "d": r"([12][0-9]|3[01]|0?[1-9])",
            "dd": r"([12][0-9]|3[01]|0[1-9])",
            "b": r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            "B": r"(january|february|march|april|may|june|july|august|september|october|november|december)",
        }
        regex = tuple(t.format_map(fmt) for t in template)

        fmt.clear()
        return regex, fmt

    regex, fmt = _init_regex()

    @classmethod
    def search(cls, match: re.Match):

        try:
            fmt = cls.fmt[match.lastgroup]
        except KeyError:
            fmt = cls.fmt[match.lastgroup] = " ".join("%" + f for f in match.lastgroup)

        i = match.lastindex + 1
        try:
            return ScrapeResult(
                publishDate=strptime(" ".join(match.group(i, i + 2, i + 3)), fmt),
                source=cls.source,
            )
        except ValueError:
            pass


def _load_json_ld(tree: HtmlElement):
    """Loads JSON-LD data from page.

    Raise TypeError if json was not found on page, ValueError when parsing failed.
    """
    json = re_sub(r"[\t\n\r\f\v]", "", tree.findtext('.//script[@type="application/ld+json"]'))
    try:
        return json_loads(json)
    except ValueError:
        repl = lambda m: '":"{}"{}'.format(re_sub(r'\\*"', r'\\"', m[1]), m[2])
        return json_loads(re_sub(r'"\s*:\s*"([^"]*"(?!\s*[,}]).*?)"\s*([,}])', repl, json))


def _combine_scraper_regex(*args: Scraper, b=r"\b") -> re.Pattern:
    """Combine one or more scraper regexes to a single pattern, in strict order,
    without duplicates.
    """

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


def from_string(string: str) -> Optional[ScrapeResult]:
    """Scrape information from a string."""

    string = _clean_re(" ", string.lower()).replace("_", "-")

    match = _search_re(string)
    if match:
        result = _search_map[match.lastgroup](string, match).search()
        if result:
            return result

    for match in _iter_re(string):
        result = PatternSearcher(string, match).search()
        if result:
            return result

    match = _date_re(string)
    if match:
        return DateSearcher.search(match)


_search_map = {
    "studio": StudioMatcher,
    "heyzo": Heyzo,
    "fc2": FC2,
    "heydou": Heydouga,
    "av98": AV9898,
    "honna": Honnamatv,
    "x1x": X1X,
    "sm": SM_Miracle,
    "h4610": H4610,
    "kin8": Kin8,
    "gd": GirlsDelta,
    None: UncensoredMatcher,
    "kg": OneKGiri,
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
    168x|44x|3xplanet|sogclub|
    sis001|sexinsex|thz|dioguitar23|
    uncensored|nodrm|fhd|
    tokyo[\s_-]?hot|1000[\s_-]?giri
    )(?:[\s\]_-]+|\b)|
    \s+
    """,
    flags=re.VERBOSE,
).sub
