#!/usr/bin/env python3
"""塞いだ穴がまた開いてないかの見張り（11/14 夜 オーナー「塞いだ穴がまた広がることはない？」）
直しの印（その直しにしか無い文字）がファイルに残っとるか・動きの試験が通るかを見る。毎時 friday-kenkou から呼ばれる。
開いた穴があれば 1行ずつ出して終わりの値 1（kenkou が LINE で1日1回知らせる）。直しを足したら ANA に1行足す。
穴が開く道＝①夜の直し係（4:45）が同じファイルを書き換える ②別のタブ・Codex が古い写しで上書きする ③.bak から戻す ④入口を古い src で公開する"""
import os, re, sys, json, subprocess, time
H = os.path.expanduser("~"); B = H + "/bin/"
ANA = [  # (ファイル, 残っとるはずの文字, 何の穴か)
 (B + "mimi-watch.py", "名前の頼み→返事係（聞き返し）", "耳：名前で呼ばれたら黙らず聞き返す（11/16）"),
 (B + "mimi-server.py", 'self.path.startswith("/ack")', "耳 v5：受け取りの音の受け口（11/16）"),
 (B + "mimi_filter.py", "DERA.search(t)", "耳：でたらめな外国語の段を捨てる（11/16）"),
 (H + "/friday-bot/src/index.js", "function oboe(", "入口：絵は N枚目として覚える（11/16 引用の絵が分からん）"),
 (B + "friday-send", '"nimg"', "送り口：絵の枚数を入口に伝える（11/16）"),
 (B + "friday-agent.py", "当て推量で進めん", "返事係：選択肢の後の「これ」は分からん時聞き返す（11/16）"),
 (B + "mimi-server.py", "koe_hon(path)", "耳：声紋の本人らしさ hon を区切りに付ける（11/16）"),
 (B + "mimi_filter.py", "def koe_shirushi(", "耳：声紋の印 👤／🔈（11/16）"),
 (B + "mimi-watch.py", "or HONNIN):", "耳：声紋が本人の声は上限で捨てん（11/16）"),
 (B + "mimi_kiku.py", 'JISHO = "フライデー、"', "耳：書き起こしに名前を先に教える（11/16 フライエー等 12/14 直った）"),
 (B + "mimi-watch.py", "送れん返事→返事係", "耳：本人の頼みへの返事が門で止まったら返事係へ渡す（11/15 23:01 黙って止めた）"),
 (B + "mimi-watch.py", 'if YOBI or TANO: cmd.append("--reply")', "耳：本人の頼みへの返事は1仕事1人の門を通らん（11/15）"),
 (B + "friday_hitori.py", "耳は iPhone のマイクの声を全部文字にして残しとる", "門：記録しております は本当（11/15）"),
 (B + "mimi_filter.py", "[さっ]といて", "耳：「記録さっといて」等を頼みとして拾う（11/15 22:50）"),
 (B + "mimi_filter.py", "[エレテ]ー|デイ", "耳：化けた名前「フライエー」等を拾う（11/15 22:01 Meta の頼みを捨てた）"),
 (B + "mimi_filter.py", "def toi(", "耳：質問の形は上限の後でも係に見せる（11/15 夜 4件捨てた）"),
 (B + "mimi-watch.py", "not (YOBI or TANO or TOI)", "耳：上限の後の質問を中身を見ずに捨てん（11/15）"),
 (B + "mimi-server.py", "x-ta", "耳 v4：動画が鳴っとった割合を受け取る（11/15）"),
 (B + "mimi-server.py", "app_conf.json", "耳 v4：声の処理のオン／オフを心拍で返す（11/15）"),
 (B + "mimi-watch.py", "douga", "耳 v4：動画の区切りに🎬を付けて本人の頼みと分ける（11/15）"),
 (B + "mimi-server.py", "hb_oto.jsonl", "耳 v4：心拍の中身（音の大きさ・送った/捨てた区切り）を毎分残す（11/15）"),
 (B + "mimi_filter.py", "avg_logprob", "耳：幻聴の門（自信の点）"),
 (B + "mimi_filter.py", "KIMARI", "耳：外でも出る決まり文句の幻聴"),
 (B + "mimi-server.py", "FILT.moji", "耳：受け口が共通の門を使う"),
 (B + "mimi-server.py", "mimi_kiku.py", "耳：聞く本体（声の有無の門・切り出し）を使う"),
 (B + "mimi_kiku.py", "get_speech_timestamps", "耳：声の有無の門（VAD）"),
 (B + "mimi_kiku.py", "def kiridashi", "耳：声の所だけ切り出して書き起こす"),
 (B + "mimi-shiken.py", "cases.json", "耳：毎朝の試験"),
 (B + "friday-kenkou.py", "耳の試験", "健康診断：試験の点を見る"),
 (B + "mimi-server.py", "def yarinaoshi", "耳：起こし直しで声が消えん（.meta）"),
 (B + "mimi_filter.py", "PARTNER", "耳：〈パートナー〉さんの話を伏せる"),
 (B + "mimi-server.py", "ISOGI.search", "耳：願いの言葉で先回りをすぐ起こす"),
 (B + "mimi_filter.py", "def bad(", "耳：句点つきの幻聴"),
 (B + "mimi-watch.py", '.local/bin/claude', "耳：すぐ起こした時に claude が見つかる"),
 (B + "mimi-watch.py", 'hb.get("v") not in ("2", "3")', "耳：本人が止めた時に「落ちた」と誤報せん"),
 (B + "mimi-watch.py", "mimi-watch.again", "耳：走っとる最中に来た声は終わった瞬間にもう1回"),
 (B + "mimi-watch.py", "名前で呼ばれた頼みは", "耳：フライデーと呼ばれた頼みは必ず受ける・EC の作業には反応せん"),
 (B + "mimi-watch.py", "調べを返事係へ", "耳：調べては確認なしで返事係へ"),
 (B + "mimi-watch.py", "friday_kane", "耳：カードの利用可能額は AI を起こさず即答"),
 (B + "friday_sokutou.py", "def kane(t)", "LINE：カードの利用可能額は即答"),
 (B + "mimi-watch.py", "mimi_basho.kotoba", "耳：場所を言葉で渡す"),
 (B + "mimi-watch.py", "CLAUDE_CODE_DISABLE_CLAUDE_MDS", "耳：軽い起動"),
 (B + "mimi-watch.py", "FRIDAY_KOE", "耳：声の質問を門に渡す（声で聞いたのに返事が無い）"),
 (B + "mimi-watch.py", "{line_talk}", "耳：先回りが LINE の話も読む"),
 (B + "friday_hitori.py", "FRIDAY_KOE", "1仕事1人の門：声で聞かれた答えは止めん"),
 (B + "mimi-matome.py", "3回だめ＝飛ばす", "耳：まとめが1会話で詰まらん"),
 (B + "mimi-matome.py", "mimi-cal-add", "耳：やる事→カレンダー"),
 (B + "mimi-renew.sh", "mimi_basho.py --ie", "耳：外出中にロック解除を頼まん"),
 (B + "mimi_basho.py", "work/nearby/loc.db", "耳：OwnTracks の点を使う"),
 (B + "basho", "overpass.openstreetmap.fr", "場所：生きとる地図の写し"),
 (B + "basho", "def _ovp", "場所：同時に探す（24秒→2〜4秒）"),
 (B + "friday-agent.py", '"sent": True', "LINE：届いた返事を二度送らん"),
 (B + "friday-agent.py", "もう届いた返事", "LINE：届いた返事を二度送らん（入口）"),
 (B + "friday-agent.py", "BASHO_HAYASA_Q", "LINE：「どこ」の質問も検算する"),
 (B + "friday-agent.py", "def kensan_zairyo", "LINE：『無い』の検算に耳・ご自宅・受信箱の材料を渡す（11/15 直し係）"),
 (B + "friday-agent.py", "def ichi_ato", "LINE：家に置いたスマホの位置を移動中の今の場所と言わん（11/15 直し係）"),
 (B + "friday-agent.py", "def jibun_mon", "LINE：「確認して」に「〜しましょうか」で投げ返さん（11/15 直し係）"),
 (B + "friday-agent.py", "def login_mon", "LINE：ログイン切れ・QR を理由に本人へ投げん＝ログイン済みのアプリを先に（11/16 直し係）"),
 (B + "friday-agent.py", "def bangou_mae", "LINE：番号1つの返事を聞き直さん＝直前の選択肢の行として渡す（11/16 直し係）"),
 (B + "friday-agent.py", "1回だけ作り直す", "LINE：空の返事で本人に再送を頼まん＝1回作り直す（11/16 直し係）"),
 (B + "friday-agent.py", "絵の番号の門", "LINE：絵を引用した「これ」を聞き直さん＝引用された絵の番号として渡す（11/17 直し係）"),
 (B + "friday-agent.py", "def nage2_mon", "LINE：決まり・期限を「納付書でご確認ください」「未確認です」で投げ返さん（11/17 直し係）"),
 (B + "friday-agent.py", "def kiroku_mon", "LINE：お金は記録の数字・明細なしの払い済みで言わん（11/17 直し係）"),
 (B + "friday-send", "todokanai-net", "LINE：通信エラーの文が消えん"),
 (B + "friday-send", "timeout=20", "LINE：送信の時間切れ"),
 (B + "friday-mail.sh", "last_ok", "メール：失敗した枠を見直す"),
 (B + "friday-mail.sh", "alarm shift", "メール：時間切れ"),
 (B + "friday-watch.sh", "alarm shift", "見張り：時間切れ"),
 (B + "friday-plan.sh", "alarm shift", "予定：時間切れ"),
 (B + "friday-plan.sh", "friday_planio", "予定：鍵つきで書く"),
 (B + "friday-tick.py", "awasete_kaku", "予定：古い写しで上書きせん"),
 (B + "friday-yakusoku.py", "friday_planio", "約束：鍵つきで書く"),
 (B + "friday_onaji.py", "直す所(は|が)?", "同じミスの門：「OK」の一言が返事にならん"),
 (B + "friday_hitori.py", "CLAUDE_CODE_DISABLE_CLAUDE_MDS", "1仕事1人の門：軽い起動"),
 (B + "friday-naoshi-prompt.md", "fa-idle naoshi", "夜の直し係：走っとる仕事を切らん"),
 (B + "friday-kenkou.py", "耳の受け口", "健康診断：耳を見る"),
 (H + "/friday-bot/src/index.js", '"done:" + id', "入口：返した id を覚える（公開する元）"),
 (H + "/friday-bot/src/index.js", "phq_", "入口：電話の同じ質問は1回だけ答える"),
]
bad = []
for f, mark, what in ANA:
    try: ok = mark in open(f, encoding="utf-8", errors="ignore").read()
    except Exception: ok = False
    if not ok: bad.append(f"{what}（{os.path.basename(f)} に「{mark[:24]}」が無い）")
