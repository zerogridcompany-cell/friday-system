#!/usr/bin/env python3
"""フライデーの耳の先回り係（11/13 オーナー「常にマイクで聞いて、口に出した物を先回りして LINE に『ここいかがですか？』『タクシー手配しました』」）
mimi-server.py が書いた ~/owner-kotoba/friday/mimi/mimi.jsonl の新しい言葉を90秒ごとに読み、助かる一言があれば friday-send で1通。
動き（タクシーを呼ぶ・予約・買う）は勝手にやらん＝ボタン（--ask）で本人が押した1回だけ。"""
import json, os, re, subprocess, sys, time, datetime, fcntl
HOME = os.path.expanduser("~"); D = os.environ.get("MIMI_D") or HOME + "/owner-kotoba/friday/mimi"; F = HOME + "/owner-kotoba/friday"   # MIMI_D＝試験（mimi-shiken.py）用の別フォルダ
ST = D + "/watch_state.json"; JST = datetime.timezone(datetime.timedelta(hours=9))
DAY_MAX = 20
lk = open("/tmp/mimi-watch-test.lock" if os.environ.get("MIMI_D") else "/tmp/mimi-watch.lock", "w")
try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    # 11/15 速さ：走っとる最中に新しい声が来ると、次の見回り（最大60秒）まで待っとった（今朝 27〜28秒が2回）＝印を置いて、今の回が終わった瞬間にもう1回走らせる
    if not os.environ.get("MIMI_D"): open("/tmp/mimi-watch.again", "w").close()
    sys.exit(0)
import atexit
def _again():
    if os.environ.get("MIMI_D") or "--dry" in sys.argv or not os.path.exists("/tmp/mimi-watch.again"): return
    try:
        os.remove("/tmp/mimi-watch.again"); fcntl.flock(lk, fcntl.LOCK_UN)
        subprocess.Popen([sys.executable, os.path.abspath(__file__)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass
atexit.register(_again)
def log(s):
    with open(D + "/watch.log", "a") as f: f.write(datetime.datetime.now(JST).strftime("%m-%d %H:%M:%S ") + s + "\n")

# 11/14 耳の見張り：アプリの心拍（hb.json・1分ごと）が15分来ん／マイクが10分止まっとる時は LINE で1回だけ知らせる（3時間あける・8〜24時）
def hb_check(st, fn="hb.json", na="フライデーの耳", key="hb_alert"):
    try: hb = json.load(open(D + "/" + fn))
    except Exception:
        return   # 心拍が無い＝古い版か未起動。止めたか落ちたか分からん＝知らせん
    now = time.time(); h = datetime.datetime.now(JST).hour
    if hb.get("on") != "1" or not (8 <= h < 24) or now - st.get(key, 0) < 3 * 3600: return
    age = now - hb.get("t", now); stop = float(hb.get("stopsec") or 0)
    why = None
    # 11/14 夜 オーナー「俺が意図的に止めてる」＝止めた合図（on=0）を出せる新しいアプリ（v=2）だけ「返事が無い」で知らせる。古い版は止めたか落ちたか分からん＝知らせん
    if age > 15 * 60 and hb.get("v") not in ("2", "3"): return
    if age > 15 * 60: why = f"{datetime.datetime.fromtimestamp(hb['t'], JST):%H:%M} からアプリの返事がありません"
    elif stop > 600: why = f"マイクが{int(stop//60)}分止まっています（{hb.get('st', '')}）"
    if not why: return
    out = subprocess.run([HOME + "/bin/friday-send", f"オーナー様、{na}が止まっているようです（{why}）。お手数ですが、その iPhone でアプリ「フライデーの耳」を一度開いてください。", "--force"],   # 11/14 夜 2回目の停止が「同じ文」で止められて届かんかった＝3時間あけは自前でしとるので通す
                         capture_output=True, text=True).stdout.strip()
    st[key] = now; log(f"心拍の知らせ {na} {why} {out}")
st = json.load(open(ST)) if os.path.exists(ST) else {"seen": "", "sent": {}, "topics": []}
# 11/16 夜 渡せんかった調べ（enq_pending.jsonl）を渡し直す（6時間より古い物は捨てる）
try:
    _pp = os.path.dirname(ST) + "/enq_pending.jsonl"
    if os.path.exists(_pp) and "--dry" not in sys.argv and not os.environ.get("MIMI_D"):
        import urllib.request as _u0
        _d0 = json.load(open(HOME + "/.config/line/friday.json")); _rest = []
        for _l in open(_pp):
            _r = json.loads(_l)
            if time.time() - _r["t"] > 21600: continue
            try:
                _u0.urlopen(_u0.Request("https://friday-line.example.workers.dev/enqueue", data=json.dumps({"text": _r["text"]}).encode(), method="POST",
                    headers={"content-type": "application/json", "x-agent-key": _d0["agent_key"], "x-agent": "mimi", "user-agent": "friday-agent/1"}), timeout=15).read()
                log("渡せんかった調べを渡し直した")
            except Exception: _rest.append(_l)
        open(_pp, "w").writelines(_rest)
except Exception as _e: log(f"渡し直し失敗 {repr(_e)[:80]}")
hb_check(st)
if not os.path.exists(D + "/ie_off"): hb_check(st, "hb_ie.json", "家の耳", "hb_alert_ie")   # 11/14 夕 家の耳（EarPods）は本人の判断でやめた
json.dump(st, open(ST, "w"), ensure_ascii=False)
# 11/17 本人「フライデーと言ってから途切れたら、そこで区切って答えを出そうとする。その先は別の文として読む」
# ＝最後の声が名前の呼びかけの時は、続きの声が届くのを待ってから、まとめて読む（名前だけ・文の途中＝最大15秒、文が終わっとる＝5秒、続きが来たらそこから6秒静かになるまで・合計30秒まで）
if "--dry" not in sys.argv and not os.environ.get("MIMI_D"):
    try:
        sys.path.insert(0, HOME + "/bin"); import mimi_filter as FILT
        def _saigo():
            with open(D + "/mimi.jsonl", "rb") as f:
                f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 8000)); ls = f.read().decode("utf-8", "ignore").strip().split("\n")
            for l in reversed(ls):
                try:
                    r = json.loads(l)
                    if r.get("text") and not r.get("ie"): return r
                except Exception: pass
            return None
        _c = _saigo()
        if _c and FILT.yobu(_c["text"]):
            _lim = 15 if (FILT.namae_dake(_c["text"]) or not re.search(r"[。？?！!]\s*$", _c["text"])) else 5
            _s0 = _q0 = time.time()
            while time.time() - _s0 < 30 and time.time() - _q0 < _lim:
                time.sleep(1.5); _n = _saigo()
                if _n and _n["at"] != _c["at"]: _c = _n; _q0 = time.time(); _lim = 6
            log(f"続きを待った {int(time.time() - _s0)}秒")
    except Exception as _e: log(f"続き待ち失敗 {repr(_e)[:80]}")
