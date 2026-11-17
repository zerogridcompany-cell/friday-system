#!/usr/bin/env python3
"""フライデーの耳のまとめ係（11/14 オーナー「話しとる物をタスク化・言葉は全部コンテキストとして集める・『この時何か言ってたっけ？』で思い出せるように」）
mimi.jsonl を「15分あいたら1つの会話」で区切り、終わった会話ごとに 要約・決まった事・やる事・オーナー様が欲しそうな物 を
matome/<日付>.md と tasks.md に書く。オーナー様のやる事か欲しそうな物がある時だけ LINE で1通。"""
import json, os, re, subprocess, sys, time, datetime, fcntl
HOME = os.path.expanduser("~"); D = HOME + "/owner-kotoba/friday/mimi"; F = HOME + "/owner-kotoba/friday"
ST = D + "/matome_state.json"; JST = datetime.timezone(datetime.timedelta(hours=9))
GAP = 15 * 60; DAY_MAX = 8
lk = open("/tmp/mimi-matome.lock", "w")
try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: sys.exit(0)
os.makedirs(D + "/matome", exist_ok=True)
def log(s):
    with open(D + "/matome.log", "a") as f: f.write(datetime.datetime.now(JST).strftime("%m-%d %H:%M:%S ") + s + "\n")
def T(a): return datetime.datetime.fromisoformat(a)
st = json.load(open(ST)) if os.path.exists(ST) else {"done": "", "sent": {}}
recs = []
for l in open(D + "/mimi.jsonl"):
    try:
        r = json.loads(l)
        if r.get("text"): recs.append(r)
    except Exception: pass
now = datetime.datetime.now(JST)
blocks = []
for ie, dk in ((False, "done"), (True, "done_ie")):   # 11/14 持ち歩きと家の iPhone は別々の会話として区切る
    rs = [r for r in recs if bool(r.get("ie")) == ie and r["at"] > st.get(dk, "")]
    cur = []
    for r in rs:
        if cur and (T(r["at"]) - T(cur[-1]["at"])).total_seconds() > GAP: blocks.append((dk, cur)); cur = []
        # 11/14 夜 切れ目の無い長い話（会議・移動中ずっと）は終わるまで何時間もまとめが出ん＝60分か6千字で区切る
        if cur and ((T(r["at"]) - T(cur[0]["at"])).total_seconds() > 3600 or sum(len(x["text"]) for x in cur) > 6000): blocks.append((dk, cur)); cur = []
        cur.append(r)
    if cur and (now - T(cur[-1]["at"])).total_seconds() > GAP: blocks.append((dk, cur))   # 最後の会話は15分静かになってから

# 11/17 オーナー「録音でのコンテキスト集めも聞こえたものをそのまま置いとくんじゃなくて、ある程度修正できない？」
# ＝会話ごとに Opus が書き起こしを直す（元の言葉は残す）。直した物は mimi/naoshi/<日付>.md。まとめもこの直した文で作る
def _jisho():
    t = []
    try:
        for l in open(HOME + "/owner-kotoba/torisetsu/CORE.md", encoding="utf-8"):
            if "→" in l: t.append(l.strip())
    except Exception: pass
    try:
        for l in open(HOME + "/owner-kotoba/master/枝/02_話し方.md", encoding="utf-8"):
            if "読み違い" in l or "誤変換" in l: t.append(l.strip()[:400])
    except Exception: pass
    return "\n".join(t)[-3000:]
