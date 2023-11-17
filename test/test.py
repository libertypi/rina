import unittest
from pathlib import Path

from avinfo import birth, idol, scraper, video
from avinfo.connection import get_tree


class Test_Scraper(unittest.TestCase):
    def _run_test(self, values: dict, source: str):
        for k, v in values.items():
            result = scraper.scrape(k)
            self.assertIsNotNone(result)
            self.assertEqual(v[0], result.product_id)
            self.assertIn(v[1], result.title)
            self.assertAlmostEqual(v[2], result.publish_date)
            self.assertEqual(source, result.source)

    def test_javbus(self):
        source = "javbus.com"
        values = {
            "CZ016 vol.3": ("CZ016-3", "出合い頭4秒", 1504569600),
            "SMbd-110 s 2 model 3": ("SMBD-110", "小西まりえ", 1412985600),
            "bouga012 [cd2]": ("bouga012-2", "忘我素人", 1496275200),
            "n0253": ("n0253", "無料校内中出", 1188518400),
            "150605-KURUMI_KUMI": ("150605-KURUMI_KUMI", "美麗", 1433462400),
            "150626 KURUMI": ("150626-KURUMI", "美少女", 1435276800),
        }
        self._run_test(values, source)

    def test_javdb(self):
        source = "javdb.com"
        values = {
            "FC2PPV 1201745": ("FC2-1201745", "女の子", 1573776000),
            "XXXAV 20879": ("XXX-AV-20879", "朝倉ことみ", 1565654400),
        }
        self._run_test(values, source)

    def test_carib(self):
        source = "caribbeancom.com"
        values = {
            "[CARIB] 082920_001   (high) 3 haha 5": (
                "082920-001-carib-high-3",
                "未来のきもち",
                1598659200,
            ),
            "120313_001 人 3": ("120313-001-carib", "麻倉憂", 1385683200),
        }
        self._run_test(values, source)

    def test_caribpr(self):
        source = "caribbeancompr.com"
        values = {
            "[HD]022114_777-caribpr-mid haha 5": (
                "022114_777-caribpr-mid",
                "レッドホット",
                1392940800,
            ),
            "090613_656-caribpr-whole1-hd": (
                "090613_656-caribpr-whole1-hd",
                "全裸家政婦",
                1378425600,
            ),
        }
        self._run_test(values, source)

    def test_1pon(self):
        source = "1pondo.tv"
        values = {
            "010617-460 1pon [1080p]": ("010617_460-1pon-1080p", "鈴木さとみ", 1483660800)
        }
        self._run_test(values, source)

    def test_10mu(self):
        source = "10musume.com"
        values = {
            "083014_01-10mu-whole1-psp": (
                "083014_01-10mu-whole1-psp",
                "主人様",
                1409356800,
            )
        }
        self._run_test(values, source)

    def test_paco(self):
        source = "pacopacomama.com"
        values = {
            "(pacopacomama) 071219-130": ("071219_130-paco", "鈴木", 1562889600),
            "120618_394": ("120618_394-paco", "尾上若葉", 1544054400),
            "030417_040-paco": ("030417_040-paco", "熟女", 1488585600),
        }
        self._run_test(values, source)

    def test_mura(self):
        source = "muramura.tv"
        values = {"010216_333-mura": ("010216_333-mura", "美巨乳女優", 1451692800)}
        self._run_test(values, source)

    def test_heyzo(self):
        source = "heyzo.com"
        values = {
            "(heyzo) 1888": ("HEYZO-1888", "芸能人", 1545436800),
            "heyzo-0755-c": ("HEYZO-0755-C", "彼氏目線", 1419465600),
            "HEYZO-0947": ("HEYZO-0947", "美人姉妹", 1441756800),
        }
        self._run_test(values, source)

    def test_heydouga(self):
        source = "heydouga.com"
        values = {
            "heydouga 4240-009-3": ("heydouga-4240-009-3", "若菜亜衣", 1664150400),
            "Heydouga 4030-PPV1768": ("heydouga-4030-1768", "立花美涼", 1448150400),
            "Heydouga 4030-PPV2232 AV9898": ("heydouga-4030-2232", "極射", 1553904000),
            "AV9898-1566": ("AV9898-1566", "前田由美", 1452643200),
            "honnamatv-216 (5)": ("honnamatv-216-5", "M顔娘", 1380585600),
        }
        self._run_test(values, source)

    def test_h4610(self):
        source = "h4610.com"
        values = {"H4610 gol185": ("H4610-gol185", "美加子", 1497052800.0)}
        self._run_test(values, source)

    def test_c0930(self):
        source = "c0930.com"
        values = {"C0930-gol0136": ("C0930-gol0136", "羽田", 1456358400.0)}
        self._run_test(values, source)

    def test_h0930(self):
        source = "h0930.com"
        values = {"H0930 (ori1575)": ("H0930-ori1575", "33歳", 1593216000.0)}
        self._run_test(values, source)

    def test_x1x(self):
        source = "x1x.com"
        values = {
            "x1x-111815 一ノ瀬アメリ": ("x1x-111815", "50連発", 1396483200),
            "x1x.com 111860": ("x1x-111860", "一ノ瀬アメリ", 1332374400),
        }
        self._run_test(values, source)

    def test_smmiracle(self):
        source = "sm-miracle.com"
        values = {"sm miracle e0689": ("sm-miracle-e0689", "黒髪の地方令嬢２", None)}
        self._run_test(values, source)

    def test_fc2(self):
        source = "fc2.com"
        values = {
            "FC2-PPV-1021420_3": ("FC2-1021420-3", "32歳", 1548201600),
        }
        self._run_test(values, source)

    def test_kin8(self):
        source = "kin8tengoku.com"
        values = {
            "kin8-3039": ("kin8-3039", "MASSAGE", 1548892800),
            "Kin8tengoku 3329": ("kin8-3329", "肉感", 1607558400),
        }
        self._run_test(values, source)

    def test_girlsdelta(self):
        source = "girlsdelta.com"
        values = {"GirlsDelta 1706": ("GirlsDelta-1706", "安原舞葉", None)}
        self._run_test(values, source)

    def test_mgs(self):
        source = "mgstage.com"
        values = {
            "siro-1204": ("SIRO-1204", "体験撮影438", 1349136000),
            "DANDY-241": ("DANDY-241", "風呂", 1308355200),
        }
        self._run_test(values, source)

    def test_date(self):
        source = "date string"
        values = {
            "Ray Milf  28Jul2015 1080p": 1438041600,
            "welivetogether.15.08.20.daisy.summers": 1440028800,
            "welivetogether 23-jun 2014 test": 1403481600,
            "welivetogether dec.23.2014 test": 1419292800,
            "deeper.20.03.14.rae.lil.black": 1584144000,
            "march 14, 2012": 1331683200,
            "20170102": 1483315200,
            "20-03.14": None,
        }
        for k, v in values.items():
            result = scraper.scrape(k)
            if v is None:
                self.assertIsNone(result)
            else:
                self.assertEqual(v, result.publish_date)
                self.assertEqual(source, result.source)

    def test_year_regex(self):
        values = {
            0: "00",
            5: "0[0-5]",
            56: "[0-4][0-9]|5[0-6]",
            59: "[0-5][0-9]",
        }
        for k, v in values.items():
            self.assertEqual(scraper.get_year_regex(k), v)