recs = []
if os.path.exists(D + "/mimi.jsonl"):
    for l in open(D + "/mimi.jsonl"):
        try: recs.append(json.loads(l))
        except Exception: pass
# 11/14 家に置いた iPhone（ie）の声は「家での様子」。オーナー様が家に居る時だけ先回りに使う
def _km(a, b):
    import math
    if not (a and b and a.get("lat") and b.get("lat")): return 99
    return math.hypot((a["lat"] - b["lat"]) * 111, (a["lon"] - b["lon"]) * 91)
_me = next((r for r in reversed(recs) if r.get("lat") and not r.get("ie")), None)
_ie = next((r for r in reversed(recs) if r.get("lat") and r.get("ie")), None)
def _zaitaku():
    """持ち歩きの iPhone が mini から見えとる（同じ家の Wi-Fi）＝家に居る。5分ためる"""
    c = D + "/zaitaku.json"
    try:
        j = json.load(open(c))
        if time.time() - j["t"] < 300: return j["v"]
    except Exception: pass
    try:
        out = subprocess.run(["xcrun", "devicectl", "list", "devices"], capture_output=True, text=True, timeout=40).stdout
        v = bool(re.search(r"YOUR_IPHONE_UDID\S*\s*(\(UDID\))?\s+(available|connected)", out))
    except Exception: v = _km(_me, _ie) < 0.3
    json.dump({"t": time.time(), "v": v}, open(c, "w")); return v
AT_HOME = _zaitaku()
# 11/15 「どこまで読んだか」を時刻（seen）だけで持つと、受け口のやり直しで時刻が前後した声を飛ばす＝行の数（pos）でも持つ
now = datetime.datetime.now(JST)
_pos = st.get("pos")
_cand = [r for r in recs if r["at"] > st["seen"]] if (_pos is None or _pos > len(recs)) else recs[_pos:]
_cut = (now - datetime.timedelta(minutes=20)).isoformat()
new = [r for r in _cand if r.get("text") and (AT_HOME or not r.get("ie")) and (r["at"] > st["seen"] or r["at"] >= _cut)]
if not new:
    if recs: st["seen"] = max(st["seen"], recs[-1]["at"]); st["pos"] = len(recs); json.dump(st, open(ST, "w"), ensure_ascii=False)
    sys.exit(0)
