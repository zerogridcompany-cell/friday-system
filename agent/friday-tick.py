#!/usr/bin/env python3
"""フライデー：plan/<日付>.json の時刻が来た知らせを LINE で送る（5分ごと・Air と mini 両方・/once で1通1回）2026-10-31
出発の知らせ（eta 付き）は、送る直前に今の場所から時間を測り直して1行足す（位置が30分より古ければ足さん）。"""
import json, os, re, subprocess, datetime, urllib.request
F = os.path.expanduser("~/owner-kotoba/friday"); now = datetime.datetime.now()
DAY = now.strftime("%Y%m%d"); P = f"{F}/plan/{DAY}.json"
plan = json.load(open(P)) if os.path.exists(P) else {"items": []}; ME = "mini" if os.path.isdir("/Users/owner") else "air"
# 10/31 決まった電話（毎朝のモーニングコール・週1のミーティング10分前）をその日の plan に足す＝denwa_teiki.json
try:
    T = json.load(open(f"{F}/denwa_teiki.json")); ids = {i["id"] for i in plan["items"]}; added = False
    for d in T.get("daily", []) + [w for w in T.get("weekly", []) if w.get("dow") == now.weekday()]:
        iid = f"{d['id']}_{DAY}"
        if iid in ids or now.strftime("%Y-%m-%d") in d.get("skip", []): continue
        plan["items"].append({"id": iid, "at": d["at"], "text": d["text"], "links": [], "eta": None, "status": None,
                              "src": "teiki", "call": d.get("call", False), "retry": d.get("retry", 0)}); added = True
    if added:   # 11/14 夜 鍵つきで書く（friday_planio）＝他の係が同時に足した知らせを消さん
        import sys; sys.path.insert(0, os.path.expanduser("~/bin")); import friday_planio as PIO
        plan = PIO.awasete_kaku(P, plan, [i["id"] for i in plan["items"] if i.get("src") == "teiki"])
    MAXCALL = T.get("max_calls_per_day", 6)
except Exception: MAXCALL = 6
DEN = os.path.expanduser("~/friday-denwa/friday-denwa.py")
def denwa(text):
    """電話をかけて、出たかを返す（75秒待って確かめる）。かけられんかったら None"""
    try:
        r = subprocess.run(["python3", DEN, "call", text], capture_output=True, text=True, timeout=60)
        cid = json.loads(r.stdout.strip().splitlines()[-1]).get("conversation_id")
    except Exception: return None
    if not cid: return None
    # 11/05 19:09 83秒話したのに75秒の時点で「出てない」と判定→19:11にかけ直した（オーナー「止めて」）
    # 通話が終わる（status=done/failed）まで待ってから判定する。最大6分
    import time; time.sleep(45); c = {}
    for _ in range(21):
        try: c = json.loads(subprocess.run(["python3", DEN, "check", cid], capture_output=True, text=True, timeout=60).stdout)
        except Exception: c = {}
        if c.get("answered"): return True
        if c.get("status") in ("done", "failed"): break
        time.sleep(15)
    return bool(c.get("answered"))
calls_today = sum(1 for l in (open(f"{F}/sent.jsonl").read().splitlines() if os.path.exists(f"{F}/sent.jsonl") else [])
                  if f'"day": "{now:%F}"' in l and '"kind": "call' in l)
key = json.load(open(os.path.expanduser("~/.config/line/friday.json")))["agent_key"]
def once(job):
    r = urllib.request.Request(f"https://friday-line.example.workers.dev/once?job={job}",
        headers={"x-agent-key": key, "x-agent": ME, "User-Agent": "friday-agent/1"})
    try: return json.load(urllib.request.urlopen(r, timeout=15)).get("run") is True
    except Exception: return False
def sh(cmd):
    a = ["zsh", "-lc", cmd] if ME == "mini" else [os.path.expanduser("~/bin/mini"), "run", cmd]
    try: return subprocess.run(a, capture_output=True, text=True, timeout=60).stdout
    except Exception: return ""
def fresh_eta(e):
    w = sh("nearby where")
    m = re.search(r"更新\s*[:：]\s*(\d+)(秒|分)前", w)
    if not m or (m.group(2) == "分" and int(m.group(1)) > 30): return ""
    out = sh(f"nearby eta '{e['dest']}' --by {e['by']}")
    car = re.search(r"車：(\d+)分.*?\n\s*→ .*?(\d+:\d+) までに出る", out, re.S)
    tr = re.search(r"電車：ざっくり (\d+)分.*?→ .*?(\d+:\d+) までに出る", out, re.S)
    s = [f"車{car.group(1)}分→{car.group(2)}まで" if car else "", f"電車約{tr.group(1)}分→{tr.group(2)}まで" if tr else ""]
    s = "・".join(x for x in s if x)
    return f"\n📍今おる所から：{s}" if s else ""
