"""フライデーの索引カード（2026-11-12 本人「AIが読みやすい形で・1秒未満で読む」）
記録（脳.md・学び・枝01〜08・会話の直近3日）を1行=1枚の小さなカードに切って索引にし、
質問に関係する上位5枚だけを AI に渡す。索引は元のファイルが変わった時だけ作り直す（キャッシュ）。
言葉の当て方＝文字の2字の組（日本語は単語に切らんでも当たる）×珍しさの重み。
試し: python3 ~/bin/friday_card.py "服のサイズ"
"""
import os, re, json, math, glob, time, pickle, datetime
HOME = os.path.expanduser("~")
K = os.path.join(HOME, "owner-kotoba")
CACHE = os.path.join(K, "friday/card_index.pkl")

def _srcs():
    s = [os.path.join(K, "friday/脳.md"), os.path.join(K, "friday/manabi.md")]
    s += sorted(glob.glob(os.path.join(K, "master/枝/0[1-8]_*.md")))
    s += sorted(glob.glob(os.path.join(K, "master/枝/06_今やっとる事/*.md")))
    s += sorted(glob.glob(os.path.join(K, "friday/kaimono/*.md")))
    today = datetime.date.today()
    s += [p for p in (os.path.join(K, f"friday/会話/{today - datetime.timedelta(days=i)}.md") for i in range(3)) if os.path.exists(p)]
    return [p for p in s if os.path.exists(p)]

def _bi(t):
    t = re.sub(r"\s+", "", t.lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}

def _cards(path):
    name = os.path.relpath(path, K)
    try: txt = open(path, encoding="utf-8").read()
    except Exception: return []
    out = []
    if "/会話/" in path:   # 会話は ### 時刻 の塊ごと
        day = os.path.basename(path)[:-3]
        for blk in re.split(r"\n(?=### )", txt):
            b = blk.strip()
            if b.startswith("### "): out.append((f"{name}", f"{day} {b[:700]}"))
        return out
    head = ""
    for l in txt.splitlines():
        s = l.strip()
        if not s: continue
        if s.startswith("#"): head = s.lstrip("# ")[:60]; continue
        if len(s) < 12: continue
        out.append((f"{name}｜{head}", s[:500]))
    return out

def build():
    srcs = _srcs(); key = [(p, os.path.getmtime(p)) for p in srcs]
    try:
        c = pickle.load(open(CACHE, "rb"))
        if c["key"] == key: return c
    except Exception: pass
    cards, seen = [], set()
    for p in srcs:
        for where, body in _cards(p):
            if body in seen: continue      # 脳.md と枝に同じ行がある＝1枚だけ
            seen.add(body); cards.append((where, body, _bi(body)))
    df = {}
    for _, _, b in cards:
        for g in b: df[g] = df.get(g, 0) + 1
    n = len(cards); idf = {g: math.log((n + 1) / (v + 0.5)) for g, v in df.items()}
    c = {"key": key, "cards": cards, "idf": idf}
    try:
        tmp = CACHE + ".tmp"; pickle.dump(c, open(tmp, "wb")); os.replace(tmp, CACHE)
    except Exception: pass
    return c

STOP = _bi("オーナー様フライデー引用返信に対して教えて") | _bi("してくださいありがとうございます")
def search(q, k=5, mx=0.0):
    c = build(); idf = c["idf"]
    qb = {g for g in _bi(q) if g not in STOP and idf.get(g, 0) > 1.5}   # よく出る組は効かんので外す
    if not qb: return []
    scored = []
    for where, body, b in c["cards"]:
        hit = qb & b
        if len(hit) < 2: continue
        s = sum(idf[g] for g in hit) / (1 + 0.15 * math.log(1 + len(b)))   # 長いカードが勝ちすぎんように
        scored.append((s, where, body))
    scored.sort(reverse=True)
    if not scored: return []
    top = scored[0][0]
    return [(w, b) for s, w, b in scored[:k] if s >= top * 0.35]

def cards_text(q, k=5):
    rs = search(q, k)
    if not rs: return ""
    return "\n".join(f"- 〔{w}〕{b}" for w, b in rs)

if __name__ == "__main__":
    import sys
    t0 = time.time(); c = build(); print(f"カード {len(c['cards'])}枚・索引 {(time.time()-t0)*1000:.0f}ms")
    for q in sys.argv[1:] or ["家族の服のサイズ", "ポイントの事後登録どうなった", "荷物の伝票番号", "美容院の予約いつ", "お店の住所"]:
        t0 = time.time(); r = cards_text(q); print(f"\n[{(time.time()-t0)*1000:.0f}ms] {q}\n{r[:1200]}")