day = now.strftime("%Y-%m-%d"); n = st["sent"].get(day, 0)
st["seen"] = max(st["seen"], max(r["at"] for r in new)); st["pos"] = len(recs)
# 11/15 耳の原因調べ（genin_20261115.md）：1日20通の上限に 11:04 で当たり、そのあと名前で呼んだ頼みも全部「上限」で黙って捨てとった（11:21 Chrome・12:03 請求書・14:07 支払い ほか7件）。
# → 上限は「頼まれてない先回り」だけに掛ける。名前（化けた「プライで」等も）で呼んだ声・頼みの言葉がある声は上限に関係なく必ず係に回す
sys.path.insert(0, HOME + "/bin"); import mimi_filter as FILT
_newraw = " ".join(r["text"] for r in new)
YOBI = FILT.yobu(_newraw); TANO = FILT.tanomi(_newraw); TOI = FILT.toi(_newraw)
JOGEN = n >= DAY_MAX
# 11/15 夜 上限の後の「質問の形」だけの声は、全部が声紋で「ほかの声」（🔈）ならテレビの質問＝係を起こさん
if JOGEN and TOI and not (YOBI or TANO) and all(FILT.koe_shirushi(r) == "🔈" for r in new): TOI = False
HONNIN = any(FILT.koe_shirushi(r) == "👤" for r in new)   # 11/15 夜 声紋が本人の声と出た区切りは、頼みの言葉が無くても上限で捨てん（「これ何キロカロリー」）
if JOGEN and not (YOBI or TANO or TOI or HONNIN):
    json.dump(st, open(ST, "w"), ensure_ascii=False); log("上限（頼みの言葉なし）" + _newraw[:60]); sys.exit(0)
# 11/15 オーナー「調べて→調べました を1秒未満の勢いで」＝カードの利用可能額は AI を起こさず、決まった道（~/bin/kane）で読んですぐ返す
try:
    sys.path.insert(0, HOME + "/bin"); import friday_kane as _fk
    _kt = " ".join(r["text"] for r in new)[-300:]
    if "--dry" not in sys.argv and not os.environ.get("MIMI_D") and _fk.cards(_kt):
        _t0 = time.time(); _ans = _fk.kotae(_kt, log=log)
        if _ans:
            _o = subprocess.run([HOME + "/bin/friday-send", _ans, "--force"], capture_output=True, text=True, env={**os.environ, "FRIDAY_KOE": _kt}).stdout.strip()
            log(f"カードの即答 {time.time()-_t0:.1f}秒 {_o} {_ans[:60]}")
            with open(F + "/sent.jsonl", "a") as f:
                f.write(json.dumps({"day": day, "at": f"{now:%FT%H:%M}", "text": _ans, "result": _o, "kind": "mimi-kane", "by": "mini"}, ensure_ascii=False) + "\n")
            st["topics"] = [t for t in st.get("topics", [])] + [{"at": now.isoformat(), "topic": "カードの利用可能額"}]
            json.dump(st, open(ST, "w"), ensure_ascii=False); sys.exit(0)
except SystemExit: raise
except Exception as ex: log(f"カードの即答 失敗 {repr(ex)[:100]}")
cut = (now - datetime.timedelta(minutes=15)).isoformat()
ctx = [r for r in recs if r["at"] >= cut and r.get("text")]
ctx = [r for r in ctx if AT_HOME or not r.get("ie")]
talk = "\n".join(f"{r['at'][11:19]} {'🏠' if r.get('ie') else ''}{'🎬' if (r.get('douga') or 0) >= 0.5 else ''}{FILT.koe_shirushi(r)}{FILT.seiki(r['text'])}" for r in ctx)
newt = "\n".join(f"{r['at'][11:19]} {'🏠' if r.get('ie') else ''}{'🎬' if (r.get('douga') or 0) >= 0.5 else ''}{FILT.koe_shirushi(r)}{FILT.seiki(r['text'])}" for r in new)
loc = _me
try:   # 11/14 夜 オーナー「位置情報と耳でさらに正確に」＝駅・地名・止まっとるか乗り物か
    sys.path.insert(0, HOME + "/bin"); import mimi_basho
    where = mimi_basho.kotoba(recs)   # OwnTracks の点も使う＝耳が静かな時も今の場所と動きが分かる
except Exception:
    where = f"{loc['lat']:.5f},{loc['lon']:.5f}（{loc['at'][11:16]} 時点）" if loc else "不明"
try:   # 11/14 夜 声だけ見て LINE の話を知らんかった＝21:16 に LINE で「シャトルバスは6番のりば」と答えた直後、声の「シャンプラバスのバス停まで何分」を「見つかりません」と書いた
    sys.path.insert(0, HOME + "/bin"); import friday_hitori as _fh
    line_talk = os.environ.get("MIMI_LINE_TALK") or "\n".join(l for l in _fh.recent_talk(hours=1).splitlines() if "〈パートナー〉" not in l)[-3500:] or "（なし）"
