import datetime
import json
import re
from dataclasses import dataclass
from typing import Optional

from avinfo.connection import (
    HtmlElement,
    HTTPError,
    get,
    get_tree,
    html_fromstring,
    xpath,
)
from avinfo.utils import (
    join_root,
    stderr_write,
    str_to_epoch,
    strptime,
    re_search,
    re_sub,
)

__all__ = ("scrape",)

# Regular expressions
_subspace = re.compile(r"\s+").sub
_subbraces = re.compile(r"[\s()\[\].-]+").sub
_valid_id = re.compile(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*").fullmatch
_has_word = re.compile(r"\w").search
_trans_sep = {ord(c): r"[\s_-]*0*" for c in " _-"}


def get_year_regex(year: int):
    """Computing the regex that matches double digits from 00 - `year`. `year`
    should be a digit from 0-99.

    example:
      - 5  -> 0[0-5]
      - 56 -> [0-4][0-9]|5[0-6]
      - 59 -> [0-5][0-9]
    """
    assert 0 <= year <= 99, f"value out of range: {year}"
    digit_reg = lambda n: f"[0-{n}]" if n > 1 else "[01]" if n else "0"
    tens, ones = divmod(year, 10)
    if tens > 0 and ones < 9:
        return f"{digit_reg(tens - 1)}[0-9]|{tens}{digit_reg(ones)}"
    return digit_reg(tens) + digit_reg(ones)


REG_Y = get_year_regex(datetime.date.today().year % 100)
REG_M = r"0[1-9]|1[0-2]"
REG_D = r"[12][0-9]|0[1-9]|3[01]"


@dataclass
class ScrapeResult:
    source: str
    product_id: str = None
    title: str = None
    publish_date: float = None


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
        for func in self._native, self._javbus, self._javdb:
            result = func()
            if result:
                try:
                    product_id = _subspace("", result.product_id)
                    title = _subspace(" ", result.title).strip()
                except TypeError:
                    continue
                if _valid_id(product_id) and _has_word(title):
                    result.title = title
                    result.product_id = self._process_id(product_id)
                    assert (
                        isinstance(result.publish_date, float)
                        or result.publish_date is None
                    )
                    return result

    def _native(self) -> Optional[ScrapeResult]:
        pass

    def _javbus(self):
        res = get(
            f"https://www.javbus.com/uncensored/search/{self.keyword}", check=False
        )
        if "member.php?mod=logging" in res.url:
            self._warn("JavBus is walled, consider switching network.")
            return
        try:
            res.raise_for_status()
            ok = True
        except HTTPError:
            if self.uncensored_only:
                return
            ok = False

        tree = html_fromstring(res.content)
        if ok:
            result = self._parse_javbus(tree)
            if result or self.uncensored_only:
                return result

        result = xpath(
            'string(//div[@class="search-header"]//li[@role="presentation"][1])'
        )(tree)
        if re_search(r"/\s*0+\s*\)", result):
            return

        tree = get_tree(f"https://www.javbus.com/search/{self.keyword}")
        if tree is not None:
            return self._parse_javbus(tree)

    def _parse_javbus(self, tree: HtmlElement):
        try:
            tree = tree.find('.//div[@id="waterfall"]').iterfind(
                './/a[@class="movie-box"]//span'
            )
        except AttributeError as e:
            self._warn(e)
            return

        mask = self._get_keyword_mask()
        for span in tree:
            product_id = span.findtext("date[1]", "")
            if mask(product_id):
                title = span.text
                try:
                    if title[0] == "【":
                        title = re_sub(r"^【(お得|特価)】\s*", "", title)
                except IndexError:
                    continue

                return ScrapeResult(
                    product_id=product_id,
                    title=title,
                    publish_date=str_to_epoch(span.findtext("date[2]")),
                    source="javbus.com",
                )

    def _javdb(self):
        tree = get_tree(f"https://javdb.com/search?q={self.keyword}&f=all")
        if tree is None or "/search" not in tree.base_url:
            return

        mask = self._get_keyword_mask()
        for v in xpath(
            './/div[contains(@class, "movie-list")]'
            '//a[@class="box"]/div[@class="video-title"]'
        )(tree):
            product_id = v.findtext("strong", "")
            if mask(product_id):
                return ScrapeResult(
                    product_id=product_id,
                    title=xpath("string(text())")(v),
                    publish_date=str_to_epoch(v.findtext('../div[@class="meta"]')),
                    source="javdb.com",
                )

    def _get_keyword_mask(self):
        mask = self._mask
        if not mask:
            mask = self._mask = re.compile(
                rf"\s*{self.keyword.translate(_trans_sep)}\s*", flags=re.I
            ).fullmatch
        return mask

    def _process_id(self, product_id: str) -> str:
        m = self.match
        suffix = re_search(
            r"^\s*(?:(?:f?hd|sd|cd|dvd|vol|[hm]hb|part)\s?|(?:216|108|72|48)0p\s)*"
            r"(?P<s>[1-9][0-9]?|[a-d])\b",
            _subbraces(" ", self.string[m.end(m.lastindex) :]),
        )

        if suffix:
            suffix = suffix["s"]
            if suffix in "abcd":
                suffix = suffix.upper()
            return f"{product_id}-{suffix}"

        return product_id

    def _warn(self, e: Exception):
        stderr_write(f"error ({self.string}): {e}\n")


class StudioMatcher(Scraper):
    uncensored_only = True
    regex = r"(?P<studio>(?P<s1>{m}{d}{y}|(?P<s4>{y}{m}{d}))-(?P<s2>[0-9]{{2,4}})(?:-(?P<s3>0[0-9]))?)".format(
        y=rf"(?:{REG_Y})",
        m=rf"(?:{REG_M})",
        d=rf"(?:{REG_D})",
    )
    _std_re = (
        r"\b(?:"
        r"(?P<_carib>carib(?:bean(?:com)?)?|カリビアンコム)|"  # 112220-001-carib
        r"(?P<_caribpr>carib(?:bean(?:com)?)?pr|カリビアンコムプレミアム)|"  # 101515_391-caribpr
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
        self.keyword = f'{match["s1"]}_{match["s2"]}'

        m = self.studio_match = re_search(self._std_re, self.string)
        if m:
            self._native = getattr(self, m.lastgroup)
        elif match["s3"] and match["s4"]:
            self._native = self._mesubuta

        result = super().search()

        if result and (result.source.startswith("jav") or not result.publish_date):
            try:
                result.publish_date = strptime(match["s1"], self.datefmt)
            except ValueError as e:
                self._warn(e)
        return result

    def _native(self) -> Optional[ScrapeResult]:
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

        product_id = ""
        date = studio = None
        get_value = lambda p: _subspace("", p.text_content().partition(":")[2])

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
                studio = re_search(self._std_re, get_value(p))
                if product_id and date:
                    break

        if studio:
            result = getattr(self, studio.lastgroup)()
            if result:
                return result

        mask = self._get_keyword_mask()
        if title and mask(product_id):
            if title.startswith(product_id):
                title = title[len(product_id) :]

            return ScrapeResult(
                product_id=product_id,
                title=title,
                publish_date=str_to_epoch(date),
                source="javbus.com",
            )

    def _carib(self, url: str = None, source: str = None):
        if not url:
            self.studio = "carib"
            self.keyword = self.keyword.replace("_", "-")
            source = "caribbeancom.com"
            url = "https://www.caribbeancom.com"

        tree = get_tree(f"{url}/moviepages/{self.keyword}/")
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
            product_id=self.keyword,
            title=title,
            publish_date=str_to_epoch(date),
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
            data = get(
                f"{url}/dyn/phpauto/movie_details/movie_id/{self.keyword}.json"
            ).json()
            return ScrapeResult(
                product_id=data["MovieID"],
                title=data["Title"],
                publish_date=str_to_epoch(data["Release"]),
                source=source,
            )
        except HTTPError:
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
            self.keyword = "_".join(self.match.group("s1", "s2", "s3"))

    def _process_id(self, product_id: str) -> str:
        result = [product_id, self.studio] if self.studio else [product_id]

        i = self.match.end()
        if self.studio_match:
            i = max(self.studio_match.end(), i)

        suffix = re_search(
            r"^\s*(([1-9]|(high|mid|low|whole|hd|sd|psp)[0-9]*|(216|108|72|48)0p)($|\s))+",
            _subbraces(" ", self.string[i:]),
        )
        if suffix:
            result.extend(suffix[0].split())

        return "-".join(result)


class Heyzo(Scraper):
    __slots__ = ()
    uncensored_only = True
    source = "heyzo.com"
    regex = r"heyzo[^0-9]*(?P<heyzo>[0-9]{4})"

    def _native(self):
        uid = self.match["heyzo"]
        self.keyword = f"HEYZO-{uid}"

        tree = get_tree(f"https://www.heyzo.com/moviepages/{uid}/")
        if tree is None:
            return
        try:
            data = _load_json_ld(tree)
            return ScrapeResult(
                product_id=self.keyword,
                title=data["name"],
                publish_date=str_to_epoch(data["dateCreated"]),
                source=self.source,
            )
        except TypeError:
            pass
        except (ValueError, KeyError) as e:
            self._warn(e)

        tree = tree.find('.//div[@id="wrapper"]//div[@id="movie"]')
        try:
            title = tree.findtext("h1").rpartition("\t-")
            date = tree.find(
                './/table[@class="movieInfo"]//*[@class="table-release-day"]'
            ).text_content()
        except AttributeError as e:
            self._warn(e)
        else:
            return ScrapeResult(
                product_id=self.keyword,
                title=title[0] or title[2],
                publish_date=str_to_epoch(date),
                source=self.source,
            )


class FC2(Scraper):
    __slots__ = ()
    uncensored_only = True
    source = "fc2.com"
    regex = r"fc2(?:[\s-]*ppv)?[\s-]+(?P<fc2>[0-9]{4,10})"

    def _native(self):
        uid = self.match["fc2"]
        self.keyword = f"FC2-{uid}"

        tree = get_tree(f"https://adult.contents.fc2.com/article/{uid}/")
        if tree is None:
            return
        if "payarticle" in tree.base_url:
            self._warn(f"FC2 is walled, consider switching network.")
            return
        if tree.find('.//div[@class="items_notfound_wp"]') is not None:
            return

        return ScrapeResult(
            product_id=self.keyword,
            title=(
                tree.xpath('string(.//meta[@name="twitter:title"]/@content)')
                or tree.xpath(
                    'string(.//div[@class="items_article_MainitemThumb"]//img/@title)'
                )
                or "".join(
                    xpath('.//div[@class="items_article_headerInfo"]/h3/text()')(tree)
                )
            ),
            publish_date=str_to_epoch(
                tree.findtext('.//div[@class="items_article_Releasedate"]/p')
            ),
            source=self.source,
        )


class Heydouga(Scraper):
    __slots__ = ()
    uncensored_only = True
    source = "heydouga.com"
    regex = r"heydouga[^0-9]*(?P<h1>[0-9]{4})[^0-9]+(?P<heydou>[0-9]{3,6})"

    def _native(self, url: str = None):
        if not url:
            m1, m2 = self.match.group("h1", "heydou")
            self.keyword = f"heydouga-{m1}-{m2}"
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
            product_id=self.keyword,
            title=title[0] or title[2],
            publish_date=str_to_epoch(date),
            source=self.source,
        )


class AV9898(Heydouga):
    __slots__ = ()
    regex = r"av9898[^0-9]+(?P<av98>[0-9]{3,})"

    def _native(self):
        uid = self.match["av98"]
        self.keyword = f"AV9898-{uid}"
        return super()._native(
            f"https://av9898.heydouga.com/monthly/av9898/moviepages/{uid}/"
        )


class Honnamatv(Heydouga):
    __slots__ = ()
    regex = r"honnamatv[^0-9]*(?P<honna>[0-9]{3,})"

    def _native(self):
        uid = self.match["honna"]
        self.keyword = f"honnamatv-{uid}"
        return super()._native(
            f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{uid}/"
        )


class X1X(Scraper):
    __slots__ = ()
    uncensored_only = True
    source = "x1x.com"
    regex = r"x1x(?:\.com)?[\s-]+(?P<x1x>[0-9]{6})"

    def _native(self):
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
                'string(.//div[@class="movie_data_rt"]'
                '//dt[contains(., "配信日")]'
                '/following-sibling::dd[contains(., "20")])'
            )(tree)
        except TypeError as e:
            self._warn(e)
        else:
            return ScrapeResult(
                product_id=self.keyword,
                title="".join(xpath("h2[1]/text()")(tree)),
                publish_date=str_to_epoch(date),
                source=self.source,
            )


