#!/usr/bin/env python3

import unittest

from . import actress
from .files import AV, Scraper


class DuckFile(AV):
    def __init__(self, basename="", keyword=""):
        self.basename = basename.lower()
        self.keyword = keyword.lower()


class ScraperTest(unittest.TestCase):
    scraper = Scraper()

    def test_get_standard_product_id(self):
        values = (
            ("[carib]022716_253 (high) 3 haha 5 放課後のリフレクソロジー 5", "022716_253-carib-high-3",),
            ("[HD](carib)022716-253 1080p haha 5 ", "022716_253-carib-1080p",),
        )
        for basename, answer in values:
            result = self.scraper._get_standard_product_id(DuckFile(basename=basename))
            self.assertEqual(result, answer)

    def test_get_video_suffix(self):
        values = (
            ("sdmt-775 2 まさかのav出演", "sdmt-775", "2"),
            ("heydouga 4017-261-3", "heydouga-4017-261", "3"),
            ("smbd-110 s 2 model 3", "smbd-110", None),
            ("fc2-ppv-1395289_3", "fc2-1395289", "3"),
            ("h0930-ki200705[cd2]", "ki200705", "cd2"),
            ("kbi-042 (5)", "kbi-042", "5"),
            ("tki-069 人 3", "tki-069", None),
            ("heyzo-1888-c 青山はな", "heyzo-1888", "C"),
        )
        for basename, keyword, answer in values:
            result = self.scraper._get_video_suffix(DuckFile(basename=basename, keyword=keyword))
            self.assertEqual(result, answer)

    def test_javbus(self):
        values = (
            (
                "abs-047",
                False,
                {
                    "productId": "ABS-047",
                    "title": "一泊二日、美少女完全予約制。 上原瑞穂",
                    "publishDate": 1319241600,
                    "source": "JavBus",
                },
            ),
            (
                "120618_394",
                True,
                {"productId": "120618_394", "title": "尾上若葉の全て", "publishDate": 1544054400, "source": "JavBus"},
            ),
        )
        for keyword, uncensoredOnly, answer in values:
            result = self.scraper._javbus(DuckFile(keyword=keyword), uncensoredOnly)
            # print((keyword, uncensoredOnly, result), ",")
            self.assertEqual(result, answer)

    def test_javdb(self):
        values = (
            (
                "abs-047",
                {"productId": "ABS-047", "title": "一泊二日、美少女完全予約制。 9", "publishDate": 1316649600, "source": "JavDB"},
            ),
            (
                "120618_394",
                {"productId": "120618_394", "title": "尾上若葉の全てシリーズ特設", "publishDate": 1544054400, "source": "JavDB"},
            ),
        )
        for keyword, answer in values:
            result = self.scraper._javdb(DuckFile(keyword=keyword))
            # print((keyword, result), ",")
            self.assertEqual(result, answer)

    def test_scrape(self):
        values = (
            (
                "sm miracle e0689",
                {"productId": "sm-miracle-e0689", "title": "黒髪の地方令嬢２", "titleSource": "sm-miracle.com"},
            ),
            (
                "022114_777-caribpr-mid",
                {
                    "productId": "022114_777-caribpr-mid",
                    "title": "レッドホットフェティッシュコレクション 108",
                    "publishDate": 1392940800,
                    "titleSource": "caribbeancompr.com",
                    "dateSource": "Product ID",
                },
            ),
            (
                "CZ016 出合い頭4秒",
                {
                    "productId": "CZ016",
                    "title": "出合い頭4秒ファック！ : Part-2",
                    "publishDate": 1504569600,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "072816_001-caribpr-high",
                {
                    "productId": "072816_001-caribpr-high",
                    "title": "続々生中〜ロリ美少女をハメまくる〜",
                    "publishDate": 1469664000,
                    "titleSource": "caribbeancompr.com",
                    "dateSource": "Product ID",
                },
            ),
            (
                "022418_01-10mu-1080p",
                {
                    "productId": "022418_01-10mu-1080p",
                    "title": "制服時代 〜スカートが短くて恥かしい〜",
                    "publishDate": 1519430400,
                    "titleSource": "JavBus",
                    "dateSource": "Product ID",
                },
            ),
            (
                "FC2-1204745",
                {
                    "productId": "FC2-1204745",
                    "title": "川上奈奈美无码流出",
                    "publishDate": 1574380800,
                    "titleSource": "fc2club.com",
                    "dateSource": "fc2club.com",
                },
            ),
            (
                "FC2-1380738",
                {
                    "productId": "FC2-1380738",
                    "title": "【個人撮影】消費者金融で借りた50万を旦那に内緒で返済する円光人妻！・旦那にバレるのが怖くて...他人の肉棒をぶち込まれ中出し",
                    "publishDate": 1590192000,
                    "titleSource": "fc2.com",
                    "dateSource": "fc2.com",
                },
            ),
            (
                "FC2-PPV-1187535",
                {
                    "productId": "FC2-1187535",
                    "title": "【個人撮影】ゆずき23歳\u3000ショートSEX",
                    "publishDate": 1579132800,
                    "titleSource": "fc2.com",
                    "dateSource": "fc2.com",
                },
            ),
            (
                "H4610 gol185",
                {
                    "productId": "h4610-gol185",
                    "title": "葉月 美加子 23歳",
                    "publishDate": 1497052800,
                    "titleSource": "h4610.com",
                    "dateSource": "h4610.com",
                },
            ),
            (
                "C0930-gol0136",
                {
                    "productId": "c0930-gol0136",
                    "title": "羽田 まなみ 25歳",
                    "publishDate": 1456358400,
                    "titleSource": "c0930.com",
                    "dateSource": "c0930.com",
                },
            ),
            (
                "H0930 (ori1575)",
                {
                    "productId": "h0930-ori1575",
                    "title": "吉間 智保 33歳",
                    "publishDate": 1593216000,
                    "titleSource": "h0930.com",
                    "dateSource": "h0930.com",
                },
            ),
            (
                "x1x-111815 一ノ瀬アメリ",
                {
                    "productId": "x1x-111815",
                    "title": "一ノ瀬アメリ - THE一ノ瀬アメリ\u3000ぶっかけ50連発！",
                    "publishDate": 1396483200,
                    "titleSource": "x1x.com",
                    "dateSource": "x1x.com",
                },
            ),
            (
                "112118_772-1pon",
                {
                    "productId": "112118_772-1pon",
                    "title": "パンツを脱いでもメガネは外しません〜家庭教師〜",
                    "publishDate": 1542758400,
                    "titleSource": "JavBus",
                    "dateSource": "Product ID",
                },
            ),
            (
                "160122_1020_01-mesubuta",
                {
                    "productId": "160122_1020_01-mesubuta",
                    "title": "【惨虐】狙われた女子校生",
                    "publishDate": 1453420800,
                    "titleSource": "JavBus",
                    "dateSource": "Product ID",
                },
            ),
            (
                "1000Giri-151127 kurumi-HD",
                {
                    "productId": "151127-KURUMI",
                    "title": "純コス☆ 清楚なホテルコンセルジュが制服脱いでエッチなサービス",
                    "publishDate": 1448582400,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "th101-000-110888",
                {
                    "productId": "th101-000-110888",
                    "title": "サンタクロースは篠めぐみ！？ ～お宅訪問3軒～",
                    "publishDate": 1514073600,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "mkbd-s117 kirari 117",
                {
                    "productId": "MKBD-S117",
                    "title": "KIRARI 117 極選！中出しイカセ~大物女優15名3時間メガ盛りMAX~ : 有賀ゆあ, 水樹りさ, 宮下華奈, 総勢15名 (ブルーレイ版)",
                    "publishDate": 1449100800,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "n0584 絶品餌食過剰中出し重篤汁",
                {
                    "productId": "n0584",
                    "title": "絶品餌食過剰中出し重篤汁",
                    "publishDate": 1288310400,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "club00379hhb",
                {
                    "productId": "CLUB-379",
                    "title": "完全盗撮 同じアパートに住む美人妻2人と仲良くなって部屋に連れ込んでめちゃくちゃセックスした件。其の九",
                    "publishDate": 1493251200,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "smbd-94 s ",
                {
                    "productId": "SMBD-94",
                    "title": "S Model 94 ベストセレクトヒッツ 3時間12本中出し : 上原結衣 (ブルーレイディスク版)",
                    "publishDate": 1386979200,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "081018-724",
                {
                    "productId": "081018-724",
                    "title": "女熱大陸 File.063",
                    "publishDate": 1533859200,
                    "titleSource": "JavBus",
                    "dateSource": "JavBus",
                },
            ),
            (
                "110614_729-carib-1080p",
                {
                    "productId": "110614_729-carib-1080p",
                    "title": "尾上若葉にどっきり即ハメ！パート2",
                    "publishDate": 1415232000,
                    "titleSource": "caribbeancom.com",
                    "dateSource": "Product ID",
                },
            ),
            (
                "heyzo-1888",
                {
                    "productId": "HEYZO-1888",
                    "title": "Z～元芸能人の美エロボディ～ - 青山はな",
                    "publishDate": 1545436800,
                    "titleSource": "heyzo.com",
                    "dateSource": "heyzo.com",
                },
            ),
            (
                "heydouga 4017-257",
                {
                    "productId": "heydouga-4017-257",
                    "title": "ヤバっ！超気持ちいい〜!!お乳とおマ○コがズラリ…全裸でおっぱい姫が抜きまくり！夢の中出しハーレム - 素人りんか 素人かなみ 素人てぃな",
                    "publishDate": 1519862400,
                    "titleSource": "heydouga.com",
                    "dateSource": "heydouga.com",
                },
            ),
            (
                "honnamatv-216",
                {
                    "productId": "honnamatv-216",
                    "title": "じゅんこ 激ヤセ！M顔娘",
                    "publishDate": 1380585600,
                    "titleSource": "heydouga.com",
                    "dateSource": "heydouga.com",
                },
            ),
            ("deeper.20.03.14.rae.lil.black", {"publishDate": 1584144000, "dateSource": "File name"}),
            (
                "welivetogether.15.08.20.abigail.mac.and.daisy.summers",
                {"publishDate": 1440028800, "dateSource": "File name",},
            ),
            ("welivetogether 23-jun 2014 test", {"publishDate": 1403481600, "dateSource": "File name",},),
            ("welivetogether dec 23.2014 test", {"publishDate": 1419292800, "dateSource": "File name",},),
            (
                "mxbd-241_c",
                {
                    "productId": "MXBD-241-C",
                    "title": "新人 青山はな ～地方局の元お天気お姉さんAVデビュー！おま●こ洪水特別警報発令、桜の開花日直前にAVで一足早く花開く！！～ in HD（ブルーレイディスク）",
                    "publishDate": 1458086400,
                    "titleSource": "JavDB",
                    "dateSource": "JavDB",
                },
            ),
        )
        for basename, answer in values:
            result = self.scraper.scrape(DuckFile(basename=basename))
            # print((basename, result), ", ", sep="")
            self.assertEqual(result, answer)


class ActressTest(unittest.TestCase):
    def test_wikipedia(self):
        wikipedia = actress.Wikipedia(0)
        values = (
            ("鈴木さとみ", ("鈴木さとみ", "1988-09-09", {"鈴木さとみ", "浅田真美", "まお"})),
            ("佐々木愛美", None),
            ("碧しの", ("碧しの", "1990-09-08", {"碧しの", "中村遙香", "宮嶋あおい", "篠めぐみ", "山口裕未"})),
            ("池田美和子", ("篠田あゆみ", "1985-11-16", {"篠田あゆみ", "さつき", "みき", "ちかこ", "菊池紀子", "池田美和子"})),
            ("上原結衣", ("上原結衣", "1990-05-01", {"上原志織", "上原結衣"})),
        )
        for searchName, answer in values:
            result = wikipedia.search(searchName)
            # print((searchName, result), ", ", sep="")
            self.assertEqual(result, answer)

    def test_minnanoav(self):
        minnanoav = actress.MinnanoAV(0)
        values = (
            ("片瀬瑞穂", ("成宮梓", "1993-04-12", {"成宮梓", "片瀬瑞穂", "前田ななみ"})),
            ("佐々木愛美", ("佐々木愛美", "1992-07-14", {"クルミ", "佐々木愛美", "佐伯史華"})),
            ("池田美和子", ("篠田あゆみ", "1985-11-16", {"菊池紀子", "池田美和子", "さつき", "インセクター篠田", "ちかこ", "篠田あゆみ"})),
            ("上原結衣", ("上原志織", "1990-05-01", {"上原結衣", "上原志織", "しおり", "斉藤美穂"})),
        )
        for searchName, answer in values:
            result = minnanoav.search(searchName)
            # print((searchName, result), ", ", sep="")
            self.assertEqual(result, answer)

    def test_seesaawiki(self):
        seesaawiki = actress.Seesaawiki(0)
        values = (
            ("上原結衣", ("上原志織", "1989-10-10", {"上原志織", "上原結衣"})),
            ("池田美和子", ("篠田あゆみ", "1985-11-16", {"菊池紀子", "池田美和子", "篠田あゆみ"})),
        )
        for searchName, answer in values:
            result = seesaawiki.search(searchName)
            # print((searchName, result), ", ", sep="")
            self.assertEqual(result, answer)

    def test_manko(self):
        manko = actress.Manko(0)
        values = (
            ("南星愛", ("南星愛", "1996-01-31", {"山城ゆうひ", "南星愛"})),
            ("北条麻妃", ("北条麻妃", "1978-12-21", {"白石さゆり", "北条麻妃"})),
        )
        for searchName, answer in values:
            result = manko.search(searchName)
            # print((searchName, result), ", ", sep="")
            self.assertEqual(result, answer)


if __name__ == "__main__":
    unittest.main()
    # print()
    # test = unittest.TestSuite()
    # test.addTest(ActressTest())
    # unittest.TextTestRunner().run(test)