except Exception: line_talk = "（読めず）"
topics = [t for t in st.get("topics", []) if t["at"] > (now - datetime.timedelta(minutes=90)).isoformat()]
prompt = f"""あなたはフライデー（オーナー様の専属執事 AI）。オーナー様の iPhone のマイクが拾った声を文字にした物を読んでいる。
今 {now:%Y-%m-%d %H:%M}（日本時間）。今の場所（緯度,経度）＝{where}

🏠 の付いた行は家に置いた iPhone が拾った声（家の中の音・テレビ・同居の人の声も入る）。オーナー様の声とは限らん。

直近15分の声:
{talk}

この回で新しく入った声:
{newt}

直近60分の LINE でのやり取り（オーナー様とフライデーの返事係）。声の中の「あのバス」「さっきの件」や、聞き間違いっぽい言葉（例：シャンプラバス＝シャトルバス）は、ここと照らして何の話かを決める。ここで答え済みの事（乗り場の番号など）は調べ直さず、それを使って声の質問（そこまで何分・どう行く）に答える:
{line_talk}

最近90分に送った話題（頼まれてない先回りの提案だけ、同じ話題は送らん。🔴本人が頼み直した声（「もう一回」「もう一度」「まだ？」・同じ頼みの言い直し）は、前に送った話題でも必ず受ける＝11/15 10:06・10:09 のカードの頼み直しを「同じ話題」で2回捨てた）: {json.dumps([t['topic'] for t in topics], ensure_ascii=False)}

機械の見立て（この回の新しい声）：名前の呼びかけ＝{'あり' if YOBI else 'なし'}・頼みの言葉＝{'あり' if TANO else 'なし'}・質問の形＝{'あり' if TOI else 'なし'}。{'🔴今日は頼まれてない先回りの上限（' + str(DAY_MAX) + '通）に達しとる＝オーナー様がフライデーに向けて言った質問・頼み（「俺の家の近くだったらどこ」「電車でどうやったら行ける」「フライデーはどう思う」）への答えだけ送る。テレビ・動画の中の質問と、頼まれてない先回りの提案は送らん。' if JOGEN else ''}書き起こしでは「フライデー」が「プライで」「フライで」「フライデン」「フライディ」「フライダー」に化ける＝上の声は機械で「フライデー」に直してある。
「俺の」「俺ん家」「俺が」が入った質問・どこで・いくら・どうやって等の生活の質問は、前置きが無くてもオーナー様本人の質問として必ず受けて調べる（do に書く）（11/17 Opus にしたら「俺の家の近くだったらどこで」を受けんかった）。

やる事：オーナー様が口に出した「行きたい・探したい・調べたい・困った・忘れそう・予定」に、先回りで LINE を1通送るかを決める。
- 送るのは本当に助かる時だけ（場所・道のり・店・時刻・予定・持ち物・調べ物の答え）。テレビや動画の音・歌詞・ただの雑談は送らん。
- 👤 の付いた行＝声紋（声の持ち主の見分け）が「オーナー様の声」と出た区切り。周りでテレビや人の声が鳴っとっても、👤 の行の質問・頼み・「〜しといて」はオーナー様が口に出した言葉として読む。🔴👤 の行の質問（「これ何キロカロリー」「いくらやったっけ」「どこで払える」）は、答えを送る（11/16 テレビの中で聞いた「リッツクラッカー何キロカロリー」を送らんかった）。送らんのは、前後の行で周りの人がその質問に答えとる（🔈 の声と掛け合いになっとる）・ゲームや会話の相手に言うとるのが明らかな時だけ。
- 🔈 の付いた行＝声紋が「オーナー様と違う声」と出た区切り（テレビ・動画・周りの人）。中身が頼みや質問の形でも、オーナー様の頼みとして扱わん。ただし「フライデー」と名前で呼ばれた行は 🔈 でも受ける（声紋は叫び声・遠い声で外れることがある）。印が無い行は声紋で見分けとらん（声が短い等）＝今まで通り中身で決める（印が無いから本人の声やないとは読まん）。
- 🎬 の付いた行＝iPhone で動画・音楽が鳴っとった時の声（11/15 本人「動画を流しながら話すと文字が化ける」）。中身はほぼ動画の音・歌詞・化けた文字＝本人の言葉として扱わん。ただし「フライデー」と名前で呼ばれた頼みは 🎬 でも受ける。
- 今の場所の行（駅・地名・止まっている／歩いている／乗り物で移動中・速さ・向き）と声を合わせて、今どこで何をしとるかを読む。電車の車内放送（「次は◯◯」「◯◯行き」）・駅や券売機の案内・空港の放送はそれだけでは送らんが、乗っとる路線・行き先・着く時刻の手がかりに使う（例：駅で券売機の音→その路線で空港方面かも）。場所の行と声が食い違う時は場所の行を信じる。
- 周りの人（友達・仕事の相手）の声も文脈として読む。みんなで決まりかけた事（店・行き先・時間・誰が何をやる）や誰かの困り事で、オーナー様が動けば助かる物は送る（例：「焼肉行こう」→近くの空いとる店と予約ボタン）。声だけでは誰が言うたか分からんので、断定せず「お話に出た◯◯」と書く。
- 🔴ただし本人の「〜したい」「〜食べたい」「〜頼んでほしい」「誰か〜してくれんかな」「〜どこやっけ」は独り言でも送る＝フライデーが叶えられる願い。何をどこで頼む／行くかを具体的に（店・品・目安の値段や時間を調べて1〜3行）提案し、動きはボタンにする（例：Uber Eats でマクドナルドを頼む→ask {{"label":"頼んで","action":"Uber Eats で◯◯を注文画面まで進める"}}）。
- 🔴🔴オーナー様が声で「◯◯調べて」「調べてほしい」「探して」「教えて」「見てきて」と頼んだ時（11/15 本人「調べてと言ったら確認は要らん。調べます→調べました」）：「お調べいたしましょうか」「確認いたしましょうか」と聞かん・調べるだけのボタン（ask）も付けん。basho の道具1回で今すぐ答えが出る物は、答えそのものを text に書く。Web・予約サイトの空き・メール・口コミ等を見ないと分からん物は、do に「何を・どこで・どの日時で調べるか」を具体的に書き、text は「オーナー様、◯◯をお調べします。」の1行だけにする（ask は null）。do は調べる・見るだけ＝予約する・買う・送る・呼ぶ・広告や設定を変える事は do に入れん（そっちは今まで通り提案＋ボタン）。テレビ・動画・他の人の声の「調べて」には do を出さん。
- 🔴「記録しといて」「メモしといて」「覚えといて」「これ全部記録」（化けて「記録さっといて」）は、名前が無くてもフライデーへの頼み（11/15 22:50 会議中に言うたのに無反応）＝send true で「承知しました。今のお話は記録しております。」と1行（何を残したか分かれば一言足す）。do は null。
- 🔴🔴名前で呼ばれた時は必ず何か返す（黙らん）：頼み・質問→答える／決まり・指示（「フライデーは◯◯せんでいい」）→「承知しました」＋中身を一言で復唱／お礼・あいさつ→一言／中身が読み取れん→「うまく聞き取れませんでした。もう一度お願いいたします。」。送らんでええのは、人との会話の中でフライデーの話をしとるだけの時（「フライデーに送った請求書」）。
- 🔴🔴声の中で「フライデー」と名前で呼ばれた頼みは、何の話でも必ず受ける（11/15 10:09「フライデー カードの利用可能額と利用履歴を調べて」を EC の話と取って無視した）。調べ物なら do に書く。
- 🔴EC の店と広告の作業には反応せん（11/15 本人「フライデーは広告とか調べなくていい。EC はメールと 〈人〉 の返答を確認してと言った時だけ。他は無視」）：名前で呼ばれてない声で、〈店〉・〈店〉・〈店〉・〈店〉の店の設定・Shopify・Meta・広告・予算・店や広告の支払い方法の付け外し・記事・動画制作の話は、別の担当（パソコンの Claude）に音声入力で頼んどる声＝send false・do null。「調べて」「確認して」「止めて」「外して」が付いとっても同じ。例外＝「メール確認して」「〈人〉の返事を見て」は do に書く。オーナー様本人のお金の事（カードの利用可能額・利用履歴・引き落とし・残高・支払い日）は EC の作業やない＝フライデーの仕事として受ける。
- 場所と道のりは道具を1回だけ使う：`~/bin/basho chikaku "<言葉>" --from "<緯度,経度>"`・`~/bin/basho michi "<行き先>" --from "<緯度,経度>"`。数字は道具の結果だけ書く（作らん）。
- 🔴やってない事を「いたしました」「準備しました」「手配しました」と書かん（11/14 Uber Eats で実際は何もしてへんのに「準備をいたしました」と書いた）。提案は「〜いたしましょうか」で。
- タクシーを呼ぶ・予約・買う・送る等の動きは、自分ではやらん。本文で提案して、ボタンを付ける：ask に {{"label": "呼んで", "action": "GO で◯◯（乗る所）から◯◯まで呼ぶ"}} の形。
- 口調：標準語の丁寧な執事（です・ます・呼びかけは「オーナー様」）。2〜5行。住所の番地・パスワード・カード番号は書かん。
- 「〈パートナー〉」に関する話は送らん・書かん。

最後の1行だけ出す：FRIDAY {{"send": true か false, "topic": "話題を10字で", "text": "本文", "ask": null か {{"label": "...", "action": "..."}}, "do": null か "調べる中身"}}"""
t0 = time.time(); _gave = False
try:
    # 11/14 夜 速く：CLAUDE.md・rules・memory を読まん軽い起動（測った差 6.2秒→3.8秒）。先回りに要る物は全部この指示文の中にある
    KEI = HOME + "/friday-work/kei"; kei = os.path.isdir(KEI) and not os.path.exists(F + "/kei_off")
    CL = os.environ.get("CLAUDE_BIN") or next((p for p in (HOME + "/.local/bin/claude", "/opt/homebrew/bin/claude") if os.path.exists(p)), "claude")   # 受け口から直に起こされた時は PATH が無い
    r = subprocess.run([CL, "-p", "--model", "opus", "--settings", '{"disableAllHooks":true}',
                        "--allowedTools", "Read,Bash(~/bin/basho:*),Bash(/Users/owner/bin/basho:*)"] + (["--setting-sources", "project"] if kei else []),
                       input=prompt, capture_output=True, text=True, timeout=240, cwd=KEI if kei else HOME,
                       env={**os.environ, "PATH": HOME + "/.local/bin:" + HOME + "/bin:/opt/homebrew/bin:/usr/bin:/bin:" + os.environ.get("PATH", ""),
                            **({"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"} if kei else {})})
    out_txt = r.stdout
