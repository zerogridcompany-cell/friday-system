#!/usr/bin/env python3
# フライデーの先回り（11/17 オーナー「来る前に潰してほしい」）
# 毎晩 3:40：昨日の返事から「記録にない・確認できません・〜しましょうか」で止まった物を拾い、
# 止まらずに済んだ物（A）を今の返事係にもう一回通す（LINE には送らん・何も変えさせん）。
# まだ止まる物は kotowari/赤.md に書く → 4:45 の直し係が一番先に直す。全部 shiken.json に貯める。
import os, re, sys, json, glob, time, subprocess
from datetime import date, timedelta
HOME = os.path.expanduser("~")
K = HOME + "/owner-kotoba/friday/kotowari/"
KAIWA = HOME + "/owner-kotoba/friday/会話/"
CLAUDE = HOME + "/.local/bin/claude" if os.path.exists(HOME + "/.local/bin/claude") else "claude"
os.makedirs(K, exist_ok=True)

KOTOWARI = re.compile(r"記録(?:に|には|から|で|上)[^。\n]{0,15}(?:無|な[いく]|ありません|見当たり|確認でき|特定|分かり|わかり)|メモ(?:に|には)[^。\n]{0,8}(?:無|な[いく]|ありません)|見当たりません|見つかりません(?:でした)?|特定(?:でき|出来)(?:ず|ませ|な)|(?:お伝え|お答え|お調べ)(?:でき|出来)(?:ず|ませ)|確認(?:でき|出来)(?:ず|ませ|な)|分かりかね|わかりかね|存じ(?:ません|あげ)|把握(?:して)?(?:おりませ|できて|出来て)|情報(?:が|は)(?:ございません|ありません)|残っておりません|教えていただけ")
SAIKAKUNIN = re.compile(r"よろしいでしょうか|いたしましょうか|しましょうか|いかがなさいますか|ご指示(?:を|ください)|お知らせください")
YATTE = re.compile(r"やって|進めて|入れて|お願い|頼む|しといて|やっといて|調べて|教えて|登録して|追加して|変えて|直して")
NOKORI = re.compile(r"記録(?:に|には|から|で)[^。\n]{0,15}(?:無|な[いく]|ありません|見当たり|確認でき|特定|分かり)|確認(?:でき|出来)(?:ず|ませ)|特定(?:でき|出来)|(?:お伝え|お答え)(?:でき|出来)|見当たりません|見つかりません|しましょうか|教えていただけ")
SHIKEN_MAE = "（試験：本物の頼みと同じに調べて答える。ただし予定・記録・メモ・メール・送信・ログイン・画面操作など何かを変える事はせず、やる事は『やる事：…』と1行で書くだけ）\n"

def hirou(day):
    f = KAIWA + day + ".md"
    if not os.path.exists(f): return []
    out = []
    for blk in re.split(r"\n(?=### )", open(f).read()):
        m = re.match(r"### (\d\d:\d\d)", blk)
        if not m: continue
        parts = re.split(r"\n- (オーナー|フライデー): ", "\n" + blk)
        ask = ans = ""
        for i in range(1, len(parts) - 1, 2):
            if parts[i] == "オーナー": ask = parts[i + 1]
            else: ans = parts[i + 1]
        if not ans: continue
        k = KOTOWARI.search(ans)
        s = SAIKAKUNIN.search(ans) if YATTE.search(ask) else None
        if k or s:
            out.append({"day": day, "t": m.group(1), "hit": (k or s).group(0), "ask": ask[:900], "ans": ans[:600]})
    return out

def claude(p, model="opus", timeout=600):
    r = subprocess.run([CLAUDE, "-p", "--model", model], input=p, capture_output=True, text=True, timeout=timeout)
    return r.stdout

def wakeru(c):
    if not c: return c
    P = """下はLINE秘書bot「フライデー」への頼み(ask)と返事(ans)。各件を判定してJSON配列だけを出す（説明なし）。
各要素 {"i":番号,"k":"A"|"B","why":"15字以内"}
A＝止まらずに済んだ：世の中の一般の事（決まり・窓口・店・値段・やり方・場所）をネットで調べれば答えられた／写真や画面から読み取れた／頼まれた動きをやらずに「記録にない」「〜しましょうか」「教えてください」で止めた
B＝正しい：外の状態を実際に確かめた上での事実／本人しか知らん事を1回だけ聞いた／お金・送信など外に出す前の確認
"""
    j = [{"i": i, "ask": o["ask"][:400], "ans": o["ans"][:400]} for i, o in enumerate(c)]
    m = re.search(r"\[.*\]", claude(P + json.dumps(j, ensure_ascii=False)), re.S)
    for x in (json.loads(m.group(0)) if m else []):
        if 0 <= x.get("i", -1) < len(c): c[x["i"]]["k"] = x.get("k"); c[x["i"]]["why"] = x.get("why", "")
    return c

