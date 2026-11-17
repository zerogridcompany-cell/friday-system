"""フライデーの即答の表（2026-11-12 本人「1秒未満で読む・AIが読みやすい形」）
場所・時刻・予定・便の決まった短い質問は、AI を起こさずデータから直接答える（1秒未満）。
自信が無い時（位置が古い・言い回しが外れる・長い文）は None＝いつもの道（AI）へ。
試し: python3 ~/bin/friday_sokutou.py "今どこ？"
"""
import os, re, json, ast, datetime, subprocess, time
HOME = os.path.expanduser("~")
F = os.path.join(HOME, "owner-kotoba/friday")
CN = datetime.timezone(datetime.timedelta(hours=8)); JP = datetime.timezone(datetime.timedelta(hours=9))

def _clean(t):
    t = re.sub(r"^（声のメッセージ）", "", (t or "").strip())
    return re.sub(r"[\s　。、！!？?〜~ｗw笑]+$", "", t).strip()

def _ima():
    try: return json.load(open(os.path.join(F, "basho/ima.json"), encoding="utf-8"))
    except Exception: return {}

def _tz():
    """今いる場所の時間帯（11/12 本人「いる場所での時刻に依存」＝genchi.py が位置から決める）"""
    try:
        import sys; sys.path.insert(0, os.path.join(HOME, "bin")); import genchi
        return genchi.genchi_tz()[0]
    except Exception: return CN if _ima().get("china") else JP

# ── 場所 ─────────────────────────────
BASHO = re.compile(r"^(俺|おれ|僕|自分)?(は|って)?(今|いま)?(どこ|何処)(に)?(いる|おる|にいる)?(と思う)?(の|か)?$|^(俺|おれ)の(今の|いる)?(場所|位置)(は|どこ|わかる|分かる)?$|^(今の|いまの)?(場所|位置|現在地)(どこ|は|教えて)$")
def basho(t):
    if not BASHO.match(t): return None
    j = _ima()
    if not j or j.get("stale") or (j.get("age_min") or 99) > 10: return None   # 古い位置は言わん＝AI が取り直す
    try: md = open(os.path.join(F, "basho/ima.md"), encoding="utf-8").read().splitlines()
    except Exception: return None
    get = lambda k: next((l.split("：", 1)[1].strip() for l in md if l.startswith(f"- {k}：")), "")
    p = get("場所"); st = get("状態"); amap = get("高德地図（中国）").split("（")[0]; g = get("地図")
    if not p: return None
    name = re.sub(r"\s+\S+市$", "", p.split("（")[0].strip())
    parts = [x.strip() for x in (p.split("（", 1)[1].rstrip("）").split(",") if "（" in p else [])]
    ku = next((x for x in parts if x.endswith("区")), ""); michi = next((x for x in parts if re.search(r"(路|街|道)$", x) and "街道" not in x), "")
    age = st.split("位置は")[1].split("・")[0] if "位置は" in st else f"{j.get('age_min')}分前"
    ugoki = st.split("・")[0] if st else ""
    out = [f"オーナー様、{age}の位置は{name}の近く{('（' + ' '.join(x for x in (ku, michi) if x) + '）') if (ku or michi) else ''}です。"]
    if ugoki: out.append(f"・{ugoki}")
    out.append(amap if (j.get("china") and amap) else g)
    return "\n".join(x for x in out if x)

# ── 時刻 ─────────────────────────────
JIKOKU = re.compile(r"^(今|いま)(何時|なんじ|の時間|の時刻)(か|かな|だっけ|？)?$|^(現地|中国)(は|って)?(今)?(何時|なんじ)$")
def jikoku(t):
    if not JIKOKU.match(t): return None
    n = datetime.datetime.now(_tz())
    return f"オーナー様、ただいま{n.month}月{n.day}日 {n.hour}時{n.minute:02d}分です。"

# ── 予定 ─────────────────────────────
YOTEI = re.compile(r"^(今日|きょう|明日|あした|あす|次|この後|このあと)(の)?(予定|スケジュール)(は|って|なに|何|ある|教えて|どう|だっけ|を教えて)*$|^(予定|スケジュール)(は|教えて|ある)$")
LRE = re.compile(r"^(\d{1,2})/(\d{1,2})\(\w+\) (終日|(\d{2}):(\d{2})-(\d{2}):(\d{2})) (.+?)(?: ＠(.+?))? \[[^\]]*\]")
def _yotei_rows():
    try: out = subprocess.run([os.path.join(HOME, "bin/yomu-yotei"), "3"], capture_output=True, text=True, timeout=8).stdout
    except Exception: return None
    rows = []; y = datetime.date.today().year
    for l in out.splitlines():
        m = LRE.match(l.strip())
        if not m: continue
        mo, d = int(m.group(1)), int(m.group(2))
        if m.group(3) == "終日":
            rows.append({"day": datetime.date(y, mo, d), "t": None, "title": m.group(8), "at": m.group(9) or ""}); continue
        s = datetime.datetime(y, mo, d, int(m.group(4)), int(m.group(5)), tzinfo=JP)   # Mac のカレンダーは日本時間
        rows.append({"day": None, "t": s, "title": m.group(8), "at": m.group(9) or ""})
    return rows