except Exception as ex:   # 11/14 夜 時間切れで落ちると印（seen）が残らず、同じ言葉を毎分やり直しとった
    log(f"失敗 {repr(ex)[:120]}"); out_txt = ""; _gave = True
    # 失敗した言葉は捨てん＝印（seen）を進めずに終わって次の回でやり直す。同じ所で3回続けて失敗した時だけ進める（毎分やり直し続けん）
    _old = json.load(open(ST)) if os.path.exists(ST) else {}
    _f = _old.get("fail", {}); _k = st["seen"]; _c = _f.get(_k, 0) + 1
    if _c < 3:
        _old["fail"] = {_k: _c}; json.dump(_old, open(ST, "w"), ensure_ascii=False); sys.exit(0)
m = re.findall(r"FRIDAY (\{.*\})", out_txt)
try: j = json.loads(m[-1]) if m else {}
except Exception: j = {}
if not j and not _gave:   # 11/15 係が答えの行を出さん回（「0s {}」）も、時間切れと同じく捨てずに次の回でやり直す（3回まで）
    _old = json.load(open(ST)) if os.path.exists(ST) else {}
    _f = _old.get("fail", {}); _k = st["seen"]; _c = _f.get(_k, 0) + 1
    if _c < 3:
        _old["fail"] = {_k: _c}; json.dump(_old, open(ST, "w"), ensure_ascii=False); log(f"答えの行なし→やり直し {_c}回目"); sys.exit(0)