class SM_Miracle(Scraper):
    __slots__ = ()
    uncensored_only = True
    source = "sm-miracle.com"
    regex = r"sm[\s-]*miracle(?:[\s-]+no)?[\s.-]+e?(?P<sm>[0-9]{4})"

    def _native(self):
        uid = "e" + self.match["sm"]
        self.keyword = f"sm-miracle-{uid}"

        try:
            data = get(f"https://sm-miracle.com/movie/{uid}.dat")
        except HTTPError:
            return

        return ScrapeResult(
            product_id=self.keyword,
            title=re_search(
                r'[{,]\s*title\s*:\s*(?P<q>[\'"])(?P<title>.+?)(?P=q)\s*[,}]',
                data.content.decode(errors="ignore"),
            )["title"],
            source=self.source,
        )


class H4610(Scraper):
    __slots__ = ()
    uncensored_only = True
    regex = r"(?P<h41>h4610|[ch]0930)\W+(?P<h4610>[a-z]+[0-9]+)"

    def _native(self):
        m1, m2 = self.match.group("h41", "h4610")
        self.keyword = f"{m1.upper()}-{m2}"

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
                self._warn(e)

        return ScrapeResult(
            product_id=self.keyword,
            title=title,
            publish_date=str_to_epoch(date),
            source=f"{m1}.com",
        )


