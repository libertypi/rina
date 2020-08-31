import re

from .common import epoch_to_str, get_response_tree, session, str_to_epoch

studios = tuple(
    (re.compile(i), j)
    for i, j in (
        (r"\b1pon(do)?\b", "1pon",),
        (r"\b10mu(sume)?\b", "10mu"),
        (r"\bcarib(bean|com)*\b", "carib"),
        (r"\bcarib(bean|com)*pr\b", "caribpr"),
        (r"\bmura(mura)?\b", "mura"),
        (r"\bpaco(pacomama)?\b", "paco"),
        (r"\bmesubuta\b", "mesubuta"),
    )
)
re_clean = tuple(
    (re.compile(i), j)
    for i, j in (
        (r"^\[f?hd\]", "",),
        (
            r"\[[a-z0-9.-]+\.[a-z]{2,}\]|(^|[^a-z0-9])(168x|44x|3xplanet|sis001|sexinsex|thz|uncensored|nodrm|fhd|tokyo[\s_-]?hot|1000[\s_-]?girl)([^a-z0-9]|$)",
            " ",
        ),
    )
)


def scrape(av) -> dict:
    """The scrape method should return a dict containing:
        "productId": productId,
        "title": title,
        "publishDate": publishDate,
        "titleSource": titleSource,
        "dateSource": dateSource,
    """

    # Cleanup
    basename = av.basename
    for p, r in re_clean:
        basename = p.sub(r, basename)
    av.basename = basename
    reSearch = re.search

    # Carib
    if reSearch(r"(^|[^a-z0-9])carib(bean|pr|com)*([^a-z0-9]|$)", basename):
        m = reSearch(r"(^|[^a-z0-9])([0-9]{6})[_-]([0-9]{2,4})([^a-z0-9]|$)", basename)
        if m:
            date = str_to_epoch(m.group(2), "%m%d%y", regex=None)
            av.set_keyword("-".join(m.group(2, 3)))
            return _query(av, func=_carib, standardID=True, date=date, uncensoredOnly=True)

    # Heyzo
    m = reSearch(r"(^|[^a-z0-9])heyzo[^0-9]*([0-9]{4})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword(m.group(2))
        return _query(av, func=_heyzo, uncensoredOnly=True)

    # heydouga
    m = reSearch(r"(^|[^a-z0-9])hey(douga)?[^a-z0-9]*([0-9]{4})[^a-z0-9]*([0-9]{3,})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword(f"heydouga-{m.group(3)}-{m.group(4)}")
        return _query(av, func=_heydouga, uncensoredOnly=True)

    m = reSearch(r"(^|[^a-z0-9])honnamatv[^0-9]*([0-9]{3,})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword(f"honnamatv-{m.group(2)}")
        return _query(av, func=_heydouga, uncensoredOnly=True)

    # h4610, c0930, h0930
    m = reSearch(r"(^|[^a-z0-9])(h4610|[ch]0930)[^a-z0-9]+([a-z]+[0-9]+)([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword("-".join(m.group(2, 3)))
        return _query(av, func=_h4610, uncensoredOnly=True)

    # x1x-111815
    m = reSearch(r"(^|[^a-z0-9])x1x[\s_-]?([0-9]{6})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword(f"x1x-{m.group(2)}")
        return _query(av, func=_x1x, uncensoredOnly=True)

    # sm-miracle
    m = reSearch(r"(^|[^a-z0-9])sm([\s_-]miracle)?([\s_-]no)?[\s_.-]e?([0-9]{4})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword(f"e{m.group(4)}")
        return _query(av, func=_sm_miracle, uncensoredOnly=True)

    # FC2
    m = reSearch(r"(^|[^a-z0-9])fc2[\s_-]*(ppv)?[\s_-]+([0-9]{2,10})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword(m.group(3))
        return _query(av, func=_fc2)

    # 1pondo
    if reSearch(r"(^|[^a-z0-9])(1pon(do)?|10mu(sume)?|mura(mura)?|paco(pacomama)?)([^a-z0-9]|$)", basename,):
        m = reSearch(r"(^|[^a-z0-9])([0-9]{6})[_-]([0-9]{2,4})([^a-z0-9]|$)", basename)
        if m:
            date = str_to_epoch(m.group(2), "%m%d%y", regex=None)
            av.set_keyword("-".join(m.group(2, 3)))
            return _query(av, standardID=True, date=date, uncensoredOnly=True)

    # 160122_1020_01_Mesubuta
    if reSearch(r"(^|[^a-z0-9])mesubuta([^a-z0-9]|$)", basename):
        m = reSearch(r"(^|[^a-z0-9])([0-9]{6})[_-]([0-9]{2,4})[_-]([0-9]{2,4})([^a-z0-9]|$)", basename)
        if m:
            date = str_to_epoch(m.group(2), "%y%m%d", regex=None)
            av.set_keyword("-".join(m.group(2, 3, 4)))
            return _query(av, standardID=True, date=date, uncensoredOnly=True)

    # 1000girl
    m = reSearch(
        r"(^|[^a-z0-9])([12][0-9](1[0-2]|0[1-9])(3[01]|[12][0-9]|0[1-9]))[\s_-]?([a-z]{3,}(_[a-z]{3,})?)([^a-z0-9]|$)",
        basename,
    )
    if m:
        av.set_keyword("-".join(m.group(2, 5)))
        return _query(av, uncensoredOnly=True)

    # th101-000-123456
    m = reSearch(r"(^|[^a-z0-9])(th101)[\s_-]([0-9]{3})[_-]([0-9]{6})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword("-".join(m.group(2, 3, 4)))
        return _query(av, uncensoredOnly=True)

    # mkbd_s24
    m = reSearch(r"(^|[^a-z0-9])(mkbd|bd)[\s_-]?([sm]?[0-9]+)([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword("-".join(m.group(2, 3)))
        return _query(av, uncensoredOnly=True)

    # jukujo
    m = reSearch(r"(^|[^a-z0-9])(jukujo|kin8tengoku)[^0-9]*([0-9]{4})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword("-".join(m.group(2, 3)))
        return _query(av, uncensoredOnly=True)

    # tokyo hot
    if reSearch(
        r"(^|[^a-z0-9])((n|k|kb|jpgc|shiroutozanmai|hamesamurai)[0-3][0-9]{3}|(bouga|ka|sr|tr|sky)[0-9]{3,4})([^a-z0-9]|$)",
        basename,
    ):
        m = reSearch(
            r"(^|[^a-z0-9])(n|k|kb|jpgc|shiroutozanmai|hamesamurai|bouga|ka|sr|tr|sky)([0-9]{3,4})([^a-z0-9]|$)",
            basename,
        )
        if m:
            av.set_keyword("".join(m.group(2, 3)))
            return _query(av, uncensoredOnly=True)

    # club00379hhb
    m = reSearch(r"(^|[^a-z0-9])([a-z]+)0{,2}([0-9]{3,4})hhb[0-9]?([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword("-".join(m.group(2, 3)))
        return _query(av)

    # MX-64
    m = reSearch(
        r"(^|[][)(])([a-z]{1,5}(3d|3d2|2d|2m)*[a-z]{,5}|xxx[_-]?av)[\s_-]?([0-9]{2,6})([^a-z0-9]|$)", basename
    )
    if m:
        av.set_keyword("-".join(m.group(2, 4)))
        return _query(av)

    # 111111_111
    m = reSearch(r"(^|[^a-z0-9])((3[01]|[12][0-9]|0[1-9]){3})[_-]([0-9]{2,4})([^a-z0-9]|$)", basename)
    if m:
        av.set_keyword("-".join(m.group(2, 4)))
        return _query(av, uncensoredOnly=True)

    # 23.Jun.2014
    m = reSearch(
        r"(^|[^a-z0-9])(3[01]|[12][0-9]|0?[1-9])[\s,._-]*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\s,._-]*(20[0-2][0-9])([^a-z0-9]|$)",
        basename,
    )
    if m:
        av.set_date_string(" ".join(m.group(2, 3, 4)), "%d %b %Y")
        return _query(av, func=_get_date_by_string)

    # Dec.23.(20)14
    m = reSearch(
        r"(^|[^a-z0-9])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\s,._-]*(3[01]|[12][0-9]|0?[1-9])[\s,._-]*(20)?([0-2][0-9])([^a-z0-9]|$)",
        basename,
    )
    if m:
        av.set_date_string(f"{m.group(2)} {m.group(3)} 20{m.group(5)}", "%b %d %Y")
        return _query(av, func=_get_date_by_string)

    # (20)19.03.15
    m = reSearch(
        r"(^|[^a-z0-9])(20)?(2[0-5]|1[0-9]|0[7-9])[._-]?(1[0-2]|0[1-9])[._-]?(3[01]|[12][0-9]|0[1-9])([^a-z0-9]|$)",
        basename,
    )
    if m:
        av.set_date_string(f"20{m.group(3)} {m.group(4)} {m.group(5)}", "%Y %m %d")
        return _query(av, func=_get_date_by_string)

    # 23.02.(20)19
    m = reSearch(
        r"(^|[^a-z0-9])(3[01]|[12][0-9]|0[1-9])[._-](1[0-2]|0[1-9])[._-](20)?(2[0-5]|1[0-9]|0[7-9])([^a-z0-9]|$)",
        basename,
    )
    if m:
        av.set_date_string(f"{m.group(2)} {m.group(3)} 20{m.group(5)}", "%d %m %Y")
        return _query(av, func=_get_date_by_string)


def _query(av, func=None, standardID=False, date=None, uncensoredOnly=False) -> dict:
    result = source = None

    if func:
        result = func(av)

    if not result:
        result = _javbus(av, uncensoredOnly)
        if not result:
            result = _javdb(av)

    if result:
        source = result.pop("source", None)
        result = {k: v for k, v in result.items() if v}

    if not result:
        return None

    title = result.get("title")
    if title:
        result["title"] = re.sub(r"\s{2,}", " ", title.strip())
        result["titleSource"] = source

    if standardID:
        reply = _get_standard_product_id(av)
        if reply:
            result["productId"] = reply
    elif "productId" in result:
        suffix = _get_video_suffix(av)
        if suffix:
            result["productId"] = f"{result['productId']}-{suffix}"

    if date:
        result["publishDate"] = date
        result["dateSource"] = "Product ID"
    elif "publishDate" in result:
        result["dateSource"] = source

    return result


def _javbus(av, uncensoredOnly=False) -> dict:
    mask = re.compile(re.sub("[_-]", "[_-]?", av.keyword.lower()))
    for prefix in ("uncensored/",) if uncensoredOnly else ("uncensored/", "",):
        response, tree = get_response_tree(f"https://www.javbus.com/{prefix}search/{av.keyword}", decoder="lxml")
        if tree is None:
            continue
        for a in tree.xpath('//div[@id="waterfall"]//a[@class="movie-box"]//span'):
            productId, date = (i.strip() for i in a.xpath("date/text()"))
            if mask.fullmatch(productId.lower()):
                return {
                    "productId": productId,
                    "title": a.text,
                    "publishDate": str_to_epoch(date) if date else None,
                    "source": "JavBus",
                }


def _javdb(av) -> dict:
    response, tree = get_response_tree("https://javdb.com/search", params={"q": av.keyword}, decoder="lxml")
    if tree is None:
        return None
    mask = re.compile(re.sub("[_-]", "[_-]?", av.keyword.lower()))
    for a in tree.xpath('//div[@id="videos"]//a[@class="box"]'):
        productId = a.xpath('div[@class="uid"]/text()')
        if productId:
            productId = productId[0].strip()
            if mask.fullmatch(productId.lower()):
                title = a.xpath('div[@class="video-title"]')
                date = a.xpath('div[@class="meta"]/text()')
                return {
                    "productId": productId,
                    "title": title[0].text_content() if title else None,
                    "publishDate": str_to_epoch(date[0]) if date else None,
                    "source": "JavDB",
                }


def _carib(av) -> dict:
    if re.search(r"(^|[^a-z0-9])carib(bean|com)*pr([^a-z0-9]|$)", av.basename):
        av.set_keyword(av.keyword.replace("-", "_"))
        url = "https://www.caribbeancompr.com/moviepages"
        source = "caribbeancompr.com"
    else:
        url = "https://www.caribbeancom.com/moviepages"
        source = "caribbeancom.com"

    response, tree = get_response_tree(f"{url}/{av.keyword}/", decoder="euc-jp")
    if tree is None:
        return None

    title = tree.xpath('//div[@id="moviepages"]//div[@class="heading"]/h1')
    if title:
        return {
            "title": title[0].text_content(),
            "source": source,
        }


def _heyzo(av) -> dict:
    response, tree = get_response_tree(f"https://www.heyzo.com/moviepages/{av.keyword}/")
    av.set_keyword(f"HEYZO-{av.keyword}")
    if tree is None:
        return None

    title = tree.xpath('//div[@id="wrapper"]//div[@id="movie"]/h1')
    if title:
        date = tree.xpath(
            '//div[@id="wrapper"]//div[@id="movie"]//table[@class="movieInfo"]/tbody/tr/td[contains(text(),"公開日")]/following-sibling::td/text()'
        )
        return {
            "productId": av.keyword,
            "title": title[0].text_content(),
            "publishDate": str_to_epoch(date[0]) if date else None,
            "source": "heyzo.com",
        }


def _heydouga(av) -> dict:
    prefix, keyword = av.keyword.split("-", 1)
    if prefix == "honnamatv":
        url = f"https://honnamatv.heydouga.com/monthly/honnamatv/moviepages/{keyword}/"
    else:
        url = f'https://www.heydouga.com/moviepages/{keyword.replace("-", "/")}/'

    response, tree = get_response_tree(url, decoder="utf-8")
    if tree is None:
        return None

    title = tree.find(".//title")
    date = tree.xpath('//*[@id="movie-info"]//span[contains(text(),"配信日")]/following-sibling::span')
    return {
        "productId": av.keyword,
        "title": title.text.rsplit(" - ", 1)[0] if title is not None else None,
        "publishDate": str_to_epoch(date[0].text_content()) if date else None,
        "source": "heydouga.com",
    }


def _h4610(av) -> dict:
    prefix, suffix = av.keyword.split("-", 1)
    response, tree = get_response_tree(f"https://www.{prefix}.com/moviepages/{suffix}/")
    if tree is None:
        return None

    title = tree.xpath('//*[@id="moviePlay"]//div[@class="moviePlay_title"]/h1/span/text()')
    if title:
        date = tree.xpath('//*[@id="movieInfo"]//section//dt[contains(text(),"公開日")]/following-sibling::dd[1]/text()')
        return {
            "productId": av.keyword,
            "title": title[0],
            "publishDate": str_to_epoch(date[0]) if date else None,
            "source": f"{prefix}.com",
        }


def _x1x(av) -> dict:
    response, tree = get_response_tree(f"http://www.x1x.com/title/{av.keyword.split('-', 1)[1]}")
    if tree is None:
        return None

    title = tree.find(".//title")
    date = tree.xpath(
        '//div[@id="main_content"]//div[@class="movie_data_rt"]//dt[contains(text(), "配信日")]/following-sibling::dd[1]/text()'
    )
    return {
        "productId": av.keyword,
        "title": title.text if title is not None else None,
        "publishDate": str_to_epoch(date[0]) if date else None,
        "source": "x1x.com",
    }


def _sm_miracle(av) -> dict:
    response = session.get(f"http://sm-miracle.com/movie/{av.keyword}.dat")
    if not response.ok:
        return
    response.encoding = response.apparent_encoding
    title = re.search(r'(?<=[\n,])\s*title:\W*(?P<title>[^\n\'"]+)', response.text)
    if title:
        return {
            "productId": f"sm-miracle-{av.keyword}",
            "title": title["title"],
            "source": "sm-miracle.com",
        }


def _fc2(av) -> dict:
    uid = av.keyword
    av.set_keyword(f"FC2-{uid}")
    response, tree = get_response_tree(f"https://adult.contents.fc2.com/article/{uid}/")
    if tree is not None:
        tree = tree.xpath('//*[@id="top"]//section[@class="items_article_header"]')
        if tree:
            tree = tree[0]
            title = tree.xpath('//div[@class="items_article_headerInfo"]/h3/text()')
            date = tree.xpath('//div[@class="items_article_Releasedate"]/p/text()')
            if date:
                date = re.search(r"\b20[0-9]{2}\W[0-9]{2}\W[0-9]{2}\b", date[0])
            return {
                "productId": av.keyword,
                "title": title[0] if title else None,
                "publishDate": str_to_epoch(date.group()) if date else None,
                "source": "fc2.com",
            }

    response, tree = get_response_tree(f"http://video.fc2.com/a/search/video/?keyword={uid}")
    if tree is not None:
        tree = tree.xpath('//*[@id="pjx-search"]//ul/li[1]//a[@title]')
        if tree:
            tree = tree[0]
            date = re.search(r"(?<=/)20[0-9]{6}(?![0-9])", tree.get("href"))
            return {
                "productId": av.keyword,
                "title": tree.text,
                "publishDate": str_to_epoch(date.group(), "%Y%m%d") if date else None,
                "source": "fc2.com",
            }

    response, tree = get_response_tree(f"https://fc2club.com/html/{av.keyword}.html")
    if tree is not None:
        title = tree.xpath('//div[contains(@class,"main")]/div[@class="show-top-grids"]/div[1]/h3/text()')
        for img in tree.xpath('//*[@id="slider"]//img[@class="responsive"]/@src'):
            m = re.search(r"(?<=/)20[0-9]{2}/[0-9]{4}(?=/)", img)
            if m:
                date = str_to_epoch(m.group(), "%Y %m%d")
                break
        else:
            date = None
        return {
            "productId": av.keyword,
            "title": re.sub(f"^{av.keyword}\s+", "", title[0], flags=re.IGNORECASE) if title else None,
            "publishDate": date,
            "source": "fc2club.com",
        }


def _get_date_by_string(av) -> dict:
    return {
        "publishDate": str_to_epoch(av.keyword, av.dFormat, regex=None),
        "source": "File name",
    }


def _get_standard_product_id(av) -> str:
    i = 0
    basename = re.sub(r"[\s\]\[)(}{._-]+", " ", av.basename)
    for k, v in studios:
        studio = k.search(basename)
        if studio:
            i = studio.end()
            studio = v
            break
    else:
        return None

    if studio == "mesubuta":
        uid = re.search(r"\b[0-9]{6} [0-9]{2,5} [0-9]{1,3}\b", basename)
    else:
        uid = re.search(r"\b[0-9]{6} [0-9]{2,6}\b", basename)
    if uid:
        i = max(i, uid.end()) + 1
        uid = uid.group().replace(" ", "_")
    else:
        return None

    results = [uid, studio]
    for word in basename[i:].split():
        other = re.fullmatch(r"(2160|1080|720|480)p|(high|mid|low|whole|hd|sd|psp)[0-9]*|[0-9]", word)
        if other:
            results.append(other.group())
        else:
            break
    return "-".join(results)


def _get_video_suffix(av, regex=re.compile(r"[\s_.-]+")) -> str:
    basename = regex.sub(" ", av.basename)
    keyword = regex.sub(" ", av.keyword)
    i = basename.find(keyword)
    if i < 0:
        keyword = keyword.split()[-1]
        i = basename.find(keyword)
        if i < 0:
            return None
    i += len(keyword)
    m = re.match(
        r"[\s\[\(]{1,2}([a-d]|(2160|1080|720|480)p|(high|mid|low|whole|hd|sd|cd|psp)?\s?[0-9]{1,2})([\s\]\)]|$)",
        basename[i:],
    )
    if m:
        suffix = m.group(1)
        if suffix in {"a", "b", "c", "d"}:
            suffix = suffix.upper()
        return suffix