log("入力 " + ("名前" if YOBI else "") + ("頼み" if TANO else "") + "｜" + newt.replace("\n", " ")[-120:])
# 11/15 名前で呼んで頼んだ声を係が「送らん」にした時（10:06 プライで…カード・10:09 フライデー カード もう一回）は、黙って捨てず返事係（LINE の本体・1人）に声のまま渡す
NIGE = bool(YOBI and (TANO or TOI) and not j.get("send") and not (isinstance(j.get("do"), str) and j["do"].strip()))
if NIGE:
    if "--dry" in sys.argv or os.environ.get("MIMI_D"): log("名前の頼み→返事係（dry・渡したことにする）")
    else:
        try:
            import urllib.request as _u
            _d = json.load(open(HOME + "/.config/line/friday.json"))
            _t = ("（耳が拾ったオーナー様の声の頼み。名前で呼ばれた頼み。声：「" + newt[-600:] + "」。先回りの係は送らん判定やったが、名前で呼ばれた頼みは必ず受ける決まり。"
                  "オーナー様が頼んだ事を読み取り、調べ物なら今すぐ調べて結果だけを短く返す。パソコンの作業への指示や独り言で、フライデーがやる事が無い時だけ「承知しました」と1行で返す。予約・購入・送信・電話など外に出す事はせず、要る時だけボタンで聞く）" + "\n直前の声（文脈・「進めて」「それ」はここの続き）：\n" + talk[-700:])
            _q = _u.Request("https://friday-line.example.workers.dev/enqueue", data=json.dumps({"text": _t}).encode(), method="POST",
                            headers={"content-type": "application/json", "x-agent-key": _d["agent_key"], "x-agent": "mimi", "user-agent": "friday-agent/1"})
            log("名前の頼み→返事係 " + _u.urlopen(_q, timeout=15).read().decode()[:60])
        except Exception as ex: log(f"名前の頼みを渡せず {repr(ex)[:120]}")
