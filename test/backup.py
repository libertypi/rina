#!/usr/bin/env python3

import unittest
from dataclasses import astuple
from pathlib import Path

from avinfo import idol, scraper, video


class Scraper(unittest.TestCase):

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

    def test_carib(self):
        values = {
            '[CARIB] 082920_001   (high) 3 haha 5':
            ('caribbeancom.com', '082920-001-carib-high-3',
             '未来のきもち 〜衰えた性欲が一気に取り戻せる乳首ンビンセラピー〜', 1598659200),
            '[HD]022114_777-caribpr-mid haha 5':
            ('caribbeancompr.com', '022114_777-caribpr-mid',
             'レッドホットフェティッシュコレクション 108', 1392940800),
            '120313_001 人 3': ('caribbeancom.com', '120313-001-carib',
                               '麻倉憂未公開映像 尻コキ編', 1385683200),
            '090613_656-caribpr-whole1-hd':
            ('caribbeancompr.com', '090613_656-caribpr-whole1-hd',
             'メルシーボークー DV 01 国宝級のおっぱい全裸家政婦', 1378425600)
        }
        self._run_test(values)

    def test_1pon(self):
        values = {
            '010617-460 1pon [1080p]': ('1pondo.tv', '010617_460-1pon-1080p',
                                        '鈴木さとみ 〜ファン感謝祭素人宅訪問〜', 1483660800)
        }
        self._run_test(values)

    def test_10mu(self):
        values = {
            '083014_01-10mu-whole1-psp':
            ('10musume.com', '083014_01-10mu-whole1-psp', '気持ちイイですかご主人様♪',
             1409356800)
        }
        self._run_test(values)

    def test_paco(self):
        values = {
            '(pacopacomama) 071219-130':
            ('pacopacomama.com', '071219_130-paco', '鈴木さとみの全て', 1562889600),
            '120618_394':
            ('pacopacomama.com', '120618_394-paco', '尾上若葉の全て', 1544054400),
            '030417_040-paco': ('pacopacomama.com', '030417_040-paco',
                                'スッピン熟女 〜素顔美人の黒マンコ〜', 1488585600)
        }
        self._run_test(values)

    def test_mura(self):
        values = {
            '010216_333-mura':
            ('muramura.tv', '010216_333-mura',
             'ラッキーホール新装開店!スレンダー美巨乳女優の初体験 壁の穴から突き出される顔も知らない男のイチモツをしゃぶり尽くす',
             1451692800)
        }
        self._run_test(values)

    def test_heyzo(self):
        values = {
            '(heyzo) 1888':
            ('heyzo.com', 'HEYZO-1888', 'Z～元芸能人の美エロボディ～', 1545436800),
            'heyzo-0755-c': ('heyzo.com', 'HEYZO-0755-C',
                             'クリスマスは二人で～ロリカワ彼女と彼氏目線でSEX～', 1419465600),
            'HEYZO-0947': ('heyzo.com', 'HEYZO-0947',
                           'Ｗエクスタシー！美人姉妹丼は極上の味２ 後編～女２・男４の６P三昧～', 1441756800),
            'heyzo 0706': ('heyzo.com', 'HEYZO-0706',
                           '鈴木さとみのイカセ方～ザーメンまみれのエロボディ～', 1413504000)
        }
        self._run_test(values)

    def test_heydouga(self):
        values = {
            'heydouga 4197-001-3':
            ('heydouga.com', 'heydouga-4197-001-3',
             '刺激を求めて応募の梨香さん、おじさんの3Ｐと中出し - 梨香', 1542931200),
            'Heydouga 4030-PPV1768':
            ('heydouga.com', 'heydouga-4030-1768',
             '夫婦喧嘩が原因で家出をしてきた隣の奥さん!! - 立花美涼', 1448150400),
            'Heydouga 4030-PPV2232 AV9898':
            ('heydouga.com', 'heydouga-4030-2232', '極射 - あすかみさき', 1553904000),
            'AV9898-1566': ('heydouga.com', 'AV9898-1566',
                            '前田由美 由美の家で撮影しちゃおう_Two', 1452643200),
            'honnamatv-216 (5)':
            ('heydouga.com', 'honnamatv-216-5', 'じゅんこ 激ヤセ！M顔娘', 1380585600)
        }
        self._run_test(values)

    def test_h4610(self):
        values = {
            'H4610 gol185':
            ('h4610.com', 'H4610-gol185', '葉月 美加子 23歳', 1497052800.0),
            'C0930-gol0136':
            ('c0930.com', 'C0930-gol0136', '羽田 まなみ 25歳', 1456358400.0),
            'H0930 (ori1575)':
            ('h0930.com', 'H0930-ori1575', '吉間 智保 33歳', 1593216000.0)
        }
        self._run_test(values)

    def test_x1x(self):
        values = {
            'x1x-111815 一ノ瀬アメリ':
            ('x1x.com', 'x1x-111815', 'THE一ノ瀬アメリ ぶっかけ50連発！', 1396483200),
            'x1x.com 111860':
            ('x1x.com', 'x1x-111860', '極上ボディー!!! 一ノ瀬アメリ', 1332374400)
        }
        self._run_test(values)

    def test_smmiracle(self):
        values = {
            'sm miracle e0689':
            ('sm-miracle.com', 'sm-miracle-e0689', '黒髪の地方令嬢２', None)
        }
        self._run_test(values)

    def test_fc2(self):
        values = {
            'fc2-340671':
            ('fc2.com', 'FC2-340671', '【激シコ美人】かわいくてエロくてマン汁たっぷりのゆうこ18歳にたっぷり中出し',
             1542585600),
            'FC2-PPV-1380738_3':
            ('fc2.com', 'FC2-1380738-3',
             '【個人撮影】消費者金融で借りた50万を旦那に内緒で返済する円光人妻！・旦那にバレるのが怖くて...他人の肉棒をぶち込まれ中出し',
             1590192000),
            'FC2-PPV-1187535':
            ('fc2.com', 'FC2-1187535', '【個人撮影】ゆずき23歳 ショートSEX', 1579132800)
        }
        self._run_test(values)

    def test_kin8(self):
        values = {
            'kin8-3039':
            ('kin8tengoku.com', 'kin8-3039',
             'JAPANESE STYLE MASSAGE スレンダーチビマンロリBODYをジックリ弄ぶ VOL2 Nelya Petite / ネルヤ',
             1548892800),
            'Kin8tengoku 3329':
            ('kin8tengoku.com', 'kin8-3329',
             '肉感フェロモンちゃんのおまんこをじっくり観察 PUSSY COLLECTION プシコレ Mona Sweet / モナ スイート',
             1607558400)
        }
        self._run_test(values)

    def test_girlsdelta(self):
        values = {
            'GirlsDelta 872':
            ('girlsdelta.com', 'GirlsDelta-872', 'MAHIRO 柚木まひろのワレメ', None)
        }
        self._run_test(values)

    def test_mgs(self):
        values = {
            'siro-1204':
            ('mgstage.com', 'SIRO-1204', '素人AV体験撮影438', 1349136000),
            'DANDY-241':
            ('mgstage.com', 'DANDY-241',
             '「昼間から風呂に入っている湯上がり美人妻がしかける火照った体を見せつけながら密着してくる誘惑サインを見逃すな！」 VOL.2',
             1308355200.0)
        }
        self._run_test(values)

    def test_onekgirl(self):
        values = {
            '150605-KURUMI_KUMI':
            ('javbus.com', '150605-KURUMI_KUMI',
             'レズフェティシズム 〜ドレス姿の美麗レズカップルがイチャイチャ〜', 1433462400),
            '150626 KURUMI': ('javbus.com', '150626-KURUMI',
                              'めっちゃしたい！！改#124 〜アイドル級美少女の知られざる実態〜', 1435276800)
        }
        self._run_test(values)

    def test_date(self):
        values = {
            'Devon Ray Milf Teen Cum Swap 28Jul2015 1080p':
            ('date string', None, None, 1438041600),
            'welivetogether.15.08.20.abigail.mac.and.daisy.summers':
            ('date string', None, None, 1440028800),
            'welivetogether 23-jun 2014 test':
            ('date string', None, None, 1403481600),
            'welivetogether dec.23.2014 test':
            ('date string', None, None, 1419292800),
            'deeper.20.03.14.rae.lil.black': ('date string', None, None,
                                              1584144000),
            'march 14, 2012': ('date string', None, None, 1331683200),
            '20-03.14':
            None
        }
        self._run_test(values)