class Kin8(Scraper):
    __slots__ = ()
    uncensored_only = True
    source = "kin8tengoku.com"
    regex = r"kin8(?:tengoku)?[^0-9]*(?P<kin8>[0-9]{4})"

    def _native(self):
        uid = self.match["kin8"]
        self.keyword = f"kin8-{uid}"

        tree = get_tree(f"https://www.kin8tengoku.com/moviepages/{uid}/index.html")
        if tree is None:
            return

        title = xpath(
            'normalize-space(.//div[@id="sub_main"]'
            '/p[contains(@class, "sub_title")])'
        )(tree)
        try:
            title = title.partition("限定配信 ")
        except AttributeError as e:
            self._warn(e)
            return
        date = xpath(
            'string(.//div[@id="main"]'
            '/div[contains(@id,"detail_box")]//td[contains(.,"更新日")]'
            '/following-sibling::td[contains(.,"20")])'
        )(tree)

        return ScrapeResult(
            product_id=self.keyword,
            title=title[2] or title[0],
            publish_date=str_to_epoch(date),
            source=self.source,
        )


class GirlsDelta(Scraper):
    __slots__ = ()
    uncensored_only = True
    source = "girlsdelta.com"
    regex = r"girls[\s-]?delta[^0-9]*(?P<gd>[0-9]{3,4})"

    def _native(self):
        uid = self.match["gd"]
        self.keyword = f"GirlsDelta-{uid}"

        tree = get_tree(f"https://girlsdelta.com/product/{uid}")
        if tree is None or "/product/" not in tree.base_url:
            return

        date = xpath(
            'string(.//div[@class="product-detail"]'
            '//li/*[contains(text(), "公開日")]'
            '/following-sibling::*/text()[contains(., "20")])'
        )(tree)

        return ScrapeResult(
            product_id=self.keyword,
            title=xpath(
                'string(.//div[@class="product-detail"]'
                '//li/*[contains(text(), "モデル名")]'
                "/following-sibling::*)"
            )(tree),
            publish_date=str_to_epoch(date),
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
        r"(mkb?d)[\s-]?(s?[0-9]{2,4})",
        r"(bd)[\s-]?([gm][0-9]{2,4})",
        r"(roselip)[\s-]*([0-9]{4})",
        r"([a-z]{1,4}(?:3d2?|2d|2m)+[a-z]{1,4}|r18|t28)[\s-]*([0-9]{2,6})",
    )

    def _native(self):
        self.keyword = "-".join(filter(None, self.match.groups()))


