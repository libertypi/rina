#!/usr/bin/env python3

import sys
import unittest
from dataclasses import astuple
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from avinfo import actress, videoscraper
else:
    raise ImportError("Test file should only be launch directly.")


class ScraperTest(unittest.TestCase):
    def test_standardize_id(self):
        values = (
            ("[carib]022716_253 (high) 3 haha 5 放課後のリフレクソロジー 5", "022716_253-carib-high-3"),
            ("[HD](carib)022716-253 1080p haha 5 ", "022716_253-carib-1080p"),
        )
        scraper = videoscraper.Scraper
        for string, answer in values:
            result = scraper(string)._standardize_id()
            self.assertEqual(result, answer)

    def test_get_video_suffix(self):
        values = (
            ("sdmt-775 2 まさかのav出演", "sdmt-775", "2"),
            ("heydouga 4017-261-3", "heydouga-4017-261", "3"),
            ("smbd-110 s 2 model 3", "smbd-110", None),
            ("fc2-ppv-1395289_3", "fc2-1395289", "3"),
            ("h0930-ki200705[cd2]", "ki200705", "2"),
            ("kbi-042 (5)", "kbi-042", "5"),
            ("tki-069 人 3", "tki-069", None),
            ("heyzo-1888-c 青山はな", "heyzo-1888", "C"),
        )
        scraper = videoscraper.Scraper
        for string, keyword, answer in values:
            result = scraper(string, keyword=keyword)._get_video_suffix()
            self.assertEqual(result, answer)

    def test_javbus(self):
        values = (
            ("abs-047", False, ("ABS-047", "一泊二日、美少女完全予約制。 上原瑞穂", 1319241600.0, None, None)),
            ("120618_394", True, ("120618_394", "尾上若葉の全て", 1544054400.0, None, None)),
            ("081020_001", False, ("081020_001", "朝ゴミ出しする近所の遊び好きノーブラ奥さん 青山未来", 1597017600.0, None, None)),
        )
        scraper = videoscraper.Scraper
        for keyword, uncensored_only, answer in values:
            keyword = keyword.lower()
            result = scraper(keyword, keyword=keyword, uncensored_only=uncensored_only)._javbus()
            result = astuple(result) if result else None
            self.assertEqual(result, answer, msg=result)

    def test_javdb(self):
        values = (
            ("abs-047", ("ABS-047", "一泊二日、美少女完全予約制。 9", 1316649600.0, None, None)),
            ("120618_394", ("120618_394", "尾上若葉の全てシリーズ特設", 1544054400.0, None, None)),
        )
        scraper = videoscraper.Scraper
        for keyword, answer in values:
            result = scraper(keyword, keyword=keyword)._javdb()
            result = astuple(result) if result else None
            self.assertEqual(result, answer, msg=result)

    def _run_test(self, scraper, values):
        for string, answer in values:
            result = scraper.run(string.lower())
            result = astuple(result) if result else None
            self.assertEqual(result, answer, msg=result)

    def test_carib(self):
        values = (
            (
                "082920_001-carib-1080p",
                (
                    "082920_001-carib-1080p",
                    "未来のきもち 〜衰えた性欲が一気に取り戻せる乳首ンビンセラピー〜",
                    1598659200.0,
                    "caribbeancom.com",
                    "Product ID",
                ),
            ),
            (
                "062317_001-caribpr",
                ("062317_001-caribpr", "S Model 172 オフィスレディーの社内交尾", 1498176000.0, "caribbeancompr.com", "Product ID"),
            ),
        )
        self._run_test(videoscraper.Carib, values)

    def test_fc2(self):
        values = (
            (
                "fc2-340671",
                ("FC2-340671", "【激シコ美人】かわいくてエロくてマン汁たっぷりのゆうこ18歳にたっぷり中出し", 1542585600.0, "fc2.com", "fc2.com"),
            ),
        )
        self._run_test(videoscraper.FC2, values)

    def test_scrape(self):
        values = (
            ("sm miracle e0689", ("sm-miracle-e0689", "黒髪の地方令嬢２", None, "sm-miracle.com", None)),
            (
                "022114_777-caribpr-mid",
                ("022114_777-caribpr-mid", "レッドホットフェティッシュコレクション 108", 1392940800, "caribbeancompr.com", "Product ID"),
            ),
            ("CZ016 出合い頭4秒", ("CZ016", "出合い頭4秒ファック！ : Part-2", 1504569600, "javbus.com", "javbus.com")),
            (
                "072816_001-caribpr-high",
                ("072816_001-caribpr-high", "続々生中〜ロリ美少女をハメまくる〜", 1469664000, "caribbeancompr.com", "Product ID"),
            ),
            (
                "022418_01-10mu-1080p",
                ("022418_01-10mu-1080p", "制服時代 〜スカートが短くて恥かしい〜", 1519430400, "javbus.com", "Product ID"),
            ),
            (
                "FC2-1380738",
                (
                    "FC2-1380738",
                    "【個人撮影】消費者金融で借りた50万を旦那に内緒で返済する円光人妻！・旦那にバレるのが怖くて...他人の肉棒をぶち込まれ中出し",
                    1590192000,
                    "fc2.com",
                    "fc2.com",
                ),
            ),
            ("FC2-PPV-1187535", ("FC2-1187535", "【個人撮影】ゆずき23歳 ショートSEX", 1579132800.0, "fc2.com", "fc2.com")),
            ("H4610 gol185", ("h4610-gol185", "葉月 美加子 23歳", 1497052800, "h4610.com", "h4610.com")),
            ("C0930-gol0136", ("c0930-gol0136", "羽田 まなみ 25歳", 1456358400, "c0930.com", "c0930.com")),
            ("H0930 (ori1575)", ("h0930-ori1575", "吉間 智保 33歳", 1593216000, "h0930.com", "h0930.com")),
            (
                "x1x-111815 一ノ瀬アメリ",
                ("x1x-111815", "一ノ瀬アメリ - THE一ノ瀬アメリ ぶっかけ50連発！", 1396483200.0, "x1x.com", "x1x.com"),
            ),
            ("112118_772-1pon", ("112118_772-1pon", "パンツを脱いでもメガネは外しません〜家庭教師〜", 1542758400, "javbus.com", "Product ID")),
            (
                "160122_1020_01-mesubuta",
                ("160122_1020_01-mesubuta", "【惨虐】狙われた女子校生", 1453420800, "javbus.com", "Product ID"),
            ),
            (
                "1000Giri-151127 kurumi-HD",
                ("151127-KURUMI", "純コス☆ 清楚なホテルコンセルジュが制服脱いでエッチなサービス", 1448582400, "javbus.com", "javbus.com"),
            ),
            (
                "th101-000-110888",
                ("th101-000-110888", "サンタクロースは篠めぐみ！？ ～お宅訪問3軒～", 1514073600, "javbus.com", "javbus.com"),
            ),
            (
                "mkbd-s117 kirari 117",
                (
                    "MKBD-S117",
                    "KIRARI 117 極選！中出しイカセ~大物女優15名3時間メガ盛りMAX~ : 有賀ゆあ, 水樹りさ, 宮下華奈, 総勢15名 (ブルーレイ版)",
                    1449100800,
                    "javbus.com",
                    "javbus.com",
                ),
            ),
            ("n0584 絶品餌食過剰中出し重篤汁", ("n0584", "絶品餌食過剰中出し重篤汁", 1288310400, "javbus.com", "javbus.com")),
            (
                "club00379hhb",
                (
                    "CLUB-379",
                    "完全盗撮 同じアパートに住む美人妻2人と仲良くなって部屋に連れ込んでめちゃくちゃセックスした件。其の九",
                    1493251200,
                    "javbus.com",
                    "javbus.com",
                ),
            ),
            (
                "smbd-94 s ",
                (
                    "SMBD-94",
                    "S Model 94 ベストセレクトヒッツ 3時間12本中出し : 上原結衣 (ブルーレイディスク版)",
                    1386979200,
                    "javbus.com",
                    "javbus.com",
                ),
            ),
            ("081018-724", ("081018-724", "女熱大陸 File.063", 1533859200.0, "javbus.com", "Product ID")),
            (
                "110614_729-carib-1080p",
                ("110614_729-carib-1080p", "尾上若葉にどっきり即ハメ！パート2", 1415232000, "caribbeancom.com", "Product ID"),
            ),
            ("heyzo-1888", ("HEYZO-1888", "Z～元芸能人の美エロボディ～ - 青山はな", 1545436800, "heyzo.com", "heyzo.com")),
            (
                "heydouga 4017-257",
                (
                    "heydouga-4017-257",
                    "ヤバっ！超気持ちいい〜!!お乳とおマ○コがズラリ…全裸でおっぱい姫が抜きまくり！夢の中出しハーレム - 素人りんか 素人かなみ 素人てぃな",
                    1519862400,
                    "heydouga.com",
                    "heydouga.com",
                ),
            ),
            ("honnamatv-216", ("honnamatv-216", "じゅんこ 激ヤセ！M顔娘", 1380585600, "heydouga.com", "heydouga.com")),
            ("deeper.20.03.14.rae.lil.black", (None, None, 1584144000, None, "File name")),
            ("welivetogether.15.08.20.abigail.mac.and.daisy.summers", (None, None, 1440028800, None, "File name")),
            ("welivetogether 23-jun 2014 test", (None, None, 1403481600, None, "File name")),
            ("welivetogether dec 23.2014 test", (None, None, 1419292800, None, "File name")),
        )
        for string, answer in values:
            result = videoscraper.scrape_string(string.lower(), error=False)
            result = astuple(result) if result else None
            self.assertEqual(result, answer, msg=result)


