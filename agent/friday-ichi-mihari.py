#!/usr/bin/env python3
"""フライデー：位置（OwnTracks）が30分以上届かん時に LINE で1回知らせる（mini の launchd・5分ごと）2026-11-08
きっかけ＝11/08 8:48〜13:02 の4時間、iPhone の OwnTracks が止まって位置が来ず、「ある市に入ったら駐車場の電話」が目的地に着いた後になった。
オーナー 11/08「改善できる部分を修正して」→ 13:18 に約束した「位置が30分以上届かない時は LINE でお知らせ」。
- 8:00〜23:00 だけ・1つの途切れにつき1回・1日2通まで
- 飛行機の予定（Flight／便／CA・MU 等）の最中とその後30分は送らん（機内は届かんのが普通）
- 送る文に「場所で動く知らせが遅れる」と添える（位置で動く知らせは、作る時に時刻の控えも必ず付ける＝master 07）"""
import sqlite3, os, json, time, datetime, subprocess, re, sys
HOME = os.path.expanduser("~"); F = f"{HOME}/owner-kotoba/friday"; ST = f"{F}/ichi_mihari.json"; LOG = f"{F}/ichi_mihari.log"
DB = f"{HOME}/work/nearby/loc.db"; USER = "YOUR_OWNTRACKS_USER"; GAP = 30 * 60
TEST = "--test" in sys.argv; now = datetime.datetime.now()
def log(s): open(LOG, "a").write(f"{now:%F %T} {s}\n")
if not TEST and not (8 <= now.hour < 23): sys.exit(0)
last = sqlite3.connect(f"file:{DB}?mode=ro", uri=True).execute("select max(ts) from locs where user=?", (USER,)).fetchone()[0] / 1000
gap = time.time() - last; lastdt = datetime.datetime.fromtimestamp(last)
st = json.load(open(ST)) if os.path.exists(ST) else {}
day = now.strftime("%F"); n = st.get("count", {}).get(day, 0)
if TEST: print(f"最後の位置 {lastdt:%m/%d %H:%M}・{int(gap // 60)}分前・今日送った {n}")
if gap < GAP: sys.exit(0)
# 11/08 予備の道＝Apple の「探す」で大まかな場所（市・区）を読む。途切れとる間は10分ごとに控えを書く（他の知らせが使える）
FM = f"{F}/findmy_latest.json"; fm = []
try: fmold = json.load(open(FM))
except Exception: fmold = {}
if TEST or time.time() - fmold.get("ts", 0) > 600:
    try:
        fm = json.loads(subprocess.run([f"{HOME}/bin/findmy-ichi", "--json"], capture_output=True, text=True, timeout=150).stdout or "[]")
        json.dump({"ts": time.time(), "at": f"{now:%F %T}", "owntracks_last": f"{lastdt:%F %T}", "devices": fm}, open(FM, "w"), ensure_ascii=False, indent=1)
        log(f"探す {fm}")
    except Exception as e: log(f"探す 読めん {e}")
else: fm = fmold.get("devices", [])
if st.get("alerted_for") == int(last) or n >= 2: sys.exit(0)
# 飛行機の最中・着いて30分は送らん
try: yotei = subprocess.run([f"{HOME}/bin/yomu-yotei", "1"], capture_output=True, text=True, timeout=60).stdout
except Exception: yotei = ""
for l in yotei.splitlines():
    m = re.match(r"(\d\d)/(\d\d)\(\w+\) (\d\d):(\d\d)-(\d\d):(\d\d) (.*)", l)
    if not m or not re.search(r"Flight|フライト|便|\b(CA|MU|NH|JL|CZ|HO|FM) ?\d{2,4}", m[7]): continue
    s = now.replace(month=int(m[1]), day=int(m[2]), hour=int(m[3]), minute=int(m[4]), second=0)
    e = now.replace(month=int(m[1]), day=int(m[2]), hour=int(m[5]), minute=int(m[6]), second=0)
    if s - datetime.timedelta(minutes=30) <= now <= e + datetime.timedelta(minutes=30):
        if TEST: print("飛行機の最中＝送らん", m[7][:40])
        sys.exit(0)
text = (f"オーナー様、スマホからの位置が {__import__('genchi').to_genchi(lastdt):%H:%M} から届いておりません（OwnTracks が止まっているようです）。\n"
        "お手すきの時に OwnTracks を一度開いていただくと、また届くようになります。\n"
        "位置が届かない間は、場所で動くお知らせ（駐車場など）が遅れることがございます。")
ph = [d for d in fm if "iPhone" in d.get("device", "") and d.get("place")]
away = [d for d in ph if d["place"] != "自宅"] or ph
if away:
    text += "\n代わりに「探す」で見ると、iPhone は " + "／".join(f"{d['place']}（{d['when']}）" for d in away[:2]) + " でございます。"
if TEST: print("送る文:\n" + text); sys.exit(0)
r = subprocess.run([f"{HOME}/bin/friday-send", text], capture_output=True, text=True).stdout.strip()
st["alerted_for"] = int(last); st.setdefault("count", {})[day] = n + 1; json.dump(st, open(ST, "w"))
log(f"{int(gap // 60)}分届かず（最後 {lastdt:%H:%M}）→ {r}")
with open(f"{F}/sent.jsonl", "a") as f:
    f.write(json.dumps({"day": day, "at": f"{now:%FT%H:%M}", "text": text, "result": r, "kind": "ichi-mihari", "by": "mini"}, ensure_ascii=False) + "\n")
