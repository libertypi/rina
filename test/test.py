import unittest

from dataclasses import astuple
from avinfo import idol, scraper, video, birth
from avinfo._utils import get_tree


class Test_Scraper(unittest.TestCase):

    def _run_test(self, values: dict):
        for string, answer in values.items():
            result = scraper.scrape(string)
            if result:
                result = astuple(result)
            self.assertEqual(result, answer, msg=result)

    def test_javbus(self):
        values = {
            'CZ016 vol.3':
            ('javbus.com', 'CZ016-3', '出合い頭4秒ファック！ : Part-2', 1504569600),
            'SMbd-110 s 2 model 3':
            ('javbus.com', 'SMBD-110',
             'S Model 110 オーバーサイズBlack Fuck 激カワアナルメイド : 小西まりえ (ブルーレイディスク版)',
             1412985600),
            'bouga012 [cd2]':
            ('javbus.com', 'bouga012-2', '忘我素人パイパンおさな妻浣腸2穴依頼調教', 1496275200),
            'n0253': ('javbus.com', 'n0253', '無料校内中出し用炉便器', 1188518400),
            'S2MBD-054': ('javbus.com', 'S2MBD-054',
                          'ボクのカテキョはビッチなエロギャル : 早川メアリー ( ブルーレイ版 )', 1467849600)
        }
        self._run_test(values)

    def test_javdb(self):
        values = {
            'FC2PPV 1201745': ('javdb.com', 'FC2-1201745',
                               'シルクストッキングをテストするために女の子を雇います。', 1573776000),
            'XXXAV 20879':
            ('javdb.com', 'XXX-AV-20879',
             '朝倉ことみ 発情歯科衛生士～僕だけのいいなり天使 フルハイビジョン ｖｏｌ.０１', 1565654400)
        }
        self._run_test(values)


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