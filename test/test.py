import unittest

from avinfo import idol, scraper, video, birth
from avinfo._utils import get_tree


class Test_Scraper(unittest.TestCase):

    def _run_test(self, values: dict, source: str):
        for string, answer in values.items():
            result = scraper.scrape(string)
            self.assertEqual(answer[0], result.product_id)
            self.assertIn(answer[1], result.title)
            self.assertAlmostEqual(answer[2], result.publish_date)
            self.assertEqual(source, result.source)

    def test_javbus(self):
        source = 'javbus.com'
        values = {
            "CZ016 vol.3": ('CZ016-3', '出合い頭4秒', 1504569600),
            'SMbd-110 s 2 model 3': ('SMBD-110', '小西まりえ', 1412985600),
            'bouga012 [cd2]': ('bouga012-2', '忘我素人', 1496275200),
            'n0253': ('n0253', '無料校内中出', 1188518400),
            '150605-KURUMI_KUMI': ('150605-KURUMI_KUMI', '美麗', 1433462400),
            '150626 KURUMI': ('150626-KURUMI', '美少女', 1435276800)
        }
        self._run_test(values, source)

    def test_javdb(self):
        source = 'javdb.com'
        values = {
            'FC2PPV 1201745': ('FC2-1201745', '女の子', 1573776000),
            'XXXAV 20879': ('XXX-AV-20879', '朝倉ことみ', 1565654400),
        }
        self._run_test(values, source)

    def test_carib(self):
        source = 'caribbeancom.com'
        values = {
            '[CARIB] 082920_001   (high) 3 haha 5':
            ('082920-001-carib-high-3', '未来のきもち', 1598659200),
            '120313_001 人 3': ('120313-001-carib', '麻倉憂', 1385683200),
        }
        self._run_test(values, source)

    def test_caribpr(self):
        source = 'caribbeancompr.com'
        values = {
            '[HD]022114_777-caribpr-mid haha 5':
            ('022114_777-caribpr-mid', 'レッドホット', 1392940800),
            '090613_656-caribpr-whole1-hd':
            ('090613_656-caribpr-whole1-hd', '全裸家政婦', 1378425600)
        }
        self._run_test(values, source)

    def test_1pon(self):
        source = '1pondo.tv'
        values = {
            '010617-460 1pon [1080p]':
            ('010617_460-1pon-1080p', '鈴木さとみ', 1483660800)
        }
        self._run_test(values, source)

    def test_10mu(self):
        source = '10musume.com'
        values = {
            '083014_01-10mu-whole1-psp':
            ('083014_01-10mu-whole1-psp', '主人様', 1409356800)
        }
        self._run_test(values, source)

    def test_paco(self):
        source = 'pacopacomama.com'
        values = {
            '(pacopacomama) 071219-130': ('071219_130-paco', '鈴木', 1562889600),
            '120618_394': ('120618_394-paco', '尾上若葉', 1544054400),
            '030417_040-paco': ('030417_040-paco', '熟女', 1488585600)
        }
        self._run_test(values, source)

    def test_mura(self):
        source = 'muramura.tv'
        values = {'010216_333-mura': ('010216_333-mura', '美巨乳女優', 1451692800)}
        self._run_test(values, source)

    def test_heyzo(self):
        source = 'heyzo.com'
        values = {
            '(heyzo) 1888': ('HEYZO-1888', '芸能人', 1545436800),
            'heyzo-0755-c': ('HEYZO-0755-C', '彼氏目線', 1419465600),
            'HEYZO-0947': ('HEYZO-0947', '美人姉妹', 1441756800),
        }
        self._run_test(values, source)

    def test_heydouga(self):
        source = 'heydouga.com'
        values = {
            'heydouga 4197-001-3': ('heydouga-4197-001-3', '梨香', 1542931200),
            'Heydouga 4030-PPV1768':
            ('heydouga-4030-1768', '立花美涼', 1448150400),
            'Heydouga 4030-PPV2232 AV9898':
            ('heydouga-4030-2232', '極射', 1553904000),
            'AV9898-1566': ('AV9898-1566', '前田由美', 1452643200),
            'honnamatv-216 (5)': ('honnamatv-216-5', 'M顔娘', 1380585600)
        }
        self._run_test(values, source)

    def test_h4610(self):
        source = 'h4610.com'
        values = {'H4610 gol185': ('H4610-gol185', '美加子', 1497052800.0)}
        self._run_test(values, source)

    def test_c0930(self):
        source = 'c0930.com'
        values = {'C0930-gol0136': ('C0930-gol0136', '羽田', 1456358400.0)}
        self._run_test(values, source)

    def test_h0930(self):
        source = 'h0930.com'
        values = {'H0930 (ori1575)': ('H0930-ori1575', '33歳', 1593216000.0)}
        self._run_test(values, source)

    def test_x1x(self):
        source = 'x1x.com'
        values = {
            'x1x-111815 一ノ瀬アメリ': ('x1x-111815', '50連発', 1396483200),
            'x1x.com 111860': ('x1x-111860', '一ノ瀬アメリ', 1332374400),
        }
        self._run_test(values, source)

    def test_smmiracle(self):
        source = 'sm-miracle.com'
        values = {'sm miracle e0689': ('sm-miracle-e0689', '黒髪の地方令嬢２', None)}
        self._run_test(values, source)

    def test_fc2(self):
        source = 'fc2.com'
        values = {
            'FC2-PPV-1021420_3': ('FC2-1021420-3', '32歳', 1548201600),
        }
        self._run_test(values, source)

    def test_kin8(self):
        source = 'kin8tengoku.com'
        values = {
            'kin8-3039': ('kin8-3039', 'MASSAGE', 1548892800),
            'Kin8tengoku 3329': ('kin8-3329', '肉感', 1607558400)
        }
        self._run_test(values, source)

    def test_girlsdelta(self):
        source = 'girlsdelta.com'
        values = {'GirlsDelta 1706': ('GirlsDelta-1706', '安原舞葉', 1651881600)}
        self._run_test(values, source)

    def test_mgs(self):
        source = 'mgstage.com'
        values = {
            'siro-1204': ('SIRO-1204', '体験撮影438', 1349136000),
            'DANDY-241': ('DANDY-241', '風呂', 1308355200.0)
        }
        self._run_test(values, source)

    def test_date(self):
        source = 'date string'
        values = {
            'Ray Milf  28Jul2015 1080p': 1438041600,
            'welivetogether.15.08.20.daisy.summers': 1440028800,
            'welivetogether 23-jun 2014 test': 1403481600,
            'welivetogether dec.23.2014 test': 1419292800,
            'deeper.20.03.14.rae.lil.black': 1584144000,
            'march 14, 2012': 1331683200,
            '20-03.14': None,
        }
        for k, v in values.items():
            result = scraper.scrape(k)
            if v is None:
                self.assertIsNone(result)
            else:
                self.assertEqual(v, result.publish_date)
                self.assertEqual(source, result.source)


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


if __name__ == '__main__':
    unittest.main()