def kaigai():
    try:
        l = [x for x in open(os.path.expanduser("~/owner-kotoba/friday/basho/ima.md")).read().splitlines() if x.startswith("- 場所：")][0]
        return ("中国" in l or "China" in l) and "日本" not in l
    except Exception: return False
changed = False
for it in plan["items"]:
    if it.get("status"): continue
    at = datetime.datetime.strptime(DAY + it["at"], "%Y%m%d%H:%M")
    if now < at: continue
    if now - at > datetime.timedelta(minutes=30): it["status"] = "late"; changed = True; continue
    # 11/11 6:00「七時にホテルをご出発」（正＝7:30）を送った＝『◯時ご出発』『◯時発』をカレンダーと枝06に照らし、違えば直してから送る
    try:
        import sys; sys.path.insert(0, os.path.expanduser("~/bin")); from friday_shougou import shougou, kiroku
        sg = shougou(it["text"], now.date()); kiroku("tick", it["id"], sg)
        if sg["status"] == "hold": it["status"] = "hold-shougou"; it["note"] = " / ".join(sg["notes"]); changed = True; continue
        if sg["status"] == "fixed": it["text_moto"] = it["text"]; it["text"] = sg["text"]; it["shougou"] = " / ".join(sg["notes"]); changed = True
    except Exception: pass
    if not once(f"tick:{DAY}:{it['id']}"): it["status"] = "other"; changed = True; continue
    text = it["text"] + (fresh_eta(it["eta"]) if it.get("eta") else "")
    if it.get("call") and kaigai():   # 11/11 海外では日本の回線に電話が届かん（11/10 本人）＝電話せず LINE だけ
        it["call"] = False; it["note"] = "海外のため LINE に切替"; changed = True
    if it.get("call") and calls_today < MAXCALL:
        ok = denwa(text); calls_today += 1
        with open(f"{F}/sent.jsonl", "a") as f:
            f.write(json.dumps({"day": now.strftime("%F"), "at": now.strftime("%FT%H:%M"), "text": text, "result": {True: "answered", False: "noanswer", None: "error"}[ok], "kind": "call", "by": ME}, ensure_ascii=False) + "\n")
        if ok: it["status"] = "called"; changed = True; continue
        # 11/08 13:04 駐車場への電話が留守電→LINE も出ず。起こす電話（teiki）以外は、出んかったらすぐ LINE で中身を送る
        urgent = it.get("src") != "teiki"
        if ok is False and it.get("retry", 0) > 0:      # 出んかった＝5分後にかけ直す（モーニングコール）
            it["status"] = "noanswer"
            nxt = (now + datetime.timedelta(minutes=5)).strftime("%H:%M")
            plan["items"].append({**it, "id": it["id"] + "r", "at": nxt, "status": None, "retry": it["retry"] - 1, "lined": it.get("lined") or urgent}); changed = True
            if not urgent or it.get("lined"): continue
        elif it.get("lined"): it["status"] = "call-failed"; changed = True; continue   # もう LINE で送った＝2回送らん
        else: it["status"] = "call-failed"; changed = True
        text = "📞 お電話がつながりませんでしたので、LINE でお知らせいたします。\n" + text
    a = [os.path.expanduser("~/bin/friday-send"), text]
    for l, u in (it.get("links") or [])[:3]: a += ["--link", l, u]
    if it.get("isogi"): a.append("--isogi")   # 11/12 C：便の日の起こす・出る知らせは取っとき枠も使う（枠0なら todokanai へ＝次の返事の頭）
    r = subprocess.run(a, capture_output=True, text=True).stdout.strip()
    if it.get("status") != "noanswer": it["status"] = "sent" if r == "sent" else "error"
    changed = True
    with open(f"{F}/sent.jsonl", "a") as f:
        f.write(json.dumps({"day": now.strftime("%F"), "at": now.strftime("%FT%H:%M"), "text": text, "result": r, "kind": "plan", "by": ME}, ensure_ascii=False) + "\n")
if changed:   # 11/14 夜 電話待ちで最大6分持っとった古い写しを丸ごと書き戻さん＝今のファイルに合わせて書く
    import sys; sys.path.insert(0, os.path.expanduser("~/bin")); import friday_planio as PIO
    PIO.awasete_kaku(P, plan, [i["id"] for i in plan["items"] if i["id"].endswith("r") or i.get("src") == "teiki"])
