#!/usr/bin/env python3
"""フライデーの聞き取り＝持ち主の事を「聞いて」穴（ノード）を埋めていく道具。

持ち主の情報はこのリポに入っていない。フライデーは最初、何も知らない。
setup/shitsumon.json の質問1つ＝穴1つ。答えを聞くたびに記録の木（幹 MASTER.md と枝 01〜08）に書き込む。
埋まった事は毎回の返事の前に読む「脳.md」に入る（agent/friday-noh.py）。

使い方：
  friday-kikitori init             記録の木（~/owner-kotoba/master/…）を穴つきで作る。もうある所は消さず、足りん穴だけ足す
  friday-kikitori ask              ターミナルで1問ずつ聞いて埋める（最初のセットアップ向け・Enter で飛ばす・q で終わる）
  friday-kikitori status           埋まった数と、残っている穴
  friday-kikitori next [数]        次に聞く穴（必須→順番。今日もう聞いた物と「言わん」と言われた物は外す）
  friday-kikitori asked <id>       LINE で聞いた印（同じ日に同じ事を2回聞かない）
  friday-kikitori fill <id> "<答え>" [--himitsu]   答えで穴を埋める。--himitsu か質問に himitsu があれば、値は鍵（キーチェーン）にだけ入れる
  friday-kikitori fill <id> --pass 「言いたくない」と言われた。もう聞かない
  friday-kikitori noh              脳.md に入れる「まだ知らん事」の節を出す（friday-noh.py が呼ぶ）
  friday-kikitori apply-name       呼び名が埋まったら、~/bin のフライデーの文の「オーナー」を呼び名に置き換える
記録の置き場は環境変数 FRIDAY_KOTOBA（無ければ ~/owner-kotoba）。
"""
import datetime, json, os, re, subprocess, sys

H = os.path.expanduser("~")
K = os.environ.get("FRIDAY_KOTOBA", os.path.join(H, "owner-kotoba"))
HERE = os.path.dirname(os.path.realpath(__file__))
QS = next((p for p in (os.path.join(HERE, "shitsumon.json"), os.path.join(H, "bin", "friday-shitsumon.json")) if os.path.exists(p)), None)
LOG = os.path.join(K, "friday", "kikitori.jsonl")
MIKI = "未記入"
EDA = {
    "MASTER": ("master/MASTER.md", "マスターコンテキスト（幹）— 持ち主"),
    "01_人": ("master/枝/01_人.md", "01 人 — どんな人か"),
    "02_話し方": ("master/枝/02_話し方.md", "02 話し方 — 口調と読み取り"),
    "03_好みと目標": ("master/枝/03_好みと目標.md", "03 好みと目標"),
    "04_仕事と会社": ("master/枝/04_仕事と会社.md", "04 仕事と会社"),
    "05_道具とスキル": ("master/枝/05_道具とスキル.md", "05 道具とサービス"),
    "06_今やっとる事": ("master/枝/06_今やっとる事.md", "06 今やっとる事（新しい順・終わった物は「済」の下へ）"),
    "07_決まりとミス": ("master/枝/07_決まりとミス.md", "07 決まりとミス"),
    "08_お金と手続き": ("master/枝/08_お金と手続き.md", "08 お金と手続き（値は書かない・鍵の名前だけ）"),
}
LINE_RE = re.compile(r"^- \[( |x|-)\] (?P<id>[0-9]{2}\.[a-z_]+)｜(?P<mid>[^：]+)：(?P<val>.*)$")


def qs():
    return json.load(open(QS, encoding="utf-8"))["nodes"]


def path(eda):
    return os.path.join(K, EDA[eda][0])


def node_line(n, val=None, mark=" "):
    return f"- [{mark}] {n['id']}｜{n['midashi']}：{val if val is not None else '（' + MIKI + '）'}"