class OneKGiri(Scraper):
    __slots__ = ()
    uncensored_only = True
    regex = rf"((?:{REG_Y})(?:{REG_M})(?:{REG_D}))[\s-]+([a-z]{{3,8}})(?:-(?P<kg>[a-z]{{3,6}}))?"

    def _native(self):
        m = self.match
        i = m.lastindex
        self.keyword = f"{m[i-2]}-{m[i-1]}_{m[i]}"


class PatternSearcher(Scraper):
    __slots__ = ()
    regex = r"[0-9]{,5}(?P<uid>[a-z]{2,10})-?(?P<z>0)*(?P<num>(?(z)[0-9]{3,8}|[0-9]{2,8}))(?:[hm]hb[0-9]{,2})?"
    mgs_get = None

    @classmethod
    def _load_mgs(cls, filename: str = "mgs.json"):
        with open(join_root(filename), "r", encoding="utf-8") as f:
            cls.mgs_get = json.load(f).get

    def _native(self):
        m = self.match
        uid = m["uid"]
        self.keyword = f'{uid.upper()}-{m["num"]}'

        try:
            number = self.mgs_get(uid)
        except TypeError:
            self._load_mgs()
            number = self.mgs_get(uid)
        if number is None:
            return

        number += self.keyword
        tree = get_tree(f"https://www.mgstage.com/product/product_detail/{number}/")
        if tree is None or number not in tree.base_url:
            return

        tree = tree.find(
            './/article[@id="center_column"]/div[@class="common_detail_cover"]'
        )
        try:
            title = re_sub(r"^(\s*【.*?】)+|【[^】]*映像付】|\+\d+分\b", "", tree.findtext("h1"))
        except (AttributeError, TypeError) as e:
            self._warn(e)
            return

        xp = xpath(
            "string(.//table/tr/th[contains(., $title)]"
            '/following-sibling::td[contains(., "20")])'
        )
        date = xp(tree, title="発売日") or xp(tree, title="開始日")

        return ScrapeResult(
            product_id=self.keyword,
            title=title,
            publish_date=str_to_epoch(date),
            source="mgstage.com",
        )


