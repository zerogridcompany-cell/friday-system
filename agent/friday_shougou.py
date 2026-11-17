#!/usr/bin/env python3
"""フライデー：お知らせの文の『◯時ご出発』『◯時発』を、カレンダー（~/bin/yomu-yotei）とメモ（枝06）の同じ日の時刻と照らす 2026-11-11
きっかけ＝11/11 6:00「七時にホテルをご出発」と送った（正しくは 7:30・カレンダーにも枝06にも 7:30 と書いてあった）。
  食い違い → 正しい時刻に直した文を返す（送る前に直す）。どちらか決められん → hold（送らん）。
使い方: friday_shougou.py "文" [YYYY-MM-DD]   ／   friday_shougou.py --test
呼び口: from friday_shougou import shougou ; r = shougou(text, date)
  r = {"text": 直した文, "status": "ok"|"fixed"|"hold"|"unverified", "notes": [..]}"""
import re, os, sys, subprocess, datetime

KAN = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
def kan2int(s):
    if not s: return None
    if "十" in s:
        a, _, b = s.partition("十")
        return (KAN.get(a, 1) if a else 1) * 10 + (KAN.get(b, 0) if b else 0)
    n = 0
    for c in s: n = n * 10 + KAN[c]
    return n
def int2kan(n):
    d = "〇一二三四五六七八九"
    if n < 10: return d[n]
    return ("" if n // 10 == 1 else d[n // 10]) + "十" + (d[n % 10] if n % 10 else "")

ZEN = str.maketrans("０１２３４５６７８９：", "0123456789:")   # 1文字→1文字（位置がずれん）
K = "〇一二三四五六七八九十"
TIME = (r"(?<!\d)(?P<t>(?P<h>\d{1,2})[:：](?P<m>\d{2})(?!\d)"
        r"|(?P<h2>\d{1,2})時(?!間)(?:(?P<m2>\d{1,2})分|(?P<han>半))?"
        rf"|(?P<kh>[{K}]{{1,3}})時(?!間)(?:(?P<km>[{K}]{{1,3}})分|(?P<khan>半))?)")
GAP_T = r"[^、。！？!?\n\d:：時→/／()（）・「」]{0,12}?"     # 文：「七時にホテルをご出発」の「にホテルをご」
GAP_R = r"(?:ごろ|頃)?\s*[^、。\s\d:：→/／()（）・「」]{0,8}?"   # 控え：「7:30 ホテル出発」「9:30 A空港発」
NOT_HATSU = r"(?![送売表生見行言揮注明達展音信熱券])"
def pats(gap):
    return [("出発", re.compile(TIME + gap + r"出発")),
            ("出発", re.compile(r"出発(?:は|が|を|：|:)\s*" + TIME)),
            ("発", re.compile(TIME + gap + r"(?<!出)発" + NOT_HATSU))]
P_TEXT, P_REF = pats(GAP_T), pats(GAP_R)

def tval(m):
    g = m.groupdict()
    if g["h"] is not None: h, mi, sty = int(g["h"]), int(g["m"]), "colon"
    elif g["h2"] is not None: h, mi, sty = int(g["h2"]), (30 if g["han"] else int(g["m2"] or 0)), ("han" if g["han"] else "ji")
    else: h, mi, sty = kan2int(g["kh"]), (30 if g["khan"] else (kan2int(g["km"]) or 0)), ("khan" if g["khan"] else "kji")
    if h is None or h > 24 or mi > 59: return None, None
    return h * 60 + mi, sty
def fmt(v, sty):
    h, mi = divmod(v, 60)
    if sty == "colon": return f"{h}:{mi:02d}"
    if sty in ("ji", "han"): return f"{h}時" + ("半" if mi == 30 else (f"{mi}分" if mi else ""))
    return int2kan(h) + "時" + ("半" if mi == 30 else (int2kan(mi) + "分" if mi else ""))
def hm(v): return f"{v // 60}:{v % 60:02d}"

def find(text, P):
    """→ [(種類, 分, 書き方, 時刻の始め, 終わり)]  同じ時刻を2回数えん"""
    t = text.translate(ZEN); out = {}
    for kind, p in P:
        for m in p.finditer(t):
            ts, te = m.span("t")   # 時刻の部分だけ（「七時半」「7:30」）
            v, sty = tval(m)
            if v is None: continue
            out.setdefault((ts, te), (kind, v, sty, ts, te))
    return sorted(out.values(), key=lambda x: x[3])

DATE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])")
def segs_for(text, day, default_hit):
    """日付（11/11 等）で区切って、その日の所だけを返す。最初の日付より前は default_hit の時だけ"""
    out, cur, last = [], default_hit, 0
    for m in DATE.finditer(text):
        if cur: out.append(text[last:m.start()])
        cur = (int(m.group(1)), int(m.group(2))) == (day.month, day.day); last = m.start()
    if cur: out.append(text[last:])
    # 「。」で切って、日付の続きが別の話に流れ込まんようにする（最初の文だけ）
    return [s.split("。")[0] if i or not default_hit else s for i, s in enumerate(out)]