def naosu(b, day, where):
    lines = "\n".join(f"{i}\t{r['at'][11:19]}\t{r['text']}" for i, r in enumerate(b))
    p = f"""あなたはフライデー（オーナー様の専属執事 AI）の「聞き直し係」。iPhone のマイクの書き起こし（{day}・場所 {where}）には聞き違いがある。
前後の文脈・場所・下の読み違いの表・オーナー様の生活（EC の店〈店〉・〈店〉、フライデー、〈会社〉、自宅、〈パートナー〉、〈人〉、〈人〉 等）から、意味が通るように直す。
- 聞き違いの言葉・名前・数字・切れた文の継ぎ目だけを直す。言うてない事を足さん・言い回しを整えん・要約せん
- 「あの」「えっと」等の言いよどみは消してよい。テレビ・動画の音らしい行は直さん
- 「フライデー」は「プライで・フライで・ライで・アイデア・来年・ぐらいで・裏で・フライディー」に化けやすい（文頭の呼びかけは特に）。
- 自信がない直しは、直した言葉の後に（？）を付ける。直す所が無い行は出さん
読み違いの表：
{_jisho()}

書き起こし（番号・時刻・文）：
{lines}

最後の1行だけ出す：NAOSHI {{"n": [[番号, "直した文"], ...]}}"""
    try:
        r = subprocess.run([os.environ.get("CLAUDE_BIN", "claude"), "-p", "--model", "opus", "--settings", '{"disableAllHooks":true}', "--tools", ""],
                           input=p, capture_output=True, text=True, timeout=300, cwd=HOME)
        m = re.findall(r"NAOSHI (\{.*\})", r.stdout); j = json.loads(m[-1]) if m else {}
    except Exception as ex:
        log(f"聞き直し 失敗 {ex}"); return [x["text"] for x in b], 0
    out = [x["text"] for x in b]; n = 0
    for k in j.get("n", []):
        try:
            i, t = int(k[0]), str(k[1]).strip()
            if 0 <= i < len(out) and t and t != out[i]: out[i] = t; n += 1
        except Exception: pass
    if "--dry" not in sys.argv:
        os.makedirs(D + "/naoshi", exist_ok=True)
        with open(f"{D}/naoshi/{day}.md", "a", encoding="utf-8") as f:
            f.write(f"\n### {b[0]['at'][11:16]}〜{b[-1]['at'][11:16]}（📍{where}・直した {n}/{len(b)} 行）\n")
            for r, t in zip(b, out):
                f.write(f"- {r['at'][11:19]} {t}" + (f"　｜元：{r['text']}" if t != r["text"] else "") + "\n")
    return out, n