# 11/16 本人「なんで100%でできないの」＝聞き違いは0にならん→名前で呼ばれたのに何も返さん事を無くす。係が送らん・調べん・返事係にも渡さん時は、黙らず聞き返す
# （全部の行が声紋で「ほかの声」🔈＝テレビの中の名前は除く・3分に1回まで）
if YOBI and FILT.yobikake(_newraw) and not NIGE and not j.get("send") and not (isinstance(j.get("do"), str) and j["do"].strip()) and not all(FILT.koe_shirushi(r) == "🔈" for r in new):
    if time.time() - st.get("kiki", 0) >= 180:
        st["kiki"] = time.time()
        log("名前の頼み→返事係（聞き返し）")
        j = {"send": True, "topic": "聞き返し", "text": "オーナー様、お呼びでしょうか。うまく聞き取れませんでした。恐れ入りますが、もう一度お願いいたします。", "ask": None, "do": None}
# 11/16 夜 本人「最悪」＝「うまく聞き取れませんでした」が1日で約30通。大半は本人の声と出てない行（🔈・印なし）と、雑音に出た名前。
# 聞き返しだけの短い返事は「本人の声（👤）で呼びかけた行がある時」だけ送る
if j.get("send") and re.search(r"聞き取れ(?:ません|ており|なかっ)", j.get("text") or "") and len(j.get("text") or "") < 90 \
   and not (isinstance(j.get("do"), str) and j["do"].strip()) and not os.environ.get("MIMI_KIKI_OK"):
    # 送ってええ行＝呼びかけで、ほかの声（🔈）やない。名前だけの行は本人の声（👤）の時だけ
    if not any(FILT.yobikake(r["text"]) and FILT.koe_shirushi(r) != "🔈" and (FILT.koe_shirushi(r) == "👤" or not FILT.namae_dake(r["text"])) for r in new):
        log("聞き返しを止めた（本人の声の呼びかけが無い）"); j["send"] = False
log(f"{int(time.time()-t0)}s {json.dumps(j, ensure_ascii=False)[:240]}")
# 11/17 10:00 「車の修理…」を係が考えとる8秒の間に続き「車も直せる修理場…」が届いとったのに見ずに送り、続きは別の頼みとしてもう1回送った（お調べします2通・調べ2本）
# ＝送る直前に、この回の声より後に本人の声（印が🔈でない・🎬でない・家でない）が届いとったら送らず、読んだ印も進めずに終わる＝次の回で両方まとめて1通にする。
# 話し続けて永遠に待たんよう、この回の一番古い声が90秒より前なら待たずに送る
def _atokara():
    try:
        _last = max(r["at"] for r in new); _old = min(r["at"] for r in new)
        if (now - datetime.datetime.fromisoformat(_old)).total_seconds() > 90: return None
        with open(D + "/mimi.jsonl", "rb") as f:
            f.seek(0, 2); n_ = f.tell(); f.seek(max(0, n_ - 12000)); ls = f.read().decode("utf-8", "ignore").strip().split("\n")
        for l in ls:
            try: r = json.loads(l)
            except Exception: continue
            if r.get("at", "") > _last and r.get("text") and not r.get("ie") and (r.get("douga") or 0) < 0.5 and FILT.koe_shirushi(r) != "🔈" and not FILT.bad(r["text"]):
                return r
    except Exception as e: log(f"後からの声の確かめ失敗 {repr(e)[:80]}")
    return None
if j.get("send") and j.get("text") and "--dry" not in sys.argv and not os.environ.get("MIMI_D"):
    _ak = _atokara()
    if _ak:
        log("続きが届いとった→送らず次の回でまとめる ｜" + _ak["at"][11:19] + " " + _ak["text"][:50])
        open("/tmp/mimi-watch.again", "w").close()   # 終わった瞬間にもう1回走らせる（印は進めてない＝両方まとめて読む）
        sys.exit(0)