# 動きの試験（速い物だけ）
def t(name, fn):
    try:
        r = fn()
        if r is not True: bad.append(f"{name}：{r}")
    except Exception as e: bad.append(f"{name}：{repr(e)[:80]}")
def t_syntax():
    for f in ("mimi-server.py", "mimi-watch.py", "mimi-matome.py", "mimi_basho.py", "friday-agent.py", "friday-tick.py", "friday-yakusoku.py", "friday_onaji.py", "friday_hitori.py", "friday_planio.py", "friday-kenkou.py"):
        r = subprocess.run([sys.executable, "-m", "py_compile", B + f], capture_output=True, text=True)
        if r.returncode: return f"{f} が文法エラー"
    return True
def t_planio():
    import tempfile; sys.path.insert(0, B); import friday_planio as P
    p = tempfile.mkdtemp() + "/plan/t.json"
    P.naosu(p, lambda pl: {"items": [{"id": "a", "at": "09:00", "status": None}]}); mine = P.yomu(p)
    P.naosu(p, lambda pl: (pl["items"].append({"id": "x", "at": "09:30", "status": None}), pl)[1])
    mine["items"][0]["status"] = "sent"; P.awasete_kaku(p, mine, [])
    r = {i["id"]: i.get("status") for i in P.yomu(p)["items"]}
    return True if r == {"a": "sent", "x": None} else f"予定の合わせ書きが違う {r}"
def t_ping():
    r = subprocess.run(["curl", "-s", "-m", "5", "http://100.64.0.1:8840/ping"], capture_output=True, text=True).stdout
    return True if '"ok": true' in r else "耳の受け口が返事せん"
t("文法", t_syntax); t("予定ファイルの鍵", t_planio); t("耳の受け口", t_ping)
if "--basho" in sys.argv:   # 遅い試験（1日1回）
    def t_basho():
        t0 = time.time(); r = subprocess.run([B + "basho", "chikaku", "コンビニ", "--from", "35.0000,139.0000"], capture_output=True, text=True, timeout=40).stdout
        s = time.time() - t0
        return True if ("1." in r and s < 12) else f"近くの店探しが遅い・出ん（{s:.0f}秒）"
    t("近くの店探し", t_basho)
st = {"at": time.strftime("%FT%H:%M"), "n": len(ANA), "bad": bad}
json.dump(st, open(H + "/owner-kotoba/friday/ana_mihari.json", "w"), ensure_ascii=False, indent=1)
print("\n".join(bad) if bad else f"穴なし（印 {len(ANA)}・試験 3）")
sys.exit(1 if bad else 0)
