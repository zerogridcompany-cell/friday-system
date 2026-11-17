"""フライデーの速い道（11/03 オーナー「タスクを渡して10秒以内に完了」）
決まった形の頼みは Opus を起こさずに道具を直接回して返す。外れたら None を返す＝いつもの道（Opus）へ。
- タクシー：「◯◯までタクシー」→ go-taxi junbi → 料金を見せて ASK「呼んで」（呼ぶのはボタンの1回だけ）
- ボタン：action が FAST: で始まる物は道具を直接（料金の画面が同じか確かめてから押す）
"""
import os, re, subprocess, json, time
HOME = os.path.expanduser("~")
GT = os.path.join(HOME, "bin/go-taxi")
J = "/tmp/ipm/go/junbi.txt"

TAXI = re.compile(r"タクシー|ＧＯ|(?<![A-Za-z])GO(?![A-Za-z])")
NOT_FAST = re.compile(r"キャンセル|やめ|止め|中止|呼ばな|予約|明日|あした|時に|時から|後で|あとで|いくら|料金だけ|追加|支払い|カード|スキル|練習|シミュ|直し|遅い|なんで|どう|？|\?|履歴|領収")
PATS = [
    re.compile(r"(?:今から|今|いま|ここから|今いる(?:ところ|とこ)から|現在地から)?\s*(?P<d>[^、。,！!]{2,30}?)\s*(?:まで|に|へ)\s*(?:の)?\s*(?:タクシー|(?<![A-Za-z])GO(?![A-Za-z]))", re.I),
    re.compile(r"(?:タクシー|(?<![A-Za-z])GO(?![A-Za-z]))\s*(?:で|を|呼んで|よんで)?\s*、?\s*(?P<d>[^、。,！!]{2,30}?)\s*(?:まで|に|へ)", re.I),
]
def taxi_dest(text):
    t = (text or "").strip()
    if t.startswith("（引用返信") or t.startswith("（ボタン") or t.startswith("（電話"): return None
    t = re.sub(r"^（声のメッセージ）", "", t)
    if not TAXI.search(t) or NOT_FAST.search(t) or len(t) > 60: return None
    for p in PATS:
        m = p.search(t)
        if m:
            d = re.sub(r"^(今から|今|いま|ここから)", "", m.group("d")).strip()
            if d and not re.search(r"タクシー|呼|ＧＯ|(?<![A-Za-z])GO(?![A-Za-z])|家から|ここ$", d): return d
    return None

def _read():
    r = {}
    try:
        for l in open(J, encoding="utf-8"):
            if "=" in l: k, v = l.rstrip("\n").split("=", 1); r[k] = v.strip()
    except Exception: pass
    return r

def try_fast(m, log=print):
    if m.get("type", "text") != "text": 
        if not (m.get("type") == "audio" and (m.get("text") or "").startswith("（声のメッセージ）")): return None
    d = taxi_dest(m.get("text"))
    if not d: return None
    t0 = time.time(); log(f"速い道 タクシー「{d}」")
    try:
        p = subprocess.run([GT, "junbi", d, "auto"], capture_output=True, text=True, timeout=90,
                           env={**os.environ, "FRIDAY_JOB": str(m.get("id", ""))})
    except subprocess.TimeoutExpired:
        log("速い道 タクシー：時間切れ→いつもの道"); return None
    finally:
        subprocess.run([os.path.join(HOME, "bin/gamen"), "done", str(m.get("id", ""))], capture_output=True)
    res = (p.stdout.strip().splitlines() or [""])[-1]
    log(f"速い道 タクシー {time.time()-t0:.1f}秒 {res[:80]}")
    if not res.startswith("結果 OK"): return None
    r = _read()
    if not r.get("fare"): return None
    name = d   # 画面の字（候補の名前）は読み違いが多い＝頼まれた名前＋確かめの画面の住所で見せる
    addr = r.get("daddr", "")
    eta = f"・車は約{r['eta']}で参ります\n" if r.get("eta") else ""
    text = (f"オーナー様、タクシーのご用意ができました（まだお呼びしておりません）。\n"
            f"・行き先：{name}（{addr}）\n"
            f"・乗る場所：{r.get('from') or r.get('pickup') or 'GO の今の乗車地'}（GO の表示：{r.get('pickup') or '—'}）\n"
            f"・料金の目安：約{r['fare']}＋手配料\n{eta}"
            f"・お支払い：{r.get('pay') or '画面で確認できませんでした'}\n"
            f"「呼んで」を押していただいた1回だけ配車いたします。")
    ask = {"label": "呼んで", "no_label": "やめて",
           "action": f"FAST:go-taxi yobu｜料金 {r['fare']}｜行き先 {name}（{addr}）｜乗る場所 {r.get('pickup','')}｜支払い {r.get('pay','')}"
                     "（Mac mini の ~/bin/go-taxi yobu で GO の「タクシーを呼ぶ」を1回押す。料金の画面と料金が同じ時だけ。押したら撮って車番・到着時刻を返す）"}
    return text, ask

def button(msg, log=print):
    a = msg.get("ask") or {}
    act = a.get("action", "")
    if not act.startswith("FAST:go-taxi yobu"): return None
    if a.get("expired"): return None
    if msg.get("choice") != "ok":
        # 🔴 画面の鍵は頼みの番号で取って、終わったら必ず返す（11/03 返さず120秒ふさいだ）
        subprocess.Popen(["/bin/zsh", "-c", f"{GT} modoru; {HOME}/bin/gamen done"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env={**os.environ, "FRIDAY_JOB": str(msg.get("id", ""))})
        return "承知いたしました。タクシーはお呼びしておりません。"
    fare = re.search(r"料金 ([0-9,]+円)", act)
    try:
        p = subprocess.run([GT, "yobu", fare.group(1) if fare else ""], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "FRIDAY_JOB": str(msg.get("id", ""))})
    finally:
        subprocess.run([os.path.join(HOME, "bin/gamen"), "done", str(msg.get("id", ""))], capture_output=True)
    out = p.stdout.strip(); log(f"速い道 呼ぶ rc={p.returncode} {out[:120]}")
    if p.returncode != 0:
        return ("オーナー様、タクシーはまだお呼びしておりません。料金の画面が、お見せした時と変わっていたためです"
                f"（{(p.stderr or '').strip()[:60]}）。もう一度「◯◯までタクシー」とお送りください。")
    lines = [l.split(" ", 1)[1] for l in out.splitlines() if " " in l and re.search(r"分|ナンバー|到着|迎車|配車|探し|見つ|車|[0-9]{2}-[0-9]{2}|・", l)]
    return "オーナー様、タクシーをお呼びしました。\n" + "\n".join("・" + l for l in lines[:6]) + "\n（GO の画面の字をそのまま写しております。車が決まると GO からも通知が参ります）"
