#!/usr/bin/env python3
"""フライデーの「共有の脳」：Claude Code と同じ物を知っとる状態にする1枚（15分ごと・Air で作って mini へ）2026-10-31
オーナー 10/31「お前と話しとる中でフライデーとも話したい・俺の言うた事を全部覚えて・今までの作業もスマホの中身も共有して・同じ会話を繰り返さんで」
出す先＝~/owner-kotoba/friday/脳.md（friday-agent・plan・watch・asa・mail が毎回読む）。値（番号・パスワード）は入れん。"""
import json, os, glob, time, datetime, subprocess, re
H = os.path.expanduser("~"); K = f"{H}/owner-kotoba"; F = f"{K}/friday"; now = time.time()
ME = "mini" if os.path.isdir("/Users/owner") else "air"
def rd(p, n=None):
    try: s = open(p, encoding="utf-8").read()
    except Exception: return ""
    return "\n".join(s.splitlines()[:n]) if n else s
AIRSSH = ["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes", "-i", f"{H}/.ssh/id_ed25519_hermes_macbook_obsidian", "owner@YOUR_TAILSCALE_IP"]
# 11/01 mini は Air が止まっとる時だけ作る（Air の返事係が10分以上動いてへん／つながらん）。資料は Air が写した air-src を読む
MINISSH = ["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes", "project-j-macmini"]
OTHER = "project-j-macmini" if ME == "air" else "air"
# 11/02 mini が主（オーナー「基盤を mini に」）。Air は mini の返事係が10分以上動いてへん／つながらん時だけ作る
if ME == "air":
    try:
        r = subprocess.run(MINISSH + ['echo $(( $(date +%s) - $(stat -f %m ~/.friday-alive) ))'], capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip().isdigit() and int(r.stdout.strip()) < 600: raise SystemExit
    except subprocess.TimeoutExpired: pass
AIRSRC = f"{F}/air-src" if ME == "mini" else None
def sp(air_path, name):   # 自分の手元にあればそれ（11/02 mini の ~/owner-kotoba は Air と同じ中身）・無ければ Air が写した控え
    return air_path if os.path.exists(air_path) or not AIRSRC else f"{AIRSRC}/{name}"
def sh(a, t=30):
    try: return subprocess.run(a, capture_output=True, text=True, timeout=t).stdout
    except Exception: return ""
out = [f"# フライデーの共有の脳（{datetime.datetime.now():%m/%d %H:%M} 時点・{ME} で作成）",
       "これはパソコンの Claude Code と同じ記憶。答える前・送る前に必ず読む。ここにある事をオーナーに聞き直さん・同じ事を2回送らん。",
       "🎩 フライデーの口調（10/31 本人）：標準語の丁寧な執事の口調（です・ます・呼びかけは「オーナー様」）。関西弁は使わない。LINE も電話も同じ。",
       "🕐 時刻（11/12 本人「今後はいる場所での時刻に依存するようにして」）：時刻は全部、オーナー様が今いる場所の時間帯で言う（位置から自動で決まる＝genchi.py・今の時刻は入力の頭の「🕐 今の時刻」の行）。「現地」「日本時間」の併記はせん。日本側の締め切りなど日本時間が要る時だけ「日本時間◯時」と添える。このマシンの時計・予約（friday-yoyaku）は日本時間なので、「◯時に起こして」は日本時間に直して予約する。"]

# 11/12 本人「永久的に学習して・言われることが時間が経つにつれてなくなっていく感じ」＝毎晩の学び（friday-manabi.sh）の帳面を一番上に入れる
_mn = rd(f"{F}/manabi.md")
if _mn.strip(): out += ["", "## 🧠 フライデーの学び（毎晩の振り返りで覚えた事＝返事の前に必ず守る・全文 ~/owner-kotoba/friday/manabi.md）", _mn[:12000]]

m = rd(sp(f"{K}/master/MASTER.md", "MASTER.md")); i = m.find("## 幹"); j = m.find("## 枝")
out += ["", m[i:j].strip() if i >= 0 else ""]

# 11/11 直し：master-add が「## 済」の下に足しとったため、11/03以降の新しい行が脳に入らんかった（旅先の買い物リスト見落とし）。
# 済の上＋ファイル全体の直近14日の行を、新しい順で入れる。
import re as _re, datetime as _dt
_t06 = rd(sp(f"{K}/master/枝/06_今やっとる事.md", "06_今やっとる事.md"))
_top = _t06.split("## 済")[0].strip()
_lim = (_dt.date.today() - _dt.timedelta(days=14)).isoformat()
_new = [l for l in _t06.splitlines() if _re.match(r"- (\d{4}-\d{2}-\d{2})", l) and l[2:12] >= _lim and l not in _top]
_new.sort(key=lambda l: l[2:12], reverse=True)
# 11/11 15:45 本人「似たようなことが起こらないようにして」：6000字で切っとって直近14日の152行中124行がまだ脳に入ってへんかった。
# 塊ごと切らず、1行ずつ200字に縮めて全部入れる（14日より前は「済より上」の物だけ）。入らん行が出たら下の点検が記録する。
_cut = lambda l: l if len(l) <= 200 else l[:198] + "…"
_body = "\n".join(_cut(l) for l in _new) + "\n" + "\n".join(_cut(l) for l in _top.splitlines())
out += ["", "## 今やっとる事（枝06・直近14日は全部・新しい順＋済より上。1行200字まで＝全文は ~/owner-kotoba/master/枝/06_今やっとる事.md を grep）", _body]

out += ["", "## 今日・明日の予定（Mac のカレンダー）", sh([f"{H}/bin/yomu-yotei", "2"]).strip()[:2500] or "（読めんかった）"]

# オーナーがパソコン（Claude Code・Codex・声）で言うた事＝直近36時間・新しい順
said = []
SRC = ("claude", "claude-shiji", "claude-sdk", "voiceos", "codex-shiji", "mini-claude-shiji", "mini-claude-sdk", "mini-codex-app", "mini-codex-shiji")
try:
    with open(f"{K}/kotoba.jsonl", "rb") as f:
        f.seek(max(0, os.path.getsize(f"{K}/kotoba.jsonl") - 3_000_000)); lines = f.read().decode("utf-8", "ignore").splitlines()[1:]
    for l in lines:
        try: x = json.loads(l)
        except Exception: continue
        if x.get("tool") not in SRC: continue
        t = datetime.datetime.fromisoformat(x["at"]).timestamp()
        if now - t > 36 * 3600: continue
        s = re.sub(r"\s+", " ", x.get("text", ""))
        if len(s) < 4 or s.startswith(("<", "#")) or "あなたは" in s[:200] or "FRIDAY" in s: continue
        said.append(f"- {datetime.datetime.fromtimestamp(t):%m/%d %H:%M} {s[:160]}")
except Exception: pass
said = list(dict.fromkeys(x[12:] and x for x in said[::-1]))
seen = set(); said = [x for x in said if not (x[16:] in seen or seen.add(x[16:]))]
out += ["", "## オーナーがパソコンで言うた事（直近36時間・新しい順）", "\n".join(said[:45]) or "（なし）"]

# 直近48時間の引き継ぎメモ（作業の今）
hs = [p for p in (glob.glob(f"{H}/HANDOFF_*.md") or glob.glob(f"{AIRSRC or H}/HANDOFF_*.md")) if now - os.path.getmtime(p) < 48 * 3600]
out += ["", "## 直近の作業の引き継ぎ（48時間）"]
for p in sorted(hs, key=os.path.getmtime, reverse=True)[:4]:
    s = [x.replace("## ", "") for x in rd(p).splitlines() if x.strip()]; out += [f"### {os.path.basename(p)}", "\n".join(s[:3] + ["…"] + s[-8:])[:900]]

out += ["", "## スマホの中身から分かったオーナー（10/31 本人確認済み）", rd(sp(f"{H}/research/phone-context-20261031/総まとめ.md", "総まとめ.md"), 26).replace("## ", "■ ")[:2200]]

# フライデーがもう送った物（Air＋mini・今日と昨日）＝同じ事を2回言わん
sent = []
for src in [f"{F}/sent.jsonl"] + ([f"{F}/sent_other.jsonl"] if os.path.exists(f"{F}/sent_other.jsonl") else []):
    for l in rd(src).splitlines():
        try: x = json.loads(l)
        except Exception: continue
        if x.get("day", "") >= (datetime.date.today() - datetime.timedelta(days=1)).isoformat():
            sent.append((x.get("at", ""), re.sub(r"\s+", " ", x.get("text", ""))[:140]))
out += ["", "## フライデーがもう送った物（昨日と今日・Air と mini 両方）", "\n".join(f"- {a} {t}" for a, t in sorted(set(sent))) or "（なし）"]

out += ["", "## 道具（ログイン不要の道を先に）",
        "- 予定＝`~/bin/yomu-yotei 3`（Mac のカレンダー）／メール＝`~/bin/yomu-mail 24`・本文＝`~/bin/yomu-mail --body <番号>`（Mac のメール）。Google のコネクタは切れることがある＝こっちが先",
        "- 今の場所＝`nearby where`（mini）／行き先までの時間＝`nearby eta <行き先> --by HH:MM`",
        "- 詳しい過去＝`~/bin/context-atsume <話題>`・`~/owner-kotoba/master/枝/`・memory・`~/HANDOFF_*.md`"]
s = "\n".join(out)
# 11/11 点検：直近14日の行が1行でも脳に入ってへんかったら記録して、末尾に足す（黙って抜けるのを止める）
_miss = [l for l in _new if l[:50] not in s]
if _miss:
    open(f"{F}/kenkou.log", "a").write(f"{datetime.datetime.now():%F %T} [{ME}] 脳の点検：直近14日の{len(_miss)}行が脳に入らんかった→末尾に足した\n")
    s += "\n\n## 入りそこねた直近の記録（点検で足した）\n" + "\n".join(_cut(l) for l in _miss)
open(f"{F}/脳.md", "w", encoding="utf-8").write(s)
subprocess.run(["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", f"{F}/脳.md", f"{OTHER}:owner-kotoba/friday/脳.md"], timeout=40)
sh(["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", f"{OTHER}:owner-kotoba/friday/sent.jsonl", f"{F}/sent_other.jsonl"], 40)
if ME == "air":
    # 11/01 Air が止まった時に mini が同じ脳を作れるよう、資料の控えを写す（mtime を保つ）
    src = [f"{K}/master/MASTER.md", f"{K}/master/枝/06_今やっとる事.md", f"{H}/research/phone-context-20261031/総まとめ.md"] + hs
    sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "project-j-macmini", "mkdir -p owner-kotoba/friday/air-src && rm -f owner-kotoba/friday/air-src/HANDOFF_*.md"], 30)
    sh(["scp", "-q", "-p", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"] + [x for x in src if os.path.exists(x)] + ["project-j-macmini:owner-kotoba/friday/air-src/"], 60)
print(len(s))
