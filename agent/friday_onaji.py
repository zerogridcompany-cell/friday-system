"""同じミスの門（11/14 オーナー「同じこと言いたくない・ここまた間違ってるよ、が無い学習方法に」）
- 直された瞬間に覚える：本人の言葉が「直し」なら、その場で『次から何を確かめるか』を1つ作って onaji.json に足す（夜を待たん）
- 送る前に確かめる：返事の案に関係する過去の直し（言葉が当たる物）だけを読み、外れとったら直してから送る。当たらん時は0秒
- 回数：直された回数（n）を数える。同じ物の n が増えたら、それは門が効いてへん印＝夜の直し係が先にコードで直す"""
import json, os, re, time, datetime, threading
F = os.path.expanduser("~/owner-kotoba/friday/manabi/onaji.json")
LOG = os.path.expanduser("~/owner-kotoba/friday/manabi/onaji.log")
LK = threading.Lock()
NAOSHI = re.compile(r"違う|ちゃう|ちゃうよ|ちがう|また[^\s]{0,8}(間違|ミス|同じ|やっ|言っ|なっ)|さっきも|前も言|何回|何度|言ったよね|言うたやん|じゃなくて|やなくて|そうじゃない|そうやない|間違|直して|おかしい|ずれて|遅い|長い|分かりにく|わかりにく|そこじゃない|聞いてない|頼んでない|勝手に")
def log(s):
    with open(LOG, "a") as f: f.write(f"{datetime.datetime.now():%m-%d %H:%M:%S} {s}\n")
def load():
    try: return json.load(open(F, encoding="utf-8"))
    except Exception: return []
def save(L):
    tmp = F + ".tmp"; json.dump(L, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, F)
def is_naoshi(text): return bool(NAOSHI.search(text or ""))

MANABU = """あなたはフライデー（LINE の執事 AI）の学び係。オーナー様が今、フライデーの前の返事を直した。
次から同じ事を二度と言わせんための「送る前の確かめ」を作る。

フライデーの前の返事:
{prev}

オーナー様の今の言葉:
{text}

今ある確かめ（同じ意味の物があればそれの id を返す）:
{ima}

出す物（最後の1行だけ・JSON）:
ONAJI {{"naoshi": true か false（本当に直し・不満か。ただの質問や新しい頼みなら false）, "id": 同じ意味の既存の id か null, "kotoba": ["この確かめが要る場面に出る言葉を3〜8個（本人の頼みか返事の案に出る語・短く）"], "check": "送る前に返事の案で確かめる事を1文（何が×で、どうなら○か・具体的に）", "rei": "本人の言葉そのまま（40字まで）"}}"""

def learn(prev, text, run):
    """直しを1つ覚える。run(prompt, timeout)->str は呼ぶ側の Claude（Sonnet）"""
    try:
        L = load()
        ima = "\n".join(f"{x['id']}: {x['check']}" for x in L[-60:]) or "（なし）"
        out = run(MANABU.format(prev=(prev or "（なし）")[:1500], text=text[:800], ima=ima), 60)
        m = re.findall(r"ONAJI (\{.*\})", out or "")
        j = json.loads(m[-1]) if m else None
        if not j or not j.get("naoshi") or not j.get("check"): log(f"直しやない／取れん「{text[:30]}」"); return
        with LK:
            L = load(); now = time.strftime("%Y-%m-%d %H:%M")
            hit = next((x for x in L if j.get("id") and x["id"] == j["id"]), None)
            if hit:
                hit["n"] += 1; hit["last"] = now; hit["rei"] = (hit.get("rei", "") + "／" + j.get("rei", ""))[-200:]
                hit["kotoba"] = list(dict.fromkeys(hit["kotoba"] + j.get("kotoba", [])))[:15]
                log(f"🔁 {hit['id']} n={hit['n']} {hit['check'][:50]}")
            else:
                nid = f"o{len(L)+1:03d}"
                L.append({"id": nid, "kotoba": j.get("kotoba", [])[:10], "check": j["check"], "rei": j.get("rei", ""), "n": 1, "first": now, "last": now})
                log(f"新 {nid} {j['check'][:60]}")
            save(L)
    except Exception as e:
        log(f"learn 失敗 {type(e).__name__} {e}")

MON = """あなたはフライデー（オーナー様専属の LINE 執事 AI）の送る前の確かめ係。
下の「過去にオーナー様から直された事」に、返事の案が外れていないか確かめる。

過去に直された事（守る）:
{kimari}

オーナー様の言葉:
{text}

返事の案:
{draft}

外れが無ければ OK とだけ出す。外れがあれば、その所だけ直した返事の全文を出す。
- 口調・事実・URL・ASK/IMG の行はそのまま。新しい事実・数字は足さん
- やっていない事を「しました」「おかけします」「確認中」と書かん（約束を増やさん）。断定が外れなら、断定を外して「どこを確かめたか／次に何を確かめるか」に直す
- 直した理由・注釈・（※…）・前置きは書かん。オーナー様に送る本文だけ"""

def mon(text, draft, run, maxn=8):
    """関係する過去の直しだけで確かめる。当たる物が無ければ何もせず返す"""
    if not draft or len(draft) < 60: return draft
    L = load()
    if not L: return draft
    hay = (text or "") + "\n" + draft
    STOP = {"オーナー様", "オーナー", "フライデー", "です", "ます", "ありがとう", "今日", "これ", "それ", "ください"}
    hits = [x for x in L if any(k and len(k) >= 2 and k not in STOP and k in hay for k in x.get("kotoba", []))]
    if not hits: return draft
    hits.sort(key=lambda x: -x.get("n", 1)); hits = hits[:maxn]
    kimari = "\n".join(f"- （{x['n']}回）{x['check']}" for x in hits)
    t0 = time.time()
    out = (run(MON.format(kimari=kimari, text=(text or "")[:800], draft=draft), 45) or "").strip()
    out = "\n".join(l for l in out.splitlines() if not l.startswith("🔋") and not re.match(r"^\s*[（(]※", l) and not l.startswith("※")).strip()
    # 11/14 夜 「外れはありません。OK」のような一言がそのまま返事として出る筋があった＝下書きよりずっと短くて OK／外れ無し を言うとる物は「直し無し」
    _s = out.strip() if out else ""
    _ok = (not _s) or _s.upper().rstrip("。.！! ") == "OK" or (len(_s) < max(40, len(draft) * 0.4) and re.search(r"\bOK\b|外れ(は|が)?(あり|な|無)|問題(は|が)?(あり|な|無)|直す所(は|が)?(あり|な|無)", _s, re.I))
    if _ok:
        log(f"門 OK {len(hits)}件 {time.time()-t0:.0f}秒"); return draft
    if len(out) < 10: return draft
    log(f"門 直した {len(hits)}件（{','.join(x['id'] for x in hits)}） {time.time()-t0:.0f}秒")
    return out