if j.get("send") and j.get("text") and "--dry" not in sys.argv:
    cmd = [HOME + "/bin/friday-send", j["text"]]
    if isinstance(j.get("ask"), dict) and j["ask"].get("label") and j["ask"].get("action"):
        cmd += ["--ask", j["ask"]["label"], j["ask"]["action"]]
    # 11/14 夜 声で聞いた「◯◯空港って何時まで？」の答えを、1仕事1人の門が「頼まれてない」と止めた＝今の声を門に渡す
    # 11/15 23:01 本人「全然ダメ・返してこない」3回目：「会話記録しといて」に係は「承知しました」を出したのに、1仕事1人の門が「記録してないのに しております」と黙って止めた
    # → 本人の頼み（名前・頼みの言葉）への返事は返事扱い（--reply＝1仕事1人の門を通らん。同じ文の30時間の門は残る）。それでも送れんかったら黙らず返事係へ声ごと渡す
    if YOBI or TANO: cmd.append("--reply")
    out = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "FRIDAY_KOE": newt[-1200:]}).stdout.strip()
    log("送った結果 " + out[:120])
    if out != "sent" and (YOBI or TANO) and "同じ文" not in out and "--dry" not in sys.argv and not os.environ.get("MIMI_D"):
        try:
            import urllib.request as _u
            _d = json.load(open(HOME + "/.config/line/friday.json"))
            _t = ("（耳が拾ったオーナー様の声の頼み。先回りの係の返事が送れんかった（" + out[:80] + "）ので返事係に渡す。声：「" + newt[-600:] + "」。係の下書き：「" + j["text"][:300] + "」。"
                  "オーナー様の頼みに短く返す。耳はマイクの声を全部文字にして残しとる＝「記録しといて」には「記録しております」と返してええ。予約・購入・送信・電話など外に出す事はせず、要る時だけボタンで聞く）")
            _q = _u.Request("https://friday-line.example.workers.dev/enqueue", data=json.dumps({"text": _t}).encode(), method="POST",
                            headers={"content-type": "application/json", "x-agent-key": _d["agent_key"], "x-agent": "mimi", "user-agent": "friday-agent/1"})
            log("送れん返事→返事係 " + _u.urlopen(_q, timeout=15).read().decode()[:60])
        except Exception as ex: log(f"送れん返事を渡せず {repr(ex)[:120]}")
    if out == "sent" and not (YOBI or TANO or TOI):   # 11/15 頼まれた返事・聞かれた答えは上限の数に入れん
        st["sent"][day] = n + 1
        topics.append({"at": now.isoformat(), "topic": j.get("topic", "")})
    # 11/15 本人「調べてと言ったら確認なしで調べて結果だけ」＝調べる中身（do）は返事係（1人）の列に入れる。返事係が調べて結果を LINE で返す
    if isinstance(j.get("do"), str) and len(j["do"].strip()) >= 4:
        try:
            import urllib.request as _u
            _d = json.load(open(HOME + "/.config/line/friday.json"))
            _t = ("（耳が拾ったオーナー様の声の頼み。声：「" + newt[-600:] + "」。もう LINE で「お調べします」と伝えてある＝確認の質問・「調べましょうか」は書かず、"
                  "今すぐ自分で調べて、結果だけを短く返す。予約・購入・送信・電話など外に出す事はせず、要る時だけボタンで聞く）\n耳の係（軽いモデル）の読み＝外れとる事がある。上の声そのものを正にして、意味が違えば声の方で動く：" + j["do"].strip()[:800] + "\n直前の声（文脈・「進めて」「それ」はここの続き）：\n" + talk[-700:])
            _q = _u.Request("https://friday-line.example.workers.dev/enqueue", data=json.dumps({"text": _t}).encode(), method="POST",
                            headers={"content-type": "application/json", "x-agent-key": _d["agent_key"], "x-agent": "mimi", "user-agent": "friday-agent/1"})
            log("調べを返事係へ " + _u.urlopen(_q, timeout=15).read().decode()[:60] + " " + j["do"][:80])
        except Exception as ex:
            log(f"調べを渡せず {repr(ex)[:120]}")
            # 11/16 夜 受付が落ちとる間「お調べします」だけ送って調べが消えた（4件）＝渡せんかった物は残して次の回に渡し直す＋本人に1時間に1回だけ知らせる
            try:
                with open(os.path.dirname(ST) + "/enq_pending.jsonl", "a") as f: f.write(json.dumps({"t": time.time(), "text": _t}, ensure_ascii=False) + "\n")
                if time.time() - st.get("enq_ng", 0) > 3600 and "--dry" not in sys.argv and not os.environ.get("MIMI_D"):
                    st["enq_ng"] = time.time()
                    subprocess.run([HOME + "/bin/friday-send", "オーナー様、申し訳ございません。受付の不具合で、今のお調べを係に渡せておりません。直り次第、自動でお調べしてお返事いたします。"], capture_output=True, timeout=60)
            except Exception: pass
    with open(F + "/sent.jsonl", "a") as f:
        f.write(json.dumps({"day": day, "at": f"{now:%FT%H:%M}", "text": j["text"], "result": out, "kind": "mimi", "by": "mini"}, ensure_ascii=False) + "\n")
st["topics"] = topics
json.dump(st, open(ST, "w"), ensure_ascii=False)
