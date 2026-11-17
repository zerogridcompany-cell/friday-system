#!/usr/bin/env python3
"""friday-yoyaku と friday-tick を仮の置き場で通しで動かす（LINE も電話も Air への写しも撃たん）2026-11-11
使い方: friday_shougou_kansou.py  → 11/11 6:00 の「七時」の文で、予約の時と送る時の両方で直るかを見る"""
import os, sys, json, runpy, tempfile, subprocess, datetime, builtins, urllib.request
T = tempfile.mkdtemp(); os.makedirs(f"{T}/plan")
real_run, real_open, real_exp = subprocess.run, builtins.open, os.path.expanduser
sent = []
def fake_run(a, *k, **kw):
    if a and a[0] == "zsh" or a[0].endswith("friday-send"):
        sent.append(a[1] if a[0].endswith("friday-send") else a); return subprocess.CompletedProcess(a, 0, "sent", "")
    if a and os.path.basename(a[0]) in ("scp", "ssh") or (len(a) > 1 and str(a[1]).endswith("friday-denwa.py")):
        return subprocess.CompletedProcess(a, 0, "", "")
    return real_run(a, *k, **kw)
def fake_exp(p):
    if p == "~/owner-kotoba/friday/plan": return f"{T}/plan"
    if p == "~/owner-kotoba/friday": return T
    if p == "~/owner-kotoba/friday/shougou.log": return f"{T}/shougou.log"
    return real_exp(p)
subprocess.run = fake_run; os.path.expanduser = fake_exp
urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no net"))
T600 = "おはようございます、オーナー様。六時でございます。七時にホテルをご出発、九時半の便で目的地へ向かわれます。お支度をお願いいたします。"
bad = 0
# ① 予約の時
sys.argv = ["friday-yoyaku", "2026-11-11 23:59", T600, "--id", "kansou_yoyaku"]
try: runpy.run_path(real_exp("~/bin/friday-yoyaku"), run_name="__main__")
except SystemExit: pass
it = [i for i in json.load(open(f"{T}/plan/20261111.json"))["items"] if i["id"] == "kansou_yoyaku"][0]
ok = "七時半にホテルをご出発" in it["text"]; bad += not ok
print("✅" if ok else "❌", "予約の時に直った：", it["text"][:50])
# ② 送る時（予約を通らずに plan に直に入った文）
now = datetime.datetime.now(); P = f"{T}/plan/{now:%Y%m%d}.json"
pl = json.load(open(P)) if os.path.exists(P) else {"items": []}
pl["items"].append({"id": "kansou_tick", "at": (now - datetime.timedelta(minutes=2)).strftime("%H:%M"), "text": T600,
                    "links": [], "eta": None, "status": None, "src": "yoyaku", "call": False, "retry": 0})
json.dump(pl, open(P, "w"), ensure_ascii=False)
import friday_shougou  # noqa（~/bin を path に）
ns = {}
src = open(real_exp("~/bin/friday-tick.py")).read().replace("def once(job):", "def once(job): return True\ndef _once(job):")
src = src.replace('json.load(open(os.path.expanduser("~/.config/line/friday.json")))["agent_key"]', '"x"')
exec(compile(src, "friday-tick.py", "exec"), {"__name__": "__main__"})
it = [i for i in json.load(open(P))["items"] if i["id"] == "kansou_tick"][0]
ok = it["status"] == "sent" and sent and "七時半にホテルをご出発" in sent[-1] and "七時に" not in sent[-1]; bad += not ok
print("✅" if ok else "❌", "送る時に直った：", it["status"], "｜", it.get("shougou"), "｜送った文：", (sent[-1] if sent else "なし")[:50])
real_run(["rm", "-rf", T]); print("全部通った" if not bad else f"🔴 {bad} 件ちがう"); sys.exit(bad)
