#!/usr/bin/env python3
"""フライデー：前の晩に「明日の時刻表」を言われる前に送る（2026-11-12 C 係・manabi.md C 節「前の晩19時ごろに明日の時刻表」）
launchd com.owner.friday-ashita が 19:00 と 20:00（日本時間）に起こす。本人の今いる土地の 19 時台の回だけ動く
（日本＝19:00 の回・中国＝日本の 20:00 の回）。/once で Air・mini 合わせて1日1回。
中身＝カレンダー（~/bin/yomu-yotei 2）の明日の予定＋便の台帳（friday-bin-mihari.py の BINS：便・端末・受付と搭乗口の締め切り・席・着く）
＋明日の予約（plan/<日付>.json の起こす・出る知らせ）。時刻は全部本人の今いる土地の時間（日本に着く便の着だけ日本時間）。
送る＝friday-send --isogi（枠0なら todokanai.jsonl に入って次の返事の頭で伝わる）。friday_shougou で出発時刻を照らす。
使い方: friday-ashita.py [--test]（--test＝送らず下書きを出すだけ）  [--day YYYY-MM-DD]（明日の代わりにその日）"""
import os, re, sys, json, datetime, subprocess, urllib.request
HOME = os.path.expanduser("~"); F = f"{HOME}/owner-kotoba/friday"; LOG = f"{F}/ashita.log"
TEST = "--test" in sys.argv
SKIP = {"2026-11-12"}   # 11/12 C：今夜の分は送らん（係の指示）。下書きだけ報告へ
def log(s):
    with open(LOG, "a") as f: f.write(f"{datetime.datetime.now():%F %T} {s}\n")

def kaigai():
    try:
        l = [x for x in open(f"{F}/basho/ima.md").read().splitlines() if x.startswith("- 場所：")][0]
        return ("中国" in l or "China" in l) and "日本" not in l
    except Exception: return False
OFF = -1 if kaigai() else 0   # 日本時間→今いる土地（中国＝−1時間）
now = datetime.datetime.now()   # この機械は日本時間
loc_now = now + datetime.timedelta(hours=OFF)
if not TEST:
    if loc_now.hour != 19: sys.exit(0)
    if loc_now.strftime("%F") in SKIP: log("skip（SKIP の日）"); sys.exit(0)
day = datetime.datetime.strptime(sys.argv[sys.argv.index("--day") + 1], "%Y-%m-%d").date() if "--day" in sys.argv else (loc_now + datetime.timedelta(days=1)).date()
def lt(hhmm_jst):   # 日本時間 "HH:MM" → 今いる土地 "H:MM"
    t = datetime.datetime.strptime(hhmm_jst, "%H:%M") + datetime.timedelta(hours=OFF)
    return f"{t.hour}:{t.minute:02d}"

rows = []   # (並べる鍵 "HH:MM", 行)
# 1) 便の台帳
try:
    src = open(f"{HOME}/bin/friday-bin-mihari.py", encoding="utf-8").read()
    blk = src[src.index("BINS = ["):src.index("\nnow = ")]
    ns = {"CN": datetime.timezone(datetime.timedelta(hours=8)), "JP": datetime.timezone(datetime.timedelta(hours=9))}
    exec(blk, ns)
    for b in ns["BINS"]:
        if b["date"] != day.isoformat(): continue
        dep = datetime.datetime.strptime(f"{b['date']} {b['dep']}", "%Y-%m-%d %H:%M")
        m = lambda n: (dep - datetime.timedelta(minutes=n)).strftime("%-H:%M")
        if b.get("close"):
            rows.append((b["close"], f"・{(b.get('board') or '?').lstrip('0')}ごろ 搭乗開始{'（目安）' if b.get('board_meyasu') else ''}／{b['close'].lstrip('0')} 搭乗口が閉まります"))
        if b["id"].startswith("CA") and b["tz"].utcoffset(None) == datetime.timedelta(hours=8):
            rows.append(((dep - datetime.timedelta(minutes=50)).strftime("%H:%M"), f"・{m(50)} 受付の締め切り（国航の国際線・出発50分前）"))
        rows.append((b["dep"], f"・{b['dep'].lstrip('0')} {b['name']} 発{('（お席' + b['seat'] + '）') if b.get('seat') else ''}{'・機材 ' + b['type'] if b.get('type') else ''}"))
        rows.append(("23:58", f"・@ARR@ {b['to']}着{'（日本時間）' if b['arr_tz'] != b['tz'] else ''}"))