def saisei(o):
    # 今の返事係にもう一回通す（別の python で＝落ちても止まらん）
    code = r'''
import os, sys, json, time
sys.argv = ["friday-agent.py", "mini-test"]
src = open(os.path.expanduser("~/bin/friday-agent.py")).read()
g = {"__name__": "sakimawari", "__file__": os.path.expanduser("~/bin/friday-agent.py")}
exec(compile(src[:src.index("ALIVE = os.path.join(HOME")], "friday-agent", "exec"), g)
g["LOG"] = os.path.expanduser("~/owner-kotoba/friday/kotowari/saisei.log")
o = json.loads(sys.stdin.read())
q, typ = o["q"], "text"
if "（電話の係からの質問" in q and "質問：" in q:   # 昔の電話の頼みは、今の頼みの文に入れ替えて電話として通す
    i = src.index('m["text"] = ("（電話の係'); j = src.index('\\n質問：', i)
    q = eval(src[i + len('m["text"] = '):j] + '")') + "\n質問：" + q.split("質問：", 1)[1]; typ = "phone_ask"
out = g["answer"]({"id": "sakimawari", "type": typ, "at": o["day"] + " " + o["t"], "text": q}, []) or ""
print("SAISEI" + json.dumps(out, ensure_ascii=False), flush=True)
os._exit(0)
'''
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "-c", code], input=json.dumps({"day": o["day"], "t": o["t"], "q": SHIKEN_MAE + o["ask"]}, ensure_ascii=False),
                           capture_output=True, text=True, timeout=600)
        m = re.search(r"^SAISEI(.*)$", r.stdout, re.M)
        out = json.loads(m.group(1)) if m else "（返事なし）" + r.stderr[-300:]
    except subprocess.TimeoutExpired:
        out = "（10分で返らず）"
    o["ima"] = out[:1200]; o["sec"] = int(time.time() - t0)
    o["nokori"] = [x.group(0) for x in NOKORI.finditer(out)] or ([] if out and not out.startswith("（") else ["返事なし"])
    return o

def main():
    a = sys.argv[1:]
    if a and a[0] == "--saisei":           # 直し係の確かめ用：shiken.json の n 番をもう一回
        sh = json.load(open(K + "shiken.json")); o = saisei(dict(sh[int(a[1])]))
        print(json.dumps({"n": a[1], "nokori": o["nokori"], "ima": o["ima"][:400]}, ensure_ascii=False)); return
    day = a[0] if a else (date.today() - timedelta(days=1)).isoformat()
    c = wakeru(hirou(day))
    A = [o for o in c if o.get("k") == "A"][:5]
    for o in A: saisei(o)
    sh = json.load(open(K + "shiken.json")) if os.path.exists(K + "shiken.json") else []
    have = {(x["day"], x["t"]) for x in sh}
    sh += [{k: o[k] for k in ("day", "t", "hit", "why", "ask", "ans") if k in o} for o in A if (o["day"], o["t"]) not in have]
    json.dump(sh, open(K + "shiken.json", "w"), ensure_ascii=False, indent=1)
    aka = [o for o in A if o["nokori"]]
    if aka:
        with open(K + "赤.md", "a") as f:
            for o in aka:
                n = next(i for i, x in enumerate(sh) if (x["day"], x["t"]) == (o["day"], o["t"]))
                f.write(f"\n## {o['day']} {o['t']}（shiken.json {n}番・まだ止まる：{'・'.join(o['nokori'][:3])}）\n- 頼み：{o['ask'][:300]}\n- 前の返事：{o['ans'][:200]}\n- 今の返事：{o['ima'][:400]}\n- 確かめ：`python3 ~/bin/friday-sakimawari.py --saisei {n}`\n")
    line = f"{time.strftime('%F %T')} {day} 拾った{len(c)} 止まらず済んだ(A){len(A)} 今も止まる{len(aka)} " + " ".join(f"{o['t']}:{'赤' if o['nokori'] else '◯'}" for o in A)
    open(K + "run.log", "a").write(line + "\n"); print(line)

if __name__ == "__main__":
    main()
