#!/usr/bin/env python3
"""フライデーの耳の「毎晩の試験」（11/14 夜 オーナー「今後どんどん精度落ちていきそう。どう落ちないようにできる？」）
録ってある本物の声と、決まった言葉の場面を、本番と同じ部品（mimi_filter・mimi-watch・friday_hitori）に通して、答えが合っとるかを見る。
  A 声の門   ：shiken/koe/ の本物の声 → 書き起こし → 門。「捨てる（幻聴）」「残す（本物）」が合うか
  B 先回り   ：決まった声の文 → 先回りの係（送らん・--dry）。「送る／送らん」「答えに入っとるはずの言葉」「秒」
  C 送る前の門：1仕事1人の門に決まった文。「通す／止める」
結果＝mimi/shiken.jsonl に1行（日・点・落ちた物・秒）。前より落ちたら LINE で知らせる（friday-kenkou が朝に読む）。
🔒 オーナーに「違う・届かん・遅い」と言われた場面は、その声と正解を CASES に1行足す＝同じ外れが二度と戻らん。"""
import os, sys, json, re, time, subprocess, datetime, tempfile
H = os.path.expanduser("~"); B = H + "/bin/"; M = H + "/owner-kotoba/friday/mimi"; S = M + "/shiken"
sys.path.insert(0, B); import mimi_filter as FILT
JST = datetime.timezone(datetime.timedelta(hours=9))
ENV = {**os.environ, "PATH": H + "/.local/bin:" + H + "/bin:/opt/homebrew/bin:/usr/bin:/bin"}
C = json.load(open(S + "/cases.json"))
fails, rows = [], []
def rec(kind, name, ok, sec=0, note=""):
    rows.append({"kind": kind, "name": name, "ok": bool(ok), "sec": round(sec, 1), "note": note[:120]})
    if not ok: fails.append(f"{kind}｜{name}｜{note[:80]}")
# ---- A 声の門
for c in C["koe"]:
    t0 = time.time()
    try:   # 本番と同じ「聞く本体」（mimi_kiku.py）に通す
        o = subprocess.run([H + "/.local/share/uv/tools/mlx-whisper/bin/python", B + "mimi_kiku.py", "--one", f"{S}/koe/{c['file']}"], capture_output=True, text=True, timeout=300, env=ENV).stdout
        txt = json.loads([l for l in o.splitlines() if l.startswith("RES ")][-1][4:]).get("text")
    except Exception as e: txt = None
    if txt is None: rec("声の門", c["name"], False, time.time() - t0, "書き起こしが動かん"); continue
    ok = (txt == "") if c["expect"] == "drop" else (txt != "" and all(re.search(p, txt) for p in c.get("has", [])))
    rec("声の門", c["name"], ok, time.time() - t0, f"出た文字「{txt[:40]}」・正解={'捨てる' if c['expect']=='drop' else '残す'}")