def yotei(t):
    m = YOTEI.match(t)
    if not m: return None
    rows = _yotei_rows()
    if rows is None: return None
    tz = _tz(); now = datetime.datetime.now(tz); kaigai = now.utcoffset() != datetime.timedelta(hours=9)
    w = m.group(1) or "今日"
    for r in rows:
        if r["t"]: r["t"] = r["t"].astimezone(tz); r["day"] = r["t"].date()
    if kaigai: rows = [r for r in rows if "ごみ" not in r["title"]]   # 家の収集日は海外では要らん
    if w in ("次", "この後", "このあと"):
        sel = [r for r in rows if r["t"] and r["t"] > now][:3]; lab = "この後"
    else:
        day = now.date() + datetime.timedelta(days=1 if w in ("明日", "あした", "あす") else 0)
        sel = [r for r in rows if r["day"] == day]; lab = f"{'明日' if day != now.date() else '本日'}（{day.month}/{day.day}）"
    if not sel: return f"オーナー様、{lab}のカレンダーの予定はございません。"
    sel.sort(key=lambda r: (r["t"] is not None, r["t"] or now))
    out = [f"オーナー様、{lab}の予定は{len(sel)}件です。"]
    for r in sel[:4]:
        tt = (f"{r['t'].month}/{r['t'].day} " if w in ("次", "この後", "このあと") else "") + (f"{r['t'].hour}:{r['t'].minute:02d}" if r["t"] else "終日")
        out.append(f"・{tt} {r['title'][:40]}")
    return "\n".join(out)

# ── 便 ───────────────────────────────
BIN = re.compile(r"^(明日の|次の|帰りの|帰り|今日の)?(便|フライト|飛行機)(は|って)?(何時|なんじ|いつ|どう|教えて|の時間|の情報|は何時|何時発|何時だっけ|何時出発)?(だっけ|かな|か)?$|^(帰り|帰りの便)(は)?(明日)?(何時|なんじ)(だっけ|か)?$|^(搭乗口|ゲート)(は|どこ|わかる|分かる|決まった)*$")
def _bins():
    try: src = open(os.path.join(HOME, "bin/friday-bin-mihari.py"), encoding="utf-8").read()
    except Exception: return []
    m = re.search(r"^BINS = (\[.*?^\])", src, re.S | re.M)
    if not m: return []
    try: return eval(m.group(1), {"__builtins__": {}}, {"CN": CN, "JP": JP})
    except Exception: return []
def bin_(t):
    if not BIN.match(t): return None
    now = datetime.datetime.now(datetime.timezone.utc)
    try: st = json.load(open(os.path.join(F, "bin_mihari.json"), encoding="utf-8"))
    except Exception: st = {}
    nxt = None
    for b in _bins():
        try:
            dep = datetime.datetime.strptime(f"{b['date']} {b['dep']}", "%Y-%m-%d %H:%M").replace(tzinfo=b["tz"])
        except Exception: continue
        if dep > now - datetime.timedelta(hours=1) and not st.get(b["id"], {}).get("done"):
            if nxt is None or dep < nxt[1]: nxt = (b, dep)
    if not nxt: return None
    b, dep = nxt; s = st.get(b["id"], {})
    gate = s.get("gate") or b.get("gate")
    est = datetime.datetime.fromtimestamp(s["est"], b["tz"]) if s.get("est") else None
    out = [f"オーナー様、{b['name']}は{dep.month}/{dep.day} {dep.hour}:{dep.minute:02d}発で、{b.get('to', '')}行きです。"]
    if est and abs((est - dep).total_seconds()) >= 600: out.append(f"・出発の見込み：{est.hour}:{est.minute:02d}（遅れ）")
    bd = b.get("board"); cl = b.get("close")
    if bd: out.append(f"・搭乗開始{'の目安' if b.get('board_meyasu') else ''}：{bd}{'／搭乗口が閉まる：' + cl if cl else ''}")
    out.append(f"・席：{b.get('seat') or '未確認'}／搭乗口：{gate or 'まだ出ていません'}")
    return "\n".join(out)

def kane(t):
    """11/15 カードの利用可能額＝決まった道で読んで即答（AI を起こさん）"""
    import friday_kane
    return friday_kane.kotae(t)

HANDLERS = [("カードの額", kane), ("場所", basho), ("時刻", jikoku), ("予定", yotei), ("便", bin_)]
def try_sokutou(m, log=print):
    """戻り値＝(本文, 種類) か None"""
    if m.get("type", "text") not in ("text", "audio"): return None
    raw = (m.get("text") or "").strip()
    if not raw or raw.startswith(("（引用返信", "（ボタン", "（電話", "（写真", "（動画", "（画像")): return None
    t = _clean(raw)
    if (len(t) > 20 and not (len(t) <= 45 and __import__("friday_kane").cards(t))) or "\n" in t: return None
    for name, fn in HANDLERS:
        try:
            r = fn(t)
            if r: return r, name
        except Exception as e:
            log(f"即答 {name} 失敗 {e}")
    return None

if __name__ == "__main__":
    import sys
    for q in sys.argv[1:] or ["今どこ？", "今何時", "明日の予定は？", "次の予定", "帰りの便は何時？", "搭乗口は？", "これどこ？", "明日の予定を〈グループ〉に送って"]:
        t0 = time.time(); r = try_sokutou({"text": q}); print(f"[{(time.time()-t0)*1000:.0f}ms] {q} → {r[1] if r else 'AIへ'}\n{r[0] if r else ''}\n")