class ActressTest(unittest.TestCase):
    # def test_avrevolution(self):
    #     wiki = actress.AVRevolution
    #     values = (
    #         ("真央", ("知念真桜", None, {"井原のえる", "まお", "佐藤夏美", "羽田まなみ", "知念真央", "真央", "知念真桜"})),
    #         ("池田美和子", ("篠田あゆみ", None, {"池田美和子", "菊池紀子", "篠田あゆみ"})),
    #         ("蓮美", ("鈴木ありさ", None, {"鈴木ありさ", "藤槻ありさ", "大高頼子", "蓮美"})),
    #     )
    #     for searchName, answer in values:
    #         result = astuple(wiki.search(searchName))
    #         self.assertEqual(result, answer)

    def _do_test(self, wiki, values):
        for searchName, answer in values:
            result = wiki.search(searchName)
            if result:
                result = astuple(result)
            self.assertEqual(result, answer, msg=result)

    def test_wikipedia(self):
        wiki = actress.Wikipedia
        values = (
            ("鈴木さとみ", ("鈴木さとみ", "1988-09-09", {"鈴木さとみ", "浅田真美", "まお"})),
            ("佐々木愛美", None),
            ("碧しの", ("碧しの", "1990-09-08", {"碧しの", "中村遙香", "宮嶋あおい", "篠めぐみ", "山口裕未"})),
            ("池田美和子", ("篠田あゆみ", "1985-11-16", {"篠田あゆみ", "さつき", "みき", "ちかこ", "菊池紀子", "池田美和子"})),
            ("上原結衣", ("上原結衣", "1990-05-01", {"上原志織", "上原結衣"})),
        )
        self._do_test(wiki, values)

    def test_minnanoav(self):
        wiki = actress.MinnanoAV
        values = (
            ("片瀬瑞穂", ("成宮梓", "1993-04-12", {"成宮梓", "片瀬瑞穂", "前田ななみ"})),
            ("佐伯史華", ("佐々木愛美", "1992-07-14", {"佐伯史華", "佐々木愛美", "クルミ"})),
            ("蓮美", None),
            ("佐伯史華", ("佐々木愛美", "1992-07-14", {"佐伯史華", "クルミ", "佐々木愛美"})),
            ("上原志織", ("上原志織", "1990-05-01", {"上原結衣", "上原志織", "しおり", "斉藤美穂"})),
        )
        self._do_test(wiki, values)

    def test_seesaawiki(self):
        wiki = actress.Seesaawiki
        values = (
            (
                "田中志乃",
                (
                    "桃井杏南",
                    "1988-03-31",
                    {"さとうみつ", "田中志乃", "七草アンナ", "茉莉もも", "桃井アンナ", "辰巳ゆみ", "桃井杏南", "七草まつり", "藤野あや", "水野ふうか"},
                ),
            ),
            ("上原結衣", ("上原志織", "1989-10-10", {"上原志織", "上原結衣"})),
            ("篠田あゆみ", ("篠田あゆみ", "1985-11-16", {"池田美和子", "菊池紀子", "篠田あゆみ"})),
            ("池田美和子", None),
        )
        self._do_test(wiki, values)

    def test_msin(self):
        wiki = actress.Msin
        values = (
            (
                "木内亜美菜",
                (
                    "木内亜美菜",
                    "1991-11-30",
                    {"佐々木ゆき", "モモ", "葉月美加子", "さくらあきな", "明菜", "ナナ", "あみな", "木内亜美菜", "廣井美加子", "咲羽", "りほ"},
                ),
            ),
            ("今村ゆう", ("沖野るり", "1996-03-15", {"有吉めぐみ", "今村ゆう", "吾妻絵里", "生駒なお", "夏目陽菜", "笠原佐智子", "沖野るり", "野本カノ"})),
            ("前田ななみ", ("片瀬瑞穂", "1993-04-12", {"成宮梓", "前田ななみ", "片瀬瑞穂"})),
            ("鈴木ありさ", None),
        )
        self._do_test(wiki, values)

    def test_manko(self):
        wiki = actress.Manko
        values = (
            ("南星愛", ("南星愛", "1996-01-31", {"山城ゆうひ", "南星愛"})),
            ("小司あん", ("平子知歌", None, {"小司あん", "平子知歌", "佐々木ゆう", "あん", "いしはらさき"})),
        )
        self._do_test(wiki, values)

    def test_etigoya(self):
        wiki = actress.Etigoya
        values = (
            ("市原さとみ", (None, None, {"西村江梨", "鶴田沙織", "由宇", "市原さとみ", "じゅんこ", "北野景子"})),
            ("上原志織", (None, None, {"上原結衣", "上原志織"})),
            ("佐々木愛美", (None, None, {"佐々木愛美", "佐伯史華", "クルミ"})),
        )
        self._do_test(wiki, values)


unittest.main()