# ---- B 先回り
for c in C["sakimawari"]:
    d = tempfile.mkdtemp(); now = datetime.datetime.now(JST).isoformat(timespec="seconds")
    open(d + "/mimi.jsonl", "w").write(json.dumps({"at": now, "text": c["koe"], "lat": c["lat"], "lon": c["lon"], "acc": 20, "file": "t.m4a", "dev": "iPhone19,7", "ie": False, "hon": c.get("hon")}, ensure_ascii=False) + "\n")
    if c.get("state"):   # 11/15 本番の状態を再現（今日もう送った数＝上限・最近送った話題）
        _n = datetime.datetime.now(JST)
        json.dump({"seen": "", "sent": {_n.strftime("%Y-%m-%d"): c["state"].get("sent", 0)},
                   "topics": [{"at": (_n - datetime.timedelta(minutes=m)).isoformat(), "topic": tp} for m, tp in c["state"].get("topics", [])]},
                  open(d + "/watch_state.json", "w"), ensure_ascii=False)
    j = None; last = ""; sec = 0
    for _try in range(2):   # 係の起動が1回こける事がある（本番も次の回でやり直す作り）＝試験も1回だけやり直す。2回ともだめなら落第
        t0 = time.time()
        subprocess.run(["/usr/bin/python3", B + "mimi-watch.py", "--dry"], capture_output=True, timeout=300,
                       env={**ENV, "MIMI_D": d, "MIMI_LINE_TALK": c.get("line", "（なし）")})
        sec = time.time() - t0
        try: L = open(d + "/watch.log").read().strip().splitlines()
        except Exception: L = []
        last = L[-1] if L else ""
        if last.startswith(("上限", )) or re.match(r"[\d-]+ [\d:]+ 上限", last):   # 上限で係に回らんかった
            j = {"send": False, "text": "", "jogen": True}; break
        for last in reversed(L):   # 11/15 判定の行を探す（後ろに別の行が付く事がある）
            m = re.search(r"\d+s \{\"send\": (true|false)", last)   # 記録の行は240字で切れる＝JSON としては読まん
            if m: break
        if m:
            t = re.search(r'"text": "(.*)', last)
            j = {"send": m.group(1) == "true", "text": (t.group(1) if t else "").replace("\\n", "\n"),
                 "do": bool(re.search(r'"do": "', last)), "nige": any("名前の頼み→返事係" in x for x in L)}; break
    if not j: rec("先回り", c["name"], False, sec, "係が返事を出さん：" + last[:60]); continue
    if "uke" in c:   # 11/15 「受けたか」＝LINE で送る・調べを返事係へ・名前の頼みを返事係へ のどれか
        uke = bool(j.get("send") or j.get("do") or j.get("nige"))
        ok = uke == c["uke"] and sec <= c.get("max_sec", 90)
        rec("先回り", c["name"], ok, sec, f"受けた={uke}（正解 {c['uke']}）{'・上限で止まった' if j.get('jogen') else ''}・send={j.get('send')}・do={j.get('do')}・返事係へ={j.get('nige')}・{sec:.0f}秒・{j.get('text','')[:30]}"); continue
    ok = bool(j.get("send")) == c["send"] and all(re.search(p, j.get("text", "")) for p in c.get("has", [])) and not any(re.search(p, j.get("text", "")) for p in c.get("not", [])) and sec <= c.get("max_sec", 90)
    rec("先回り", c["name"], ok, sec, f"send={j.get('send')}（正解 {c['send']}）・{sec:.0f}秒（上限 {c.get('max_sec', 90)}）・{j.get('text','')[:40]}")
# ---- C 送る前の門
import friday_hitori as HT
HT.recent_talk = lambda hours=3: C["mon_talk"]; HT.running_jobs = lambda: []
_log = HT.log; HT.log = lambda s: None   # 試験の行で本番の記録を汚さん
for c in C["mon"]:
    if c.get("koe"): os.environ["FRIDAY_KOE"] = c["koe"]
    else: os.environ.pop("FRIDAY_KOE", None)
    t0 = time.time(); r = HT.mon(c["text"]); got = "drop" if r else "send"
    rec("送る前の門", c["name"], got == c["expect"], time.time() - t0, f"{got}（正解 {c['expect']}）{r or ''}")
os.environ.pop("FRIDAY_KOE", None)
# ---- 結果
tot = len(rows); ok = sum(r["ok"] for r in rows)
sak = sorted(r["sec"] for r in rows if r["kind"] == "先回り")
out = {"at": datetime.datetime.now(JST).isoformat(timespec="minutes"), "ok": ok, "total": tot, "fails": fails,
       "sakimawari_sec_med": sak[len(sak) // 2] if sak else None, "rows": rows}
with open(M + "/shiken.jsonl", "a") as f: f.write(json.dumps(out, ensure_ascii=False) + "\n")
print(f"{ok}/{tot} 通った・先回りの秒（真ん中）{out['sakimawari_sec_med']}")
for r in rows: print(("✅" if r["ok"] else "🔴"), r["kind"], "｜", r["name"], "｜", r["note"])
sys.exit(0 if not fails else 1)