class Test_Idol(unittest.TestCase):
    def _run_test(self, wiki, values):
        for k, v in values.items():
            r = wiki.search(k)
            if v:
                self.assertIsNotNone(r)
                self.assertTrue(r.name)
                self.assertEqual(r.birth, v[0])
                self.assertTrue(r.alias.issuperset(v[1]))
            else:
                self.assertIsNone(r)

    def test_wikipedia(self):
        wiki = idol.Wikipedia
        values = {
            "鈴木さとみ": ("1988-09-09", {"鈴木さとみ", "浅田真美"}),
            "上原結衣": ("1989-10-10", {"上原志織", "上原結衣"}),
            "佐々木愛美": None,
        }
        self._run_test(wiki, values)

    def test_minnanoav(self):
        wiki = idol.MinnanoAV
        values = {
            "片瀬瑞穂": ("1993-04-12", {"成宮梓"}),
            "上原志織": ("1990-05-01", {"上原結衣"}),
            "蓮美": None,
        }
        self._run_test(wiki, values)

    def test_avrevolution(self):
        wiki = idol.AVRevolution
        values = {
            "蓮美": (None, {"大高頼子", "鈴木ありさ"}),
            "市川サラ": (None, {"市川サラ"}),
            "伊藤ゆう": None,
        }
        self._run_test(wiki, values)

    def test_seesaawiki(self):
        wiki = idol.Seesaawiki
        values = {
            "上原結衣": ("1989-10-10", {"上原志織", "上原結衣"}),
            "成宮はるあ": ("1992-07-30", {"一ノ木ありさ", "乃木はるか"}),
            "池田美和子": None,
        }
        self._run_test(wiki, values)

    def test_msin(self):
        wiki = idol.Msin
        values = {
            "木内亜美菜": ("1991-11-30", {"木内亜美菜", "葉月美加子"}),
            "今村ゆう": ("1996-03-15", {"沖野るり", "今村ゆう"}),
            "前田ななみ": ("1993-04-12", {"片瀬瑞穂", "成宮梓"}),
        }
        self._run_test(wiki, values)

    def test_manko(self):
        wiki = idol.Manko
        values = {"南星愛": ("1996-01-31", {"南星愛"}), "小司あん": (None, {"小司あん", "平子知歌"})}
        self._run_test(wiki, values)

    def test_etigoya(self):
        wiki = idol.Etigoya
        values = {
            "市原さとみ": (None, {"鶴田沙織", "西村江梨", "由宇", "北野景子"}),
            "上原志織": (None, {"上原志織", "上原結衣"}),
            "佐々木愛美": (None, {"佐伯史華", "佐々木愛美"}),
        }
        for k, v in values.items():
            r = wiki.search(k)
            self.assertIsNone(r.name)
            self.assertIsNone(r.birth)
            self.assertTrue(r.alias.issuperset(v[1]))

    def test_clean_name(self):
        values = (
            " 木内亜美菜[xxx] abc",
            "xxx) 木内亜美菜 [abc",
            "[xxx] 木内亜美菜 (abc)",
            "    木内亜美菜   　 (abc ~",
            " xxx]木内亜美菜27歳 (abc)",
        )
        for string in values:
            result = idol.clean_name(string)
            self.assertEqual(result, "木内亜美菜", msg=string)