for dk, b in blocks:
    IEB = dk == "done_ie"
    s, e = b[0]["at"][11:16], b[-1]["at"][11:16]; day = b[0]["at"][:10]
    loc = next((r for r in b if r.get("lat")), None)
    where = f"{loc['lat']:.4f},{loc['lon']:.4f}" if loc else "不明"
    try:   # 11/14 夜 駅・地名・移動のしかたを言葉で（会話の始めと終わり）
        sys.path.insert(0, HOME + "/bin"); import mimi_basho
        if not IEB:
            w1, w2 = mimi_basho.kotoba(recs, b[0]["at"]), mimi_basho.kotoba(recs, b[-1]["at"])
            if w1 != "不明" or w2 != "不明": where = "始め " + w1 + "／終わり " + w2
    except Exception: pass
    if len(re.sub(r"\s", "", "".join(r["text"] for r in b))) < 40:
        st[dk] = b[-1]["at"]; continue
    _naoshi, _nn = naosu(b, day, where)
    words = "\n".join(f"{r['at'][11:19]} {'🎬(動画の音かも) ' if (r.get('douga') or 0) >= 0.5 else ''}{t}" for r, t in zip(b, _naoshi))   # 11/17 直した書き起こしでまとめる
    prompt = f"""あなたはフライデー（オーナー様の専属執事 AI）。オーナー様の iPhone のマイクが拾った会話（{day} {s}〜{e}・場所 {where}）を文字にした物を読む。
{'これは家に置いた iPhone が拾った家の中の音（テレビ・同居の人・オーナー様の生活の声）。家での過ごし方・習慣（起きた・寝た・料理・電話・作業など）が分かれば yoyaku に書く。' if IEB else ''}オーナー様1人の時もあれば、友達や仕事の相手と一緒の時もある。誰が言うたかは文字からは分からん＝文脈で推し量り、分からん時は「誰か」と書く。
文字起こしの誤りもある（固有名詞・数字は文脈で直してよいが、作らん）。テレビ・動画・店の放送の音は無視。「〈パートナー〉」に関する話は書かん。

会話：
{words}

最後の1行だけ出す（JSON・日本語）：
MATOME {{"title": "会話の題を15字以内", "yoyaku": ["何の話か1〜3行"], "kimatta": ["決まった事"], "yarukoto": [{{"dare": "オーナー様 か 名前 か 誰か", "nani": "やる事", "itsu": "期限（分かれば）", "itsu_iso": "期限の日時（言葉で期限が言われた時だけ。時刻まで分かれば YYYY-MM-DDTHH:MM、日だけなら YYYY-MM-DD、「今日中」なら会話の日。分からん・無い時は空）"}}], "hoshisou": ["オーナー様が欲しそう・困ってそうで、フライデーが手伝える物"], "line": true か false, "text": "line が true の時だけ、オーナー様への LINE 本文（執事の丁寧な標準語・『オーナー様、先ほど{s}ごろのお話から』で始め、やる事と手伝える事を・で3〜6行・最後に手伝いを申し出る）"}}
line を true にするのは、オーナー様のやる事か、フライデーが手伝える欲しそうな物がある時だけ。雑談だけなら false。"""
    t0 = time.time()
    try:
        r = subprocess.run([os.environ.get("CLAUDE_BIN", "claude"), "-p", "--model", "opus", "--settings", '{"disableAllHooks":true}'],
                           input=prompt, capture_output=True, text=True, timeout=300, cwd=HOME)
        m = re.findall(r"MATOME (\{.*\})", r.stdout); j = json.loads(m[-1]) if m else None
    except Exception as ex:
        log(f"失敗 {ex}"); j = None; r = None
    if not j:
        # 11/14 夜 1つの会話で失敗し続けると、後ろの会話が全部止まる＝3回だめなら飛ばして先へ
        if r is not None: log(f"形が違う {r.stdout[-200:]!r}")
        fk = dk + ":" + b[-1]["at"]; fails = st.setdefault("fail", {}); fails[fk] = fails.get(fk, 0) + 1
        if fails[fk] >= 3:
            log(f"3回だめ＝飛ばす {day} {s}〜{e}"); st[dk] = b[-1]["at"]; st["fail"] = {}
            with open(f"{D}/matome/{day}.md", "a") as f: f.write(f"\n### {s}〜{e}　（まとめられんかった・元の言葉＝mimi/{day}.md）\n")
        json.dump(st, open(ST, "w"), ensure_ascii=False); break
    L = [f"\n### {s}〜{e}　{'🏠家　' if IEB else ''}{j.get('title','')}（{'家の iPhone' if IEB else '📍' + where}）"]
    L += [f"- {x}" for x in j.get("yoyaku", [])]
    if j.get("kimatta"): L += ["- 決まった事：" + "／".join(j["kimatta"])]
    for t in j.get("yarukoto", []): L.append(f"- [ ] {t.get('dare','誰か')}：{t.get('nani','')}" + (f"（{t['itsu']}）" if t.get("itsu") else ""))
    if j.get("hoshisou"): L += ["- 欲しそう：" + "／".join(j["hoshisou"])]
    L.append(f"- 元の言葉＝mimi/{day}.md の {s}〜{e}／直した言葉＝mimi/naoshi/{day}.md（{_nn}行直した）")
    if "--dry" in sys.argv: print("\n".join(L)); continue
    with open(f"{D}/matome/{day}.md", "a") as f: f.write("\n".join(L) + "\n")
    with open(D + "/tasks.md", "a") as f:
        for t in j.get("yarukoto", []):
            f.write(f"- [ ] {day} {s} {t.get('dare','誰か')}：{t.get('nani','')}" + (f"（{t['itsu']}）" if t.get("itsu") else "") + f"　←{j.get('title','')}\n")
    log(f"{int(time.time()-t0)}s {day} {s}〜{e} {j.get('title','')} やる事{len(j.get('yarukoto', []))} line={j.get('line')} 聞き直し{_nn}行")
    # 11/14 夜 オーナー「Google カレンダーに入れる（期限がある物だけ・時間になったら iPhone に通知）」＝本人のやる事で期限がある物だけ。フライデーや他の人のやる事は入れん
    cal = [{"nani": t.get("nani", ""), "itsu_iso": t.get("itsu_iso", ""), "moto": f"{day} {s}〜{e} {j.get('title','')}"}
           for t in j.get("yarukoto", []) if "オーナー" in (t.get("dare") or "") and t.get("itsu_iso")]
    if cal: subprocess.Popen([sys.executable, HOME + "/bin/mimi-cal-add", json.dumps(cal, ensure_ascii=False)], start_new_session=True)
    n = st["sent"].get(day, 0)
    if j.get("line") and j.get("text") and n < DAY_MAX and "--dry" not in sys.argv and (now - T(b[-1]["at"])).total_seconds() < 3 * 3600:
        out = subprocess.run([HOME + "/bin/friday-send", j["text"]], capture_output=True, text=True).stdout.strip()
        if out == "sent": st["sent"][day] = n + 1
        with open(F + "/sent.jsonl", "a") as f:
            f.write(json.dumps({"day": day, "at": f"{now:%FT%H:%M}", "text": j["text"], "result": out, "kind": "mimi-matome", "by": "mini"}, ensure_ascii=False) + "\n")
    st[dk] = b[-1]["at"]
    if "--dry" not in sys.argv: json.dump(st, open(ST, "w"), ensure_ascii=False)
