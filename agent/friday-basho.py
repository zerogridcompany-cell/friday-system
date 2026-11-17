#!/usr/bin/env python3
"""フライデー：場所で動く知らせ（Mac mini の launchd・3分ごと・OwnTracks の loc.db を読む）2026-10-31
オーナー 10/31「AGI に近づける」②＝家を出たら忘れ物と次の予定・どこかに着いたらそこで要る事・帰ったら明日の段取り。
家＝夜中（0〜6時）に一番長くおる200mの升（足りん時は7日で一番長くおる升）。住所の値は使わん。
判定は sonnet（要らん時は送らん）。場所の知らせは1日3通まで。位置は外に出さん（LINE の本文に住所を書くのは本人あて1通だけ）。"""
import sqlite3, os, json, math, time, datetime, subprocess, re, collections, sys
HOME = os.path.expanduser("~"); F = f"{HOME}/owner-kotoba/friday"; B = f"{F}/basho"; os.makedirs(B, exist_ok=True)
DB = f"{HOME}/work/nearby/loc.db"; USER = "YOUR_OWNTRACKS_USER"; ST = f"{B}/state.json"; LOG = f"{F}/basho.log"
DRY = "--dry" in sys.argv
def log(s): open(LOG, "a").write(f"{datetime.datetime.now():%F %T} {s}\n")
def dist(a, b):
    return 6371000 * math.hypot(math.radians(a[0] - b[0]), math.radians(a[1] - b[1]) * math.cos(math.radians(a[0])))
db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); now = time.time()
pts = db.execute("select ts/1000.0, lat, lng, acc from locs where user=? and ts>? and acc<200 order by ts", (USER, (now - 7 * 86400) * 1000)).fetchall()
if not pts or now - pts[-1][0] > 1800: sys.exit(0)            # 位置が30分より古い＝何もせん
cell = lambda p: (round(p[1] / 0.002), round(p[2] / 0.002))
# 夜を過ごした日の数が一番多い升（2晩以上）。旅行の1晩で家が動かんように。足りん時は7日で一番長くおる升
nights = collections.defaultdict(set)
for p in pts:
    t = datetime.datetime.fromtimestamp(p[0])
    if t.hour < 6: nights[cell(p)].add(t.date())
best = max(nights.items(), key=lambda kv: len(kv[1]), default=(None, set()))
c = best[0] if len(best[1]) >= 2 else collections.Counter(cell(p) for p in pts).most_common(1)[0][0]
# 家の真ん中＝その升の中の精度15m以内の点だけで平均（GPS の誤差は平均11m）＝ほぼ建物の位置 10/31「もう少しピンポイントに」
inside = [p for p in pts if cell(p) == c and p[3] <= 15] or [p for p in pts if cell(p) == c]
home = (sum(p[1] for p in inside) / len(inside), sum(p[2] for p in inside) / len(inside))
st = json.load(open(ST)) if os.path.exists(ST) else {"where": "home", "since": now, "sent": {}}
last2 = pts[-2:]; cur = (pts[-1][1], pts[-1][2])
away = all(dist((p[1], p[2]), home) > 150 for p in last2)
athome = all(dist((p[1], p[2]), home) < 60 for p in last2)
# 止まっとるか（直近10分の点が全部100m以内）
recent = [p for p in pts if p[0] > now - 600]
still = len(recent) >= 3 and max(dist((p[1], p[2]), cur) for p in recent) < 100
ev = None
if st["where"] == "home" and away: ev, st["where"] = "leave", "out"; st["out_since"] = now; st["stop"] = None
elif st["where"] == "out" and athome:
    ev = "home" if now - st.get("out_since", now) > 2 * 3600 else None; st["where"] = "home"
elif st["where"] == "out" and still and not athome:
    s = st.get("stop")
    if not s or dist(cur, tuple(s)) > 300: st["stop"] = list(cur); ev = "arrive"
st["since"] = now
if DRY: print("home_dist_m", round(dist(cur, home)), "state", st["where"], "ev", ev); sys.exit(0)
json.dump(st, open(ST, "w"))
if not ev: sys.exit(0)
day = datetime.date.today().isoformat(); sent = st.setdefault("sent", {}); n = sent.get(day, 0)
if n >= 3 or (ev == "home" and datetime.datetime.now().hour < 17): log(f"{ev} 送らん（上限か時間）"); sys.exit(0)
try: addr = json.loads(subprocess.run([f"{HOME}/.local/bin/nearby", "where", "--json"], capture_output=True, text=True, timeout=30).stdout).get("address", "")
except Exception: addr = ""
yotei = subprocess.run([f"{HOME}/bin/yomu-yotei", "2"], capture_output=True, text=True, timeout=60).stdout[:5000]
WHAT = {"leave": "今、家を出た", "arrive": f"今ここに着いて止まっとる：{addr}", "home": "今、家に帰ってきた"}[ev]
prompt = f"""あなたはフライデー。〈姓〉オーナーの専属アシスタント。今 {datetime.datetime.now():%Y-%m-%d(%a) %H:%M}（日本時間・{__import__('genchi').genchi_now()[1]}では {__import__('genchi').genchi_now()[0]:%H:%M}）。{__import__('genchi').RULE}
OwnTracks の位置から分かった事：**{WHAT}**。
🧠 先に ~/owner-kotoba/friday/脳.md を読む（もう送った事は送らん）。今日の時刻の知らせ＝~/owner-kotoba/friday/plan/{datetime.date.today():%Y%m%d}.json

今日・明日の予定（Mac のカレンダー）:
{yotei}

この瞬間に LINE で言うたら助かる事だけを1通にする。無ければ送らん（送らんのが普通）。
- 家を出た → その日の予定に要る持ち物（チケット・充電器・書類・上着）の確認と、次の予定の時刻。予定が無い・ただの散歩らしい時は送らん
- 着いた → そこが予定の場所なら、そこで要る事（予約の名前・チェックイン・駐車場・次の時刻）。予定と関係ない所（コンビニ・ジム・家の近所）なら送らん
- 帰ってきた → 明日の朝いちの予定と出る時刻・前の晩にやっとく事。明日が空なら送らん
- 標準語の丁寧な執事の口調（です・ます。落ち着いて礼儀正しく、呼びかけは「オーナー様」。関西弁は使わない＝10/31 本人）で2〜4行。住所の番地・パスワード・番号は書かん。

最後の1行だけ出す：`FRIDAY {{"send": true か false, "text": "本文"}}`"""
r = subprocess.run([os.environ.get("CLAUDE_BIN", "claude"), "-p", "--model", "opus", "--settings", '{"disableAllHooks":true}',
                    "--allowedTools", "Read,Bash(~/bin/yomu-yotei:*)"], input=prompt, capture_output=True, text=True, timeout=240, cwd=HOME)
m = re.findall(r"FRIDAY (\{.*\})", r.stdout)
j = json.loads(m[-1]) if m else {}
log(f"{ev} {json.dumps(j, ensure_ascii=False)[:200]}")
if not j.get("send") or not j.get("text"): sys.exit(0)
out = subprocess.run([f"{HOME}/bin/friday-send", j["text"]], capture_output=True, text=True).stdout.strip()
if out == "sent": sent[day] = n + 1; json.dump(st, open(ST, "w"))
with open(f"{F}/sent.jsonl", "a") as f:
    f.write(json.dumps({"day": day, "at": f"{datetime.datetime.now():%FT%H:%M}", "text": j["text"], "result": out, "kind": "basho-" + ev, "by": "mini"}, ensure_ascii=False) + "\n")