def init():
    os.makedirs(os.path.join(K, "master", "枝"), exist_ok=True)
    for d in ("friday", "friday/会話", "friday/mimi", "friday/plan", "friday/manabi", "torisetsu"):
        os.makedirs(os.path.join(K, d), exist_ok=True)
    by = {}
    for n in qs():
        by.setdefault(n["eda"], []).append(n)
    for eda, (rel, title) in EDA.items():
        p = os.path.join(K, rel)
        if not os.path.exists(p):
            if eda == "MASTER":
                body = [f"# {title}", "", "## 幹（30秒で分かる持ち主）", *[node_line(n) for n in by.get(eda, [])], "",
                        "## 枝（話題で開く）", "| 枝 | 開く時 | ファイル |", "|---|---|---|",
                        *[f"| {k[:2]} | {EDA[k][1].split('—')[-1].strip()} | 枝/{k}.md |" for k in EDA if k != "MASTER"], "",
                        "## 育て方", "- 穴（`- [ ]`）は friday-kikitori で聞いて埋める。分かった新しい事は `master-add <枝番号> \"<事実>\"` で枝に足す"]
            else:
                body = [f"# {title}", "", "## 聞いて分かった事", *[node_line(n) for n in by.get(eda, [])], "", "## 足した事（新しい順）"]
                if eda == "06_今やっとる事":
                    body += ["", "## 済"]
            open(p, "w", encoding="utf-8").write("\n".join(body) + "\n")
            continue
        s = open(p, encoding="utf-8").read()
        have = {m.group("id") for m in map(LINE_RE.match, s.splitlines()) if m}
        add = [node_line(n) for n in by.get(eda, []) if n["id"] not in have]
        if add:
            open(p, "a", encoding="utf-8").write("\n" + "\n".join(add) + "\n")
    core = os.path.join(K, "torisetsu", "CORE.md")
    if not os.path.exists(core):
        open(core, "w", encoding="utf-8").write("# CORE — 持ち主の芯（毎回読む）\n\n"
                                                "- 口調・長さ＝master/MASTER.md の「フライデーの口調」と 枝/02_話し方.md\n"
                                                "- 好み＝枝/03・やってはいけない事＝枝/07（埋まるまでは「外に出す行為は本人の言葉の1回だけ」）\n"
                                                "- 毎晩の学び（friday-manabi.sh）がここに足していく\n")
    mn = os.path.join(K, "friday", "manabi.md")
    if not os.path.exists(mn):
        open(mn, "w", encoding="utf-8").write("# フライデーの学び（毎晩自動で書き直し）\n\n## A. 持ち主の理解（好み・言葉の意味・いつも欲しい形）\n\n"
                                              "## B. 直された事 → 決まり（🔁＝繰り返した回数）\n\n## C. 先回り（言われる前にやる）\n\n## D. 言われた回数の推移\n")
    print("記録の木を作った：", os.path.join(K, "master"))
    status()


def all_nodes():
    """[(n, 状態, 値)]  状態＝" " 穴・"x" 埋まった・"-" 言わん"""
    st = {}
    for eda in EDA:
        p = path(eda)
        if not os.path.exists(p):
            continue
        for l in open(p, encoding="utf-8"):
            m = LINE_RE.match(l.rstrip("\n"))
            if m:
                st[m.group("id")] = (l[3], m.group("val"))
    return [(n, *st.get(n["id"], (" ", ""))) for n in qs()]


