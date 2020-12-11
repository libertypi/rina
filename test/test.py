#!/usr/bin/env python3

if __name__ != "__main__":
    raise ImportError("Test file should not be imported.")

import sys
import unittest
from dataclasses import astuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from avinfo import actress, scraper, video


class Scraper(unittest.TestCase):
    def _run_test(self, values):
        for string, answer in values:
            result = scraper.from_string(string)
            if result:
                result = astuple(result)
            self.assertEqual(result, answer, msg=result)

    def test_javbus(self):
        values = (
            ("CZ016 vol.3", ("javbus.com", "CZ016-3", "出合い頭4秒ファック！ : Part-2", 1504569600.0)),
            (
                "SMbd-110 s 2 model 3",
                (
                    "javbus.com",
                    "SMBD-110",
                    "S Model 110 オーバーサイズBlack Fuck 激カワアナルメイド : 小西まりえ (ブルーレイディスク版)",
                    1412985600.0,
                ),
            ),
            ("bouga012 [cd2]", ("javbus.com", "bouga012-2", "忘我素人パイパンおさな妻浣腸2穴依頼調教", 1496275200.0)),
            (
                "150605-KURUMI_KUMI",
                ("javbus.com", "150605-KURUMI_KUMI", "レズフェティシズム 〜ドレス姿の美麗レズカップルがイチャイチャ〜", 1433462400.0),
            ),
        )
        self._run_test(values)

    def test_javdb(self):
        values = (
            ("FC2-1201745", ("javdb.com", "FC2-1201745", "シルクストッキングをテストするために女の子を雇います。", 1573776000.0)),
            (
                "XXX-AV-20761",
                ("javdb.com", "XXX-AV-20761", "朝倉ことみ 中野ありさ 救マン病棟でハーレム大乱交！フルハイビジョン vol.03", 1579219200.0),
            ),
            (
                "XXXAV 20879",
                ("javdb.com", "XXX-AV-20879", "朝倉ことみ 発情歯科衛生士～僕だけのいいなり天使 フルハイビジョン ｖｏｌ.０１", 1565654400.0),
            ),
        )
        self._run_test(values)

    def test_carib(self):
        values = (
            (
                "[CARIB] 082920_001   (high) 3 haha 5",
                ("caribbeancom.com", "082920-001-carib-high-3", "未来のきもち 〜衰えた性欲が一気に取り戻せる乳首ンビンセラピー〜", 1598659200.0),
            ),
            (
                "[HD]022114_777-caribpr-mid haha 5",
                ("caribbeancompr.com", "022114_777-caribpr-mid", "レッドホットフェティッシュコレクション 108", 1392940800),
            ),
            (
                "120313_001 人 3",
                ("caribbeancom.com", "120313-001-carib", "麻倉憂未公開映像 尻コキ編", 1385683200.0),
            ),
        )
        self._run_test(values)

    def test_1pon(self):
        values = (
            (
                "010617-460 1pon [1080p]",
                ("1pondo.tv", "010617_460-1pon-1080p", "鈴木さとみ 〜ファン感謝祭素人宅訪問〜", 1483660800.0),
            ),
        )
        self._run_test(values)

    def test_10mu(self):
        values = (
            (
                "083014_01-10mu-whole1-psp",
                ("10musume.com", "083014_01-10mu-whole1-psp", "気持ちイイですかご主人様♪", 1409356800.0),
            ),
        )
        self._run_test(values)

    def test_paco(self):
        values = (
            (
                "(pacopacomama) 071219-130",
                ("pacopacomama.com", "071219_130-paco", "鈴木さとみの全て", 1562889600.0),
            ),
            ("120618_394", ("pacopacomama.com", "120618_394-paco", "尾上若葉の全て", 1544054400.0)),
            (
                "030417_040-paco",
                ("pacopacomama.com", "030417_040-paco", "スッピン熟女 〜素顔美人の黒マンコ〜", 1488585600.0),
            ),
        )
        self._run_test(values)

    def test_mura(self):
        values = (
            (
                "010216_333-mura",
                (
                    "muramura.tv",
                    "010216_333-mura",
                    "ラッキーホール新装開店!スレンダー美巨乳女優の初体験 壁の穴から突き出される顔も知らない男のイチモツをしゃぶり尽くす",
                    1451692800.0,
                ),
            ),
        )
        self._run_test(values)

    def test_heyzo(self):
        values = (
            ("(heyzo) 1888", ("heyzo.com", "HEYZO-1888", "Z～元芸能人の美エロボディ～", 1545436800.0)),
            (
                "heyzo-0755-c",
                ("heyzo.com", "HEYZO-0755-C", "クリスマスは二人で～ロリカワ彼女と彼氏目線でSEX～", 1419465600.0),
            ),
        )
        self._run_test(values)

    def test_heydouga(self):
        values = (
            (
                "heydouga 4017-257-3",
                (
                    "heydouga.com",
                    "heydouga-4017-257-3",
                    "ヤバっ！超気持ちいい〜!!お乳とおマ○コがズラリ…全裸でおっぱい姫が抜きまくり！夢の中出しハーレム - 素人りんか 素人かなみ 素人てぃな",
                    1519862400,
                ),
            ),
            ("honnamatv-216 (5)", ("heydouga.com", "honnamatv-216-5", "じゅんこ 激ヤセ！M顔娘", 1380585600)),
            (
                "heydouga-4197-001",
                ("heydouga.com", "heydouga-4197-001", "刺激を求めて応募の梨香さん、おじさんの3Ｐと中出し - 梨香", 1542931200.0),
            ),
        )
        self._run_test(values)

    def test_h4610(self):
        values = (
            ("H4610 gol185", ("h4610.com", "h4610-gol185", "葉月 美加子 23歳", 1497052800)),
            ("C0930-gol0136", ("c0930.com", "c0930-gol0136", "羽田 まなみ 25歳", 1456358400)),
            ("H0930 (ori1575)", ("h0930.com", "h0930-ori1575", "吉間 智保 33歳", 1593216000)),
        )
        self._run_test(values)

    def test_x1x(self):
        values = (
            (
                "x1x-111815 一ノ瀬アメリ",
                ("x1x.com", "x1x-111815", "一ノ瀬アメリ - THE一ノ瀬アメリ ぶっかけ50連発！", 1396483200.0),
            ),
        )
        self._run_test(values)

    def test_smmiracle(self):
        values = (("sm miracle e0689", ("sm-miracle.com", "sm-miracle-e0689", "黒髪の地方令嬢２", None)),)
        self._run_test(values)

    def test_fc2(self):
        values = (
            (
                "fc2-340671",
                ("fc2.com", "FC2-340671", "【激シコ美人】かわいくてエロくてマン汁たっぷりのゆうこ18歳にたっぷり中出し", 1542585600.0),
            ),
            (
                "FC2-PPV-1380738_3",
                (
                    "fc2.com",
                    "FC2-1380738-3",
                    "【個人撮影】消費者金融で借りた50万を旦那に内緒で返済する円光人妻！・旦那にバレるのが怖くて...他人の肉棒をぶち込まれ中出し",
                    1590192000,
                ),
            ),
            ("FC2-PPV-1187535", ("fc2.com", "FC2-1187535", "【個人撮影】ゆずき23歳 ショートSEX", 1579132800.0)),
        )
        self._run_test(values)

    def test_date(self):
        values = (
            ("Devon Ray Milf Teen Cum Swap 28Jul2015 1080p", ("date string", None, None, 1438041600.0)),
            ("welivetogether.15.08.20.abigail.mac.and.daisy.summers", ("date string", None, None, 1440028800)),
            ("welivetogether 23-jun 2014 test", None),
            ("welivetogether dec.23.2014 test", ("date string", None, None, 1419292800)),
            ("deeper.20.03.14.rae.lil.black", ("date string", None, None, 1584144000)),
        )
        self._run_test(values)