# 11/12 C：控えの「出発を7:00→6:00に早めた」を 7:00 と読んで、正しい 6:00 の知らせを 7:00 に書き換えとった。
# 「時刻→時刻」「時刻から時刻」と直に並ぶ所は、前（古い方）を消して後ろ（新しい方）だけ残す
OLD_NEW = re.compile(r"(?:\d{1,2}[:：]\d{2}|\d{1,2}時(?:半|\d{1,2}分)?)\s*(?:→|->|⇒|から)\s*(?=\d{1,2}[:：]\d{2}|\d{1,2}時)")
def refs_from(texts):
    r = {"出発": set(), "発": set()}
    for s in texts:
        s = OLD_NEW.sub("", s.translate(ZEN))
        for kind, v, *_ in find(s, P_REF): r[kind].add(v)
    return r

def cal_refs(day):
    days = (day - datetime.date.today()).days + 1
    if days < 1: return None
    try: out = subprocess.run([os.path.expanduser("~/bin/yomu-yotei"), str(days)], capture_output=True, text=True, timeout=40).stdout
    except Exception: return None
    if "読めんかった" in out: return None
    pre = day.strftime("%m/%d(")
    body = [re.sub(r"^\d+/\d+\(\w+\) (?:終日|\d+:\d+-\d+:\d+) ", "", l) for l in out.splitlines() if l.startswith(pre)]
    return refs_from(sum((segs_for(b, day, True) for b in body), []))

EDA = os.path.expanduser("~/owner-kotoba/master/枝/06_今やっとる事.md")
def memo_refs(day, path=EDA):
    """枝06 のその日の所。新しい行（行頭の日付）から見て、時刻が書いてある一番新しい行を使う"""
    try: lines = [l for l in open(path, encoding="utf-8").read().splitlines() if l.startswith("- ")]
    except Exception: return None
    lines.sort(key=lambda l: (re.match(r"- (\d{4}-\d{2}-\d{2})", l) or [None, ""])[1], reverse=True)
    for l in lines:
        r = refs_from(segs_for(l, day, False))
        if r["出発"] or r["発"]: return r
    return {"出発": set(), "発": set()}

def shougou(text, day=None, cal=None, memo=None, near=120):
    """cal/memo を渡せば外を読まん（試験用）。正＝カレンダー、カレンダーに無い種類だけ枝06"""
    day = day or datetime.date.today()
    if isinstance(day, str): day = datetime.datetime.strptime(day[:10], "%Y-%m-%d").date()
    hits = find(text, P_TEXT)
    if not hits: return {"text": text, "status": "ok", "notes": []}
    cal = cal_refs(day) if cal is None else cal
    memo = memo_refs(day) if memo is None else memo
    notes, fixes, status = [], [], "ok"
    for kind, v, sty, ts, te in hits:
        if cal and cal[kind]: R, src = cal[kind], "カレンダー"
        elif memo and memo[kind]: R, src = memo[kind], "枝06"
        else: notes.append(f"{text[ts:te]}{kind}＝照らす控えが無い"); status = "unverified" if status == "ok" else status; continue
        if v in R: notes.append(f"{text[ts:te]}{kind}＝{src}と一致"); continue
        d = sorted((abs(r - v), r) for r in R if abs(r - v) <= near)
        if not d: notes.append(f"{text[ts:te]}{kind}＝{src}に近い時刻なし（別の予定とみて通す）"); status = "unverified" if status == "ok" else status; continue
        if len(d) > 1 and d[0][0] == d[1][0]:
            notes.append(f"{text[ts:te]}{kind}＝{src}の {hm(d[0][1])} と {hm(d[1][1])} のどちらか決められん"); status = "hold"; continue
        ok = d[0][1]; fixes.append((ts, te, fmt(ok, sty)))
        notes.append(f"{text[ts:te]}{kind}→{fmt(ok, sty)}（{src}は {hm(ok)}）"); status = "fixed" if status != "hold" else status
    for ts, te, new in sorted(fixes, reverse=True): text = text[:ts] + new + text[te:]
    return {"text": text, "status": status, "notes": notes}