def logs():
    try:
        return [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        return []


def log(**kw):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    kw["at"] = datetime.datetime.now().isoformat(timespec="seconds")
    open(LOG, "a", encoding="utf-8").write(json.dumps(kw, ensure_ascii=False) + "\n")


def nexts(k=3):
    today = datetime.date.today().isoformat()
    asked = {x["id"] for x in logs() if x.get("do") == "asked" and x["at"][:10] == today}
    hole = [n for n, s, _ in all_nodes() if s == " " and n["id"] not in asked]
    hole.sort(key=lambda n: (-n.get("hissu", 0)))
    return hole[:k]


def status():
    a = all_nodes()
    done = sum(1 for _, s, _ in a if s == "x"); pas = sum(1 for _, s, _ in a if s == "-")
    print(f"埋まった {done} / {len(a)}（言わん {pas}・穴 {len(a) - done - pas}）")
    for n, s, v in a:
        if s == " ":
            print(f"  {'★' if n.get('hissu') else '・'} {n['id']}  {n['q']}")


def kagi(nid, val):
    name = f"friday.{nid}"
    r = subprocess.run(["security", "add-generic-password", "-U", "-s", name, "-a", "friday", "-w", val], capture_output=True)
    if r.returncode:
        raise SystemExit(f"鍵に入れられんかった（{name}）")
    return name


def fill(nid, val, himitsu=False, passed=False):
    n = next((x for x in qs() if x["id"] == nid), None)
    if not n:
        raise SystemExit(f"そんな穴は無い：{nid}")
    p = path(n["eda"])
    if not os.path.exists(p):
        init()
    day = datetime.date.today().isoformat()
    if passed:
        line = node_line(n, f"（本人が言わんと言うた・{day}）", "-")
    elif himitsu or n.get("himitsu"):
        line = node_line(n, f"鍵 {kagi(nid, val)} に入れた（値はここに書かん・{day}）", "x")
    else:
        line = node_line(n, f"{val.strip()}（{day} 本人）", "x")
    out, hit = [], False
    for l in open(p, encoding="utf-8"):
        m = LINE_RE.match(l.rstrip("\n"))
        if m and m.group("id") == nid:
            out.append(line + "\n"); hit = True
        else:
            out.append(l)
    if not hit:
        out.append(line + "\n")
    open(p, "w", encoding="utf-8").writelines(out)
    log(do="pass" if passed else "fill", id=nid)
    print("埋めた：", line)
    if nid == "00.yobina" and not passed:
        print("呼び名が入った。~/bin の文にも反映するなら：friday-kikitori apply-name")


def noh():
    a = all_nodes()
    done = sum(1 for _, s, _ in a if s == "x"); hole = [n for n, s, _ in a if s == " "]
    if not hole:
        return ""
    today = datetime.date.today().isoformat()
    n_today = sum(1 for x in logs() if x.get("do") == "asked" and x["at"][:10] == today)
    nx = nexts(3)
    lines = [f"## 🕳️ まだ知らん持ち主の事（聞き取り：{done}/{len(a)} 埋まった・今日聞いた {n_today}/3）",
             "- 持ち主の情報は最初は空。勝手に決めつけず、聞いて埋める。埋まった事は master/MASTER.md と master/枝/ にある",
             "- 頼みに答えるのに要る事が穴なら、「記録にありません」で止めず、その穴の質問をそのまま聞く（答えをもらったら頼みを続ける）",
             "- それ以外は、返事の最後に1問だけ添えて聞く。1日3問まで。急ぎの頼み・夜22時〜朝8時・本人が忙しそうな時は聞かない",
             "- 聞いたら `~/bin/friday-kikitori asked <id>`。答えが来たら `~/bin/friday-kikitori fill <id> \"<答え>\"`。「言いたくない」「パス」なら `fill <id> --pass`",
             "- himitsu の穴（住所・電話など）は fill が鍵に入れる。値を返事・記録・メモに書き直さない"]
    if n_today < 3 and nx:
        lines.append("次に聞く事（上から）：")
        lines += [f"- {n['id']}：{n['q']}（使い道：{n['naze']}）" for n in nx]
    return "\n".join(lines)


def ask():
    print("フライデーの聞き取り。Enter で飛ばす・「パス」で今後聞かない・q で終わる\n")
    for n, s, _ in all_nodes():
        if s != " ":
            continue
        print(("★ " if n.get("hissu") else "") + n["q"])
        try:
            a = input("> ").strip()
        except EOFError:
            break
        if a.lower() == "q":
            break
        if not a:
            continue
        if a in ("パス", "pass"):
            fill(n["id"], "", passed=True)
        else:
            fill(n["id"], a)
        print()
    status()


def apply_name():
    v = next((v for n, s, v in all_nodes() if n["id"] == "00.yobina" and s == "x"), None)
    if not v:
        raise SystemExit("呼び名がまだ穴。先に fill 00.yobina")
    name = re.sub(r"（.*$", "", v).strip()
    name = re.sub(r"(様|さん)$", "", name)
    n = 0
    for f in os.listdir(os.path.join(H, "bin")):
        p = os.path.join(H, "bin", f)
        if not (f.startswith(("friday", "mimi")) and os.path.isfile(p)):
            continue
        try:
            s = open(p, encoding="utf-8").read()
        except Exception:
            continue
        if "オーナー" in s:
            open(p, "w", encoding="utf-8").write(s.replace("オーナー", name)); n += 1
    print(f"「オーナー」→「{name}」：{n} ファイル")


if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    c = a[0]
    if c == "init": init()
    elif c == "ask": init(); ask()
    elif c == "status": status()
    elif c == "next":
        for n in nexts(int(a[1]) if len(a) > 1 else 3): print(f"{n['id']}\t{n['q']}")
    elif c == "asked": log(do="asked", id=a[1]); print("聞いた印：", a[1])
    elif c == "fill":
        if len(a) < 3: raise SystemExit('fill <id> "<答え>" か fill <id> --pass')
        fill(a[1], "" if a[2] == "--pass" else a[2], himitsu="--himitsu" in a, passed=a[2] == "--pass")
    elif c == "noh": print(noh())
    elif c == "apply-name": apply_name()
    else: print(__doc__)
