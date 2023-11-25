import datetime
import json
import logging
import re
from abc import ABC
from dataclasses import dataclass
from typing import Optional

from . import network
from .network import get, get_tree, html_fromstring, random_choice, xpath
from .utils import join_root, re_search, re_sub, str_to_epoch, strptime, two_digit_regex

logger = logging.getLogger(__name__)

# Regular expressions
REG_Y = two_digit_regex(0, datetime.date.today().year % 100)
REG_M = r"0[1-9]|1[0-2]"
REG_D = r"[12][0-9]|0[1-9]|3[01]"
_subspace = re.compile(r"\s+").sub
_subdash = re.compile(r"[-_+]+").sub
_subbraces = re.compile(r"[\s()\[\].-]+").sub
_valid_id = re.compile(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*").fullmatch
_has_word = re.compile(r"\w").search
_sub_trash = re.compile(
    r"""\b(
    ([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,4}@|
    [\[(](([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,4}|hd|jav)[\])]|
    ([a-z]+2048|\d+sht|thzu?|168x|44x|hotavxxx|nyap2p|3xplanet|sogclub|sis001|sexinsex|hhd800)(\.[a-z]{2,4})?|
    dioguitar23|(un|de)censored|nodrm|fhd|1000[\s-]*giri
    )\b|\s+""",
    flags=re.VERBOSE,
).sub


@dataclass
class ScrapeResult:
    source: str
    product_id: str = None
    title: str = None
    pub_date: float = None


class Scraper(ABC):
    """Base class for all scrapers."""

    regex: str
    search_id: str
    uncensored: bool = False
    _id_mask = None
    _javdb_domains = ["https://javdb.com/"]

    def __init__(self, match: re.Match) -> None:
        self.match = match
        self.string = match.string

    def search(self):
        for func in self._search, self._javbus, self._javdb:
            result = func()
            if result:
                try:
                    product_id = _subspace("", result.product_id)
                    title = _subspace(" ", result.title).strip()
                except TypeError:
                    continue
                if _valid_id(product_id) and _has_word(title):
                    result.product_id = self._add_suffix(product_id)
                    result.title = title
                    result.pub_date = str_to_epoch(result.pub_date)
                    return result

    def _search(self) -> Optional[ScrapeResult]:
        """
        Abstract method to be implemented by subclasses:
         - Set `self.search_id`
         - Conduct site-specific searches
        """
        raise NotImplementedError

    def _javbus(self):
        try:
            res = get(f"https://www.javbus.com/uncensored/search/{self.search_id}")
            if "member.php?mod=logging" in res.url:
                logger.warning("JavBus is walled, consider switching network.")
                return
            res.raise_for_status()
            http_ok = True
        except network.HTTPError:
            if self.uncensored:
                return
            http_ok = False
        except network.RequestException as e:
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
        if re_search(r"/\s*0+\s*\)", result):
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
                        title = re_sub(r"^【(お得|特価)】\s*", "", title)
                except IndexError:
                    continue
                return ScrapeResult(
                    product_id=product_id,
                    title=title,
                    pub_date=span.findtext("date[2]"),
                    source="javbus.com",
                )

    def _javdb(self):
        tree = get_tree(
            f"{random_choice(self._javdb_domains)}search?q={self.search_id}&f=all"
        )
        if tree is None or "/search" not in tree.base_url:
            return
        if len(self._javdb_domains) == 1:
            self._set_javdb_alt_domains(tree)

        mask = self._get_id_mask()
        for v in xpath(
            './/div[contains(@class, "movie-list")]'
            '//a[@class="box"]/div[@class="video-title"]'
        )(tree):
            product_id = v.findtext("strong", "")
            if mask(product_id):
                return ScrapeResult(
                    product_id=product_id,
                    title=xpath("string(text())")(v),
                    pub_date=v.findtext('../div[@class="meta"]'),
                    source="javdb.com",
                )

    def _set_javdb_alt_domains(self, tree: network.HtmlElement):
        domains = self._javdb_domains
        main_netloc = network.urlparse(domains[0]).netloc
        for d in tree.xpath(
            ".//nav[@class='sub-header']/div[@class='content']/text()[contains(., '最新域名')]"
            "/following-sibling::a/@href[not(contains(., '.app'))]",
            smart_strings=False,
        ):
            pr = network.urlparse(d)
            if not (pr.scheme and pr.netloc):
                continue
            d = f"{pr.scheme}://{pr.netloc}/"
            if d not in domains:
                domains.append(d)
                network.set_alias(pr.netloc, main_netloc)
                logger.debug("Add javdb alt domain: %s", d)
        if len(domains) == 1:
            self.warning(f"unable to find alt domains at: {tree.base_url}")

    def _get_id_mask(self):
        mask = self._id_mask
        if not mask:
            mask = re_sub(
                r"[\s_-]+((?=\d))?",
                lambda m: r"[\s_-]*" if m[1] is None else r"[\s_-]*0*",
                self.search_id,
            )
            mask = self._id_mask = re.compile(rf"\s*{mask}\s*", re.IGNORECASE).fullmatch
        return mask

    def _add_suffix(self, product_id: str) -> str:
        m = self.match
        suffix = re_search(
            r"^\s*(?:(?:f?hd|cd|dvd|vol|[hm]hb|part)\s*|(?:4k|sd|(?:216|108|72|48)0p)\s+)*"
            r"(?P<s>[1-9][0-9]?|[a-d])\b",
            _subbraces(" ", self.string[m.end(m.lastindex) :]),
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
        self.search_id = f'{match["s1"]}_{match["s2"]}'

        m = self.studio_match = re_search(self._std_re, self.string)
        if m:
            self._search = getattr(self, m.lastgroup)
        elif match["s3"] and match["s4"]:
            self._search = self._mesubuta

        result = super().search()

        if result and (result.source.startswith("jav") or not result.pub_date):
            try:
                result.pub_date = strptime(match["s1"], self.datefmt)
            except ValueError as e:
                self.warning(e)
        return result

    def _search(self) -> Optional[ScrapeResult]:
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

        mask = self._get_id_mask()
        if title and mask(product_id):
            if title.startswith(product_id):
                title = title[len(product_id) :]

            return ScrapeResult(
                product_id=product_id,
                title=title,
                pub_date=date,
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
            pub_date=date,
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
                f"{url}/dyn/phpauto/movie_details/movie_id/{self.search_id}.json"
            )
            data.raise_for_status()
        except network.HTTPError as e:
            logger.debug(e)
            return
        except network.RequestException as e:
            logger.warning(e)
            return
        try:
            data = data.json()
            return ScrapeResult(
                product_id=data["MovieID"],
                title=data["Title"],
                pub_date=data["Release"],
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

        suffix = re_search(
            r"^\s*(([1-9]|(high|mid|low|whole|hd|sd|psp)[0-9]*|(216|108|72|48)0p)($|\s))+",
            _subbraces(" ", self.string[i:]),
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
                pub_date=data["dateCreated"],
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
                pub_date=date,
                source=self.source,
            )


class FC2Scraper(Scraper):
    uncensored = True
    source = "fc2.com"
    regex = r"fc2(?:[\s-]*ppv)?[\s-]+(?P<fc2>[0-9]{4,10})"

    def _search(self):
        uid = self.match["fc2"]
        self.search_id = f"FC2-{uid}"

        tree = get_tree(f"https://adult.contents.fc2.com/article/{uid}/")
        if tree is None:
            return
        if "payarticle" in tree.base_url:
            logger.warning(f"FC2 is walled, consider switching network.")
            return
        if tree.find('.//div[@class="items_notfound_wp"]') is not None:
            return

        return ScrapeResult(
            product_id=self.search_id,
            title=(
                tree.xpath('string(.//meta[@name="twitter:title"]/@content)')
                or tree.xpath(
                    'string(.//div[@class="items_article_MainitemThumb"]//img/@title)'
                )
                or "".join(
                    xpath('.//div[@class="items_article_headerInfo"]/h3/text()')(tree)
                )
            ),
            pub_date=tree.findtext('.//div[@class="items_article_Releasedate"]/p'),
            source=self.source,
        )


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
            pub_date=date,
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


class HonnamatvScraper(HeydougaScraper):
    regex = r"honnamatv[^0-9]*(?P<honna>[0-9]{3,})"

    def _search(self):
        uid = self.match["honna"]
        self.search_id = f"honnamatv-{uid}"
        return super()._search(
            f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{uid}/"
        )


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
                pub_date=date,
                source=self.source,
            )


class SMMiracleScraper(Scraper):
    uncensored = True
    source = "sm-miracle.com"
    regex = r"sm[\s-]*miracle(?:[\s-]+no)?[\s.-]+e?(?P<sm>[0-9]{4})"

    def _search(self):
        uid = "e" + self.match["sm"]
        self.search_id = f"sm-miracle-{uid}"

        try:
            data = get(f"https://sm-miracle.com/movie/{uid}.dat")
            data.raise_for_status()
        except network.HTTPError as e:
            logger.debug(e)
            return
        except network.RequestException as e:
            logger.warning(e)
            return

        return ScrapeResult(
            product_id=self.search_id,
            title=re_search(
                r'[{,]\s*title\s*:\s*(?P<q>[\'"])(?P<title>.+?)(?P=q)\s*[,}]',
                data.content.decode(errors="ignore"),
            )["title"],
            source=self.source,
        )


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
            pub_date=date,
            source=f"{m1}.com",
        )


class Kin8Scraper(Scraper):
    uncensored = True
    source = "kin8tengoku.com"
    regex = r"kin8(?:tengoku)?[^0-9]*(?P<kin8>[0-9]{4})"

    def _search(self):
        uid = self.match["kin8"]
        self.search_id = f"kin8-{uid}"

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
            self.error(e)
            return
        date = xpath(
            'string(.//div[@id="main"]'
            '/div[contains(@id,"detail_box")]//td[contains(.,"更新日")]'
            '/following-sibling::td[contains(.,"20")])'
        )(tree)

        return ScrapeResult(
            product_id=self.search_id,
            title=title[2] or title[0],
            pub_date=date,
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
            pub_date=date,
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
    regex = rf"((?:{REG_Y})(?:{REG_M})(?:{REG_D}))[\s-]+([a-z]{{3,8}})(?:-(?P<kg>[a-z]{{3,6}}))?"

    def _search(self):
        m = self.match
        i = m.lastindex
        self.search_id = f"{m[i-2]}-{m[i-1]}_{m[i]}"


class MGSScraper(Scraper):
    # This regex is compiled as is and matched with finditer. <hhb> matches
    # empty string so it does not consume the sequence number.
    regex = r"\b(?:[0-9]{,2}|(?P<num>[0-9]{3,5}))(?P<pre>[a-z]{2,9})-?(?=[0-9]*?[1-9])(?P<sfx>[0-9]{2,8})(?:[a-d]?|(?P<hhb>)[hm]hb[0-9]{,2})\b"
    mgs_get = None

    @classmethod
    def _load_mgs(cls, filename: str = "mgs.json"):
        with open(join_root(filename), "r", encoding="utf-8") as f:
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
                title = re_sub(
                    r"^(\s*【.*?】)+|【[^】]*映像付】|\+\d+分\b", "", tree.findtext("h1")
                )
            except (AttributeError, TypeError) as e:
                self.error(e)
                return

            date = xp(tree, title="発売日") or xp(tree, title="開始日")
            return ScrapeResult(
                product_id=self.search_id,
                title=title,
                pub_date=date,
                source="mgstage.com",
            )


class DateSearcher:
    source = "date string"
    fmt = {}

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

        return tuple(t.format_map(fmt) for t in template)

    regex = _init_regex()

    @classmethod
    def search(cls, m: re.Match):
        try:
            fmt = cls.fmt[m.lastgroup]
        except KeyError:
            fmt = cls.fmt[m.lastgroup] = " ".join("%" + f for f in m.lastgroup)

        i = m.lastindex + 1
        try:
            return ScrapeResult(
                pub_date=strptime(" ".join(m.group(i, i + 2, i + 3)), fmt),
                source=cls.source,
            )
        except ValueError as e:
            logger.error(f"[{cls.__name__}] [{m[0]}] {e}")


def _load_json_ld(tree: network.HtmlElement):
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
        data = re_sub(
            r'(?<=[{,])\s*("[^"]+")\s*:\s*"(.*?)"\s*(?=[,}])',
            lambda m: f"{m[1]}:{dumps(m[2], ensure_ascii=False)}",
            data,
        )
        return json.loads(data)


def _combine_regex(*args: Scraper, b=r"\b") -> re.Pattern:
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
        result = f"{b}{result}{b}"
    else:
        result = f"{b}(?:{result}){b}"

    assert "_" not in result, f'"_" in regex: {result}'
    logger.debug("Combined regex: '%s'", result)
    return re.compile(result)


def scrape(string: str) -> Optional[ScrapeResult]:
    """Scrape information from a string."""

    string = _sub_trash(" ", _subdash("-", string.lower()))

    m = _maker_matcher(string)
    if m:
        result = _scraper_map[m.lastgroup](m).search()
        if result:
            return result
    else:
        for m in _general_matcher(string):
            result = MGSScraper(m).search()
            if result:
                return result
    m = _date_matcher(string)
    if m:
        return DateSearcher.search(m)


_scraper_map = {
    "studio": StudioScraper,
    "heyzo": HeyzoScraper,
    "fc2": FC2Scraper,
    "heydou": HeydougaScraper,
    "av98": AV9898Scraper,
    "honna": HonnamatvScraper,
    "x1x": X1XScraper,
    "sm": SMMiracleScraper,
    "h4610": H4610Scraper,
    "kin8": Kin8Scraper,
    "gd": GirlsDeltaScraper,
    None: UncensoredScraper,
    "kg": OneKGiriScraper,
}
_maker_matcher = _combine_regex(*_scraper_map.values()).search
_general_matcher = re.compile(MGSScraper.regex).finditer
_date_matcher = _combine_regex(DateSearcher).search