class Test_AVFile(unittest.TestCase):
    class DuckAVFile(video.AVFile):
        def __init__(self, **kwargs) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def test_get_file_name(self):
        values = (
            (
                "FC2-1355235",
                " \n \t ★顔出し☆スタイル抜群！貧乳美熟女の可奈子さん34歳☆かなりレアな貧乳デカ乳首♥電マ潮吹き♥激フェラでイキそ～♥パイパンまんこに生挿入で中出し射精♥【個人撮影】\n \t ",
                "FC2-1355235 ★顔出し☆スタイル抜群！貧乳美熟女の可奈子さん34歳☆かなりレアな貧乳デカ乳首♥電マ潮吹き♥激フェラでイキそ～♥パイパンまんこに生挿入で中出し射精♥【個人撮影】.mp4",
            ),
            (
                "DAVK-042",
                "2920日間ドM調教経過報告 数学教師26歳は結婚していた【優しい夫を裏切り】異常性欲を抑えきれず【浮気男6名連続ザーメン中出し懇願】8年間サークル集団の性処理女として完全支配されてきた彼女が新妻になった今でも6P輪姦ドロドロ体液漬けSEX中毒ドキュメント報告",
                "DAVK-042 2920日間ドM調教経過報告 数学教師26歳は結婚していた【優しい夫を裏切り】異常性欲を抑えきれず【浮気男6名連続ザーメン中出し懇願】.mp4",
            ),
            (
                "FC2-2539111",
                "【無修正ｘ個人撮影】Merry Christmas★アラサー**超メンヘラ風俗嬢とクリスマス企画★ツンデレトナカイさんに顔射したら、ご機嫌斜めになっちゃったけど、最後はピースでメリクリ★",
                "FC2-2539111 【無修正ｘ個人撮影】Merry Christmas★アラサー 超メンヘラ風俗嬢とクリスマス企画★ツンデレトナカイさんに顔射したら、ご機嫌斜めになっちゃったけど.mp4",
            ),
            ("", "日" * 300, None),
            ("", "abc" * 300, None),
        )
        path = Path("test.Mp4")
        for product_id, title, answer in values:
            result = self.DuckAVFile(source=path)._get_filename(product_id, title)
            if answer:
                self.assertEqual(result, answer, msg=result)
            self.assertLessEqual(len(result.encode("utf-8")), video._NAMEMAX)
            self.assertRegex(result, r"\w+")


class Test_Birth_List(unittest.TestCase):
    url = "http://www.minnano-av.com/actress_list.php?birthday=1989"
    tree = None

    def setUp(self) -> None:
        if self.tree is None:
            self.tree = get_tree(self.url)

    def test_get_last_page(self):
        result = birth.get_lastpage(self.tree)
        self.assertGreater(result, 1)

    def test_xpath(self):
        result = birth.xpath_actress_list(self.tree)
        self.assertGreater(len(result), 5)


class Test_Birth_Filter(unittest.TestCase):
    url = "http://www.minnano-av.com/actress.php?actress_id=9190"
    tree = None

    def setUp(self) -> None:
        if self.tree is None:
            self.tree = get_tree(self.url)

    def test_filter(self):
        result_1 = birth.ProductFilter(20, False, False).run(self.tree)
        result_2 = birth.ProductFilter(20, True, False).run(self.tree)
        result_3 = birth.ProductFilter(20, True, True).run(self.tree)
        self.assertGreater(result_1, 1)
        self.assertGreater(result_2, 1)
        self.assertGreater(result_3, 1)

    def test_col_finder(self):
        values = {"作品タイトル": 2, "発売日": 3}
        for k, v in values.items():
            result = birth.ProductFilter._get_col_path(self.tree, k, 10)
            self.assertEqual(result, f"td[{v}]")


if __name__ == "__main__":
    unittest.main()