def kiroku(where, iid, r):
    if r["status"] == "ok": return
    import json
    with open(os.path.expanduser("~/owner-kotoba/friday/shougou.log"), "a") as f:
        f.write(json.dumps({"at": datetime.datetime.now().strftime("%FT%H:%M"), "where": where, "id": iid, **r}, ensure_ascii=False) + "\n")

# ---- 試験：11/11 6:00 に送った「七時」の誤り（カレンダーと枝06の実際の文で） ----
CAL_1111 = "都市A→都市B XX123（9:30 A空港発→11:30 B空港着） ＠A空港 → B空港 [owner@example.com] ／LINE 11/7で変更：〈グループ〉 11/7 夜「出張 予定」■11/11（水）都市A→都市B：7:30 ホテル出発／9:30 A空港発（XX123）"
MEMO_1111 = "- 2026-11-11 海外出張（11/8〜13）：11/8 出国→11/9 都市A→11/10 都市Aで用事→11/11 XX123 都市A→都市B（朝7:30ごろ出発・9:30発）→都市B のホテル（11/11〜13）→11/13 帰国。現地時間で案内する"
def test():
    D = datetime.date(2026, 11, 11); bad = 0
    cal = refs_from(segs_for(CAL_1111, D, True))
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(MEMO_1111 + "\n- 2026-11-09 明日（11/9）は 5:00 出発のため 4:30 に電話\n"); mp = f.name
    memo = memo_refs(D, mp); os.unlink(mp)
    T600 = "おはようございます、オーナー様。六時でございます。七時にホテルをご出発、九時半の便で目的地へ向かわれます。お支度をお願いいたします。"
    cases = [  # (名前, 文, cal, memo, 期待の状態, 期待の文に含む)
        ("6:00の誤り（カレンダー）", T600, cal, memo, "fixed", "七時半にホテルをご出発"),
        ("6:00の誤り（枝06だけ）", T600, {"出発": set(), "発": set()}, memo, "fixed", "七時半にホテルをご出発"),
        ("8:20 の正しい文", "7:30にホテルをご出発のお時間です。\nXX123は9:30発、受付の締め切りは8:45です。", cal, memo, "ok", "7:30にホテルをご出発"),
        ("21:30 の「7:00ご出発」", "明日は7:00ご出発です。", cal, memo, "fixed", "7:30ご出発"),
        ("便の時刻の誤り", "XX123は9:00発です。", cal, memo, "fixed", "9:30発"),
        ("0:26 の正しい漢数字", "明朝は七時半にホテルをご出発、九時半A空港発の XX123 で都市Bへ", cal, memo, "ok", "七時半"),
        ("今の時刻だけ（照らさん）", "六時でございます。お支度をお願いいたします。", cal, memo, "ok", "六時"),
        ("別の日の 5:00 は混ぜん（遠い時刻は直さん）", "5:00ご出発", {"出発": set(), "発": set()}, memo, "unverified", "5:00ご出発"),
        ("全角の「：」の後ろの時刻", "都市A→都市B：7:00 ホテルご出発", cal, memo, "fixed", "7:30 ホテルご出発"),
    ]
    # 11/12 C：「7:00→6:00 に早めた」は新しい 6:00 が正（11/13 の帰国）
    m13 = refs_from(segs_for("- 2026-11-12 11/13 帰国：ホテル出発を7:00→6:00（現地時間）に早めた", datetime.date(2026, 11, 13), False))
    ok13 = m13["出発"] == {360}; bad += not ok13
    print(("✅" if ok13 else "❌"), "「7:00→6:00」は 6:00 と読む", sorted(m13["出発"]))
    if memo["出発"] != {450}: print(f"❌ 枝06 から取った出発 {sorted(memo['出発'])}（期待 [450]＝7:30）"); bad += 1
    if cal["出発"] != {450} or cal["発"] != {570}: print(f"❌ カレンダーから取った {cal}"); bad += 1
    for name, t, c, mm, st, want in cases:
        r = shougou(t, D, cal=c, memo=mm)
        ok = r["status"] == st and want in r["text"]
        bad += not ok
        print(("✅" if ok else "❌"), name, r["status"], "｜", " / ".join(r["notes"]) or "-", "｜", r["text"][:60].replace("\n", " "))
    print("全部通った" if not bad else f"🔴 {bad} 件ちがう"); return bad

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    if a[0] == "--test": sys.exit(test())
    r = shougou(a[0], a[1] if len(a) > 1 else None)
    print(r["status"], "｜", " / ".join(r["notes"])); print(r["text"])