class DateSearcher:
    source = "date string"

    def _init_regex():
        template = [
            r"(?P<{0}>{{{0[0]}}}\s*?(?P<s{0}>[\s.-])\s*{{{0[1]}}}\s*?(?P=s{0})\s*{{{0[2]}}})".format(
                f
            )
            for f in (
                "ymd",  # (20)19.03.15
                "mdy",  # 10.15.(20)19
                "dmy",  # 23.02.(20)19
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
            "y": rf"(?:20)?({REG_Y})",
            "Y": rf"(20(?:{REG_Y}))",
            "m": r"(1[0-2]|0?[1-9])",
            "mm": rf"({REG_M})",
            "d": r"([12][0-9]|3[01]|0?[1-9])",
            "dd": rf"({REG_D})",
            "b": r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            "B": r"(january|february|march|april|may|june|july|august|september|october|november|december)",
        }  # yapf: disable
        regex = tuple(t.format_map(fmt) for t in template)

        fmt.clear()
        return regex, fmt

    regex, fmt = _init_regex()
    del _init_regex

    @classmethod
    def search(cls, m: re.Match):
        try:
            fmt = cls.fmt[m.lastgroup]
        except KeyError:
            fmt = cls.fmt[m.lastgroup] = " ".join("%" + f for f in m.lastgroup)

        i = m.lastindex + 1
        try:
            return ScrapeResult(
                publish_date=strptime(" ".join(m.group(i, i + 2, i + 3)), fmt),
                source=cls.source,
            )
        except ValueError as e:
            stderr_write(f"parsing date failed '{m[0]}': {e}\n")


def _load_json_ld(tree: HtmlElement):
    """Loads JSON-LD from tree.

    Raise TypeError if there is no json-ld, ValueError if parsing failed.
    """
    data = re_sub(
        r"[\t\n\r\f\v]", " ", tree.findtext('.//script[@type="application/ld+json"]')
    )
    try:
        return json.loads(data)
    except ValueError:
        dumps = json.dumps
        repl = lambda m: f"{m[1]}:{dumps(m[2], ensure_ascii=False)}"
        return json.loads(
            re_sub(r'(?<=[{,])\s*("[^"]+")\s*:\s*"(.*?)"\s*(?=[,}])', repl, data)
        )


def _combine_scraper_regex(*args: Scraper, b=r"\b") -> re.Pattern:
    """Combine one or more scraper regexes to form a single pattern.

    After called, the `regex` attributes of input classes are deleted in order
    to free some memory.
    """
    item = []
    for scraper in args:
        if isinstance(scraper.regex, str):
            item.append(scraper.regex)
        else:
            item.extend(scraper.regex)
        del scraper.regex

    result = "|".join(item)
    assert "_" not in result, f'"_" in regex: {result}'

    if len(item) == 1:
        result = f"{b}{result}{b}"
    else:
        result = f"{b}(?:{result}){b}"

    return re.compile(result)


def scrape(string: str) -> Optional[ScrapeResult]:
    """Scrape information from a string."""

    string = _clean_re(" ", string.lower()).replace("_", "-")

    m = _search_re(string)
    if m:
        result = _search_map[m.lastgroup](string, m).search()
        if result:
            return result

    for m in _iter_re(string):
        result = PatternSearcher(string, m).search()
        if result:
            return result

    m = _date_re(string)
    if m:
        return DateSearcher.search(m)


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
_clean_re = re.compile(
    r"""
    \s*\[(?:[a-z0-9.-]+\.[a-z]{2,4}|f?hd|jav)\]\s*|
    (?:[\s\[_-]+|\b)(?:
        (?:[a-z]+2048|\d+sht|thzu?|168x|44x)\.[a-z]{2,4}|
        (?:hotavxxx|nyap2p|3xplanet|sogclub|sis001|sexinsex)(?:\.[a-z]{2,4})?|
        [a-z0-9.-]+\.[a-z]{2,4}@|
        dioguitar23|uncensored|nodrm|fhd|tokyo[\s_-]?hot|1000[\s_-]?giri
    )(?:[\s\]_-]+|\b)|
    \s+
    """,
    flags=re.VERBOSE,
).sub