class Actress(unittest.TestCase):

    def _run_test(self, wiki, values: dict):
        for searchName, answer in values.items():
            result = wiki.search(searchName)
            if result:
                result = astuple(result)
            self.assertEqual(result, answer, msg=result)

    def test_wikipedia(self):
        wiki = idol.Wikipedia
        values = {
            '鈴木さとみ': ('鈴木さとみ', '1988-09-09', {'鈴木さとみ', 'まお', '浅田真美'}),
            '佐々木愛美':
            None,
            '碧しの':
            ('碧しの', '1990-09-08', {'宮嶋あおい', '山口裕未', '碧しの', '篠めぐみ', '中村遙香'}),
            '池田美和子': ('篠田あゆみ', '1985-11-16',
                      {'篠田あゆみ', 'さつき', 'ちかこ', 'みき', '菊池紀子', '池田美和子'}),
            '上原結衣': ('上原結衣', '1990-05-01', {'上原志織', '上原結衣'})
        }
        self._run_test(wiki, values)

    def test_minnanoav(self):
        wiki = idol.MinnanoAV
        values = {
            '片瀬瑞穂': ('成宮梓', '1993-04-12', {'片瀬瑞穂', '前田ななみ', '成宮梓'}),
            '佐伯史華': ('佐々木愛美', '1992-07-14', {'クルミ', '佐伯史華', '佐々木愛美'}),
            '蓮美': None,
            '上原志織': ('上原志織', '1990-05-01', {'しおり', '上原志織', '斉藤美穂', '上原結衣'})
        }
        self._run_test(wiki, values)

    def test_avrevolution(self):
        wiki = idol.AVRevolution
        values = {
            '真央': ('知念真桜', None,
                   {'まお', '佐藤夏美', '羽田まなみ', '知念真央', '井原のえる', '真央', '知念真桜'}),
            '池田美和子': ('篠田あゆみ', None, {'篠田あゆみ', '菊池紀子', '池田美和子'}),
            '蓮美': ('鈴木ありさ', None, {'蓮美', '大高頼子', '藤槻ありさ', '鈴木ありさ'}),
            '市川サラ': ('市川サラ', None, {'市川サラ'}),
            '伊藤ゆう':
            None
        }
        self._run_test(wiki, values)

    def test_seesaawiki(self):
        wiki = idol.Seesaawiki
        values = {
            '田中志乃': ('桃井杏南', '1988-03-31', {
                '茉莉もも', '田中志乃', 'さとうみつ', '辰巳ゆみ', '水野ふうか', '七草まつり', '藤野あや',
                '桃井杏南', '七草アンナ', '桃井アンナ'
            }),
            '上原結衣': ('上原志織', '1989-10-10', {'上原志織', '上原結衣'}),
            '篠田あゆみ': ('篠田あゆみ', '1985-11-16', {'篠田あゆみ', '菊池紀子', '池田美和子'}),
            '池田美和子':
            None,
            '成宮はるあ': ('乃木はるか', '1992-07-30', {
                '一ノ木ありさ', '深山梢', '乃木はるか', '葵律', '芦原亮子', '春宮はるな', '東美奈',
                '成宮はるあ', '陽咲希美'
            })
        }
        self._run_test(wiki, values)

    def test_msin(self):
        wiki = idol.Msin
        values = {
            '木内亜美菜': ('木内亜美菜', '1991-11-30', {
                '咲羽', 'りほ', 'モモ', '佐々木ゆき', '木内亜美菜', 'ナナ', '葉月美加子', '廣井美加子',
                'あみな', '明菜', 'さくらあきな'
            }),
            '今村ゆう': ('沖野るり', '1996-03-15', {
                '有吉めぐみ', '吾妻絵里', '野本カノ', '生駒なお', '夏目陽菜', '沖野るり', '今村ゆう',
                '笠原佐智子'
            }),
            '前田ななみ': ('片瀬瑞穂', '1993-04-12', {'片瀬瑞穂', '前田ななみ', '成宮梓'}),
            '鈴木ありさ': ('大高頼子', '1983-01-28', {'藤槻ありさ', '大高頼子', '蓮美', '鈴木ありさ'}),
            '白鳥みなみ': ('白鳥みなみ', '1988-04-02', {'白鳥みなみ'})
        }
        self._run_test(wiki, values)

    def test_manko(self):
        wiki = idol.Manko
        values = {
            '南星愛': ('南星愛', '1996-01-31', {'南星愛', '山城ゆうひ'}),
            '小司あん': ('平子知歌', None, {'佐々木ゆう', 'あん', 'いしはらさき', '小司あん', '平子知歌'})
        }
        self._run_test(wiki, values)

    def test_etigoya(self):
        wiki = idol.Etigoya
        values = {
            '市原さとみ':
            (None, None, {'じゅんこ', '市原さとみ', '鶴田沙織', '西村江梨', '由宇', '北野景子'}),
            '上原志織': (None, None, {'上原志織', '上原結衣'}),
            '佐々木愛美': (None, None, {'クルミ', '佐伯史華', '佐々木愛美'})
        }
        self._run_test(wiki, values)

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
        for product_id, title, answer in values:
            result = self.DuckAVFile(
                target=path,
                product_id=product_id,
                title=title,
            )._get_filename(namemax=255)
            if answer:
                self.assertEqual(result, answer, msg=result)
            self.assertLessEqual(len(result.encode("utf-8")), 255)
            self.assertRegex(result, r"\w+")


unittest.main()