class Actress(unittest.TestCase):
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
            ("上原志織", ("上原志織", "1990-05-01", {"上原結衣", "上原志織", "しおり", "斉藤美穂"})),
        )
        self._do_test(wiki, values)

    def test_avrevolution(self):
        wiki = actress.AVRevolution
        values = (
            ("真央", ("知念真桜", None, {"井原のえる", "まお", "佐藤夏美", "羽田まなみ", "知念真央", "真央", "知念真桜"})),
            ("池田美和子", ("篠田あゆみ", None, {"池田美和子", "菊池紀子", "篠田あゆみ"})),
            ("蓮美", ("鈴木ありさ", None, {"鈴木ありさ", "藤槻ありさ", "大高頼子", "蓮美"})),
            ("市川サラ", ("市川サラ", None, {"市川サラ"})),
            ("伊藤ゆう", None),
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
            (
                "成宮はるあ",
                ("乃木はるか", "1992-07-30", {"春宮はるな", "葵律", "東美奈", "一ノ木ありさ", "陽咲希美", "芦原亮子", "乃木はるか", "深山梢", "成宮はるあ"}),
            ),
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
            ("鈴木ありさ", ("大高頼子", "1983-01-28", {"蓮美", "大高頼子", "藤槻ありさ", "鈴木ありさ"})),
            ("白鳥みなみ", ("白鳥みなみ", "1988-04-02", {"白鳥みなみ"})),
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

    def test_clean_name(self):
        values = (
            " 木内亜美菜[xxx] abc",
            "xxx) 木内亜美菜 [abc",
            "[xxx] 木内亜美菜 (abc)",
            "    木内亜美菜   　 (abc ~",
            " xxx]木内亜美菜27歳 (abc)",
        )
        for string in values:
            result = actress._clean_name(string)
            self.assertEqual(result, "木内亜美菜", msg=string)


class Files(unittest.TestCase):
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
            ("", "日" * 300, None),
            ("", "abc" * 300, None),
            ("", "a" * 300 + " a", None),
            ("", " " + "a" * 300, None),
        )
        path = Path("test.Mp4")
        for productId, title, answer in values:
            result = self.DuckAVFile(
                path=path,
                productId=productId,
                title=title,
            )._get_filename(namemax=255)
            if answer:
                self.assertEqual(result, answer, msg=result)
            self.assertLessEqual(len(result.encode("utf-8")), 255)
            self.assertRegex(result, r"\w+")


unittest.main()