except Exception as e: log(f"便の台帳が読めん {e}")
# 2) カレンダー（日本時間で出る）
try:
    out = subprocess.run([f"{HOME}/bin/yomu-yotei", "3"], capture_output=True, text=True, timeout=60).stdout
    pre = day.strftime("%m/%d(")
    for l in out.splitlines():
        if not l.startswith(pre): continue
        m = re.match(r"^\d+/\d+\(\w+\) (終日|(\d+:\d+)-(\d+:\d+)) (.*?)(?: ＠(.*?))? \[", l)
        if not m: continue
        title = m.group(4).strip(); where = (m.group(5) or "").strip()
        if m.group(1) == "終日": rows.append(("00:00", f"・終日 {title}")); continue
        a, z = m.group(2), m.group(3)
        if re.match(r"Flight to|(?:CA|MU|NH|JL)\s?\d+\s*$", title):   # 便はカレンダーの着時刻だけ使う（日本に着く便は日本時間）
            rows[:] = [(k, v.replace("@ARR@", z.lstrip("0"))) if k == "23:58" else (k, v) for k, v in rows]
            continue
        rows.append((lt(a).zfill(5), f"・{lt(a)} {title}" + (f"（{where}）" if where and where not in title else "")))
except Exception as e: log(f"カレンダーが読めん {e}")
# 3) 明日の予約（起こす・出る）
try:
    pl = json.load(open(f"{F}/plan/{day:%Y%m%d}.json"))
    for it in pl.get("items", []):
        if it.get("status"): continue
        t = it["text"]
        if re.search(r"おはよう|お目覚め|起床", t): rows.append((lt(it["at"]).zfill(5), f"・{lt(it['at'])} お目覚め（iPhone のアラームもお願いします）＋LINE でお声がけ"))
except Exception: pass
if not rows: log(f"{day} 予定なし＝送らん"); print("予定なし"); sys.exit(0)
rows.sort(key=lambda r: r[0].zfill(5))
seen, lines = set(), []
for _, v in rows:
    v = v.replace("@ARR@ ", "")   # カレンダーに便が無い時は時刻なしで
    if v not in seen: seen.add(v); lines.append(v)
WD = "月火水木金土日"[day.weekday()]
text = (f"オーナー様、明日{day.month}/{day.day}（{WD}）の時刻表でございます（{'中国時間' if OFF else '日本時間'}）。\n" + "\n".join(lines[:9])
        + "\n変更がございましたらお知らせください。")
try:
    sys.path.insert(0, f"{HOME}/bin"); from friday_shougou import shougou, kiroku
    sg = shougou(text, day); kiroku("ashita", f"ashita_{day:%Y%m%d}", sg)
    if sg["status"] == "hold": log("照合で止めた " + " / ".join(sg["notes"])); print("⛔ 照合で止めた", sg["notes"]); sys.exit(2)
    text = sg["text"]
    if TEST: print("［照合］", sg["status"], " / ".join(sg["notes"]))
except SystemExit: raise
except Exception as e: log(f"照合できん {e}")
if TEST: print(text); sys.exit(0)
# Air・mini 合わせて1日1回
key = json.load(open(f"{HOME}/.config/line/friday.json"))["agent_key"]
try:
    q = urllib.request.Request(f"https://friday-line.example.workers.dev/once?job=ashita:{day:%Y%m%d}",
        headers={"x-agent-key": key, "x-agent": "mini", "User-Agent": "friday-agent/1"})
    if json.load(urllib.request.urlopen(q, timeout=15)).get("run") is not True: sys.exit(0)
except SystemExit: raise
except Exception as e: log(f"/once 読めん {e}"); sys.exit(1)
r = subprocess.run([f"{HOME}/bin/friday-send", text, "--isogi"], capture_output=True, text=True, timeout=60)
log(f"送った {day} → {r.stdout.strip()[:100]}")
with open(f"{F}/sent.jsonl", "a") as f:
    f.write(json.dumps({"day": now.strftime("%F"), "at": now.strftime("%FT%H:%M"), "text": text, "result": r.stdout.strip(), "kind": "ashita", "by": "mini"}, ensure_ascii=False) + "\n")
