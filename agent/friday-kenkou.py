#!/usr/bin/env python3
"""フライデーの健康診断（Air と mini の launchd・毎時）2026-10-31
オーナー 10/31「家を出たら、が1回きりで終わらんように・仕組みが崩れんように日々維持して」。
自分の機械の部品を見て、止まっとったら自分で起こす（launchctl load / kickstart・メールアプリを開く）。
直せん物（位置が届かん＝iPhone 側）は kenkou.md に書き、朝のまとめに出す。昼間に3時間以上位置が届かん時だけ LINE で1日1回知らせる。"""
import os, re, subprocess, json, time, datetime, sqlite3, urllib.request
HOME = os.path.expanduser("~"); ME = "mini" if os.path.isdir("/Users/owner") else "air"
F = f"{HOME}/owner-kotoba/friday"; LA = f"{HOME}/Library/LaunchAgents"; UID = os.getuid(); now = time.time()
OUT = f"{F}/kenkou-{ME}.json"; LOG = f"{F}/kenkou.log"
def sh(*a, t=30):
    try: return subprocess.run(list(a), capture_output=True, text=True, timeout=t)
    except Exception as e: return subprocess.CompletedProcess(a, 1, "", str(e))
def log(s): open(LOG, "a").write(f"{datetime.datetime.now():%F %T} [{ME}] {s}\n")
JOBS = {"air": ["friday-agent", "friday-tick", "friday-plan", "friday-mail", "friday-mail-now", "mail-keep", "friday-yakusoku",
                "friday-noh", "friday-asa", "friday-watch", "friday-kenkou", "friday-denwa-ato"],
        "mini": ["friday-agent", "friday-tick", "friday-plan", "friday-mail", "friday-yakusoku", "friday-asa", "friday-watch",
                 "friday-basho", "nearby", "friday-kenkou", "friday-noh", "friday-denwa-ato", "friday-dwatch", "kinko", "friday-awase",
                 "mimi-server", "mimi-watch", "mimi-matome", "mimi-drive", "mimi-renew"]}[ME]  # 11/02 足した
listed = sh("launchctl", "list").stdout
res, fixed, need = {}, [], []
for j in JOBS:
    label = f"com.owner.{j}"; plist = f"{LA}/{label}.plist"
    if not os.path.exists(plist): res[j] = "plist無し"; continue
    if label not in listed:
        sh("launchctl", "load", plist); fixed.append(f"{j} を読み込み直した")
        res[j] = "直した"
    else: res[j] = "ok"
# 常駐の返事係：生きとる印が2分より古い→起こし直す
alive = f"{HOME}/.friday-alive"
if os.path.exists(alive) and now - os.path.getmtime(alive) > 120:
    sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.friday-agent"); fixed.append("返事係を起こし直した"); res["返事係"] = "直した"
if ME == "air":
    # メールアプリ（即時メールの目）
    if sh("pgrep", "-x", "Mail").returncode: sh("open", "-gj", "-a", "Mail"); fixed.append("メールアプリを開いた")
    beat = f"{F}/mail/now_beat"
    age = now - float(open(beat).read()) if os.path.exists(beat) else 1e9
    res["即時メール"] = f"{int(age/60)}分前"
    if age > 3 * 3600:
        sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.friday-mail-now"); fixed.append("即時メールを起こし直した")
if ME == "mini":
    # 位置（家を出た・着いた・帰った の元）
    try:
        db = sqlite3.connect(f"file:{HOME}/work/nearby/loc.db?mode=ro", uri=True)
        last = (db.execute("select max(ts) from locs where user='YOUR_USER_ID'").fetchone()[0] or 0) / 1000
    except Exception: last = 0
    age = now - last; res["位置"] = f"{int(age/60)}分前"
    if sh("curl", "-s", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:8820/").stdout in ("", "000"):
        sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.nearby"); fixed.append("位置の受け口を起こし直した")
    h = datetime.datetime.now().hour
    if age > 3 * 3600 and 9 <= h <= 22:
        need.append(f"位置が{int(age/3600)}時間届いていません（iPhone の OwnTracks と Tailscale を開いてください）")
    # LINE の見張り（一覧の写し lst.txt が5分ごとに新しくなる）。10/31 17:52〜20:53 に3時間止まっとった
    lst = f"{HOME}/work/linemini/t/lst.txt"
    lage = now - os.path.getmtime(lst) if os.path.exists(lst) else 1e9
    res["LINE の見張り"] = f"{int(lage/60)}分前"
    if lage > 20 * 60:
        # 11/09 Terminal が AppleEvent に答えんまま18時間止まっとった（見張りを起こし直しても直らん）。
        # 答えん時だけ、タブで何も動いてへん（zsh だけ）のを確かめて Terminal を開き直す
        if ME == "mini":
            t = sh("osascript", "-e", 'with timeout of 10 seconds', "-e", 'tell application "Terminal" to count windows', "-e", "end timeout", t=15)
            if t.returncode != 0 and ("-1712" in (t.stderr or "") or "timed out" in (t.stderr or "").lower() or "Timeout" in (t.stderr or "")):
                tp = sh("pgrep", "-x", "Terminal").stdout.split()
                busy = False
                for tpid in tp:
                    for lg in sh("pgrep", "-P", tpid).stdout.split():
                        for zs in sh("pgrep", "-P", lg).stdout.split():
                            if sh("pgrep", "-P", zs).stdout.strip(): busy = True
                if tp and not busy:
                    for tpid in tp: sh("kill", "-TERM", tpid)
                    time.sleep(4); sh("open", "-g", "-j", "-a", "Terminal"); time.sleep(4)
                    fixed.append("答えんかった Terminal を開き直した")
                elif busy:
                    need.append("Terminal が答えません（タブで作業が動いとるので自動では開き直していません）")
        sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.friday-watch"); fixed.append("LINE の見張りを起こし直した")
    if lage > 60 * 60 and 8 <= datetime.datetime.now().hour <= 23:
        need.append(f"LINE の見張りが{int(lage/60)}分止まっています（Mac mini の画面が別の作業で使われとるか、LINE が閉じとる可能性）")
    # 場所の判定が最後に動いた時刻
    st = f"{F}/basho/state.json"
    res["場所の判定"] = f"{int((now - json.load(open(st)).get('since', 0))/60)}分前" if os.path.exists(st) else "まだ"
    if os.path.exists(st) and now - json.load(open(st)).get("since", 0) > 3600 and age < 1800:
        sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.friday-basho"); fixed.append("場所の判定を起こし直した")
if ME == "mini":
    # 11/14 夜 フライデーの耳（オーナー「強いシステムに」）：受け口・書き起こしの詰まり・Drive の控え・アプリの期限・空き
    try:
        M = f"{F}/mimi"
        pg = sh("curl", "-s", "-m", "5", "http://100.64.0.1:8840/ping").stdout
        try: q = json.loads(pg).get("q", 0)
        except Exception: q = -1
        if q < 0:
            sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.mimi-server"); fixed.append("耳の受け口を起こし直した"); res["耳の受け口"] = "直した"
        else:
            res["耳の受け口"] = f"ok（待ち{q}本）"
            if q > 40:   # 書き起こしが詰まっとる（whisper が固まった）
                sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.mimi-server"); fixed.append(f"耳の書き起こしが{q}本詰まっとったので起こし直した")
        dl = f"{M}/drive.log"
        if os.path.exists(dl):
            dage = now - os.path.getmtime(dl); res["耳の Drive 控え"] = f"{int(dage/60)}分前"
            if dage > 3 * 3600: sh("launchctl", "kickstart", "-k", f"gui/{UID}/com.owner.mimi-drive"); fixed.append("耳の Drive 控えを起こし直した")
            tail = open(dl, errors="ignore").read()[-600:]
            if dage < 3600 and "ok" not in tail.split("\n")[-2:][0] and "ERROR" in tail: need.append("耳の記録が Google Drive に控えられていません（rclone のエラー）")
        li = f"{HOME}/work/friday-mimi-ios/last_install"
        if os.path.exists(li):
            left = float(open(li).read().strip() or 0) + 7 * 86400 - now; res["耳のアプリの期限"] = f"あと{left/86400:.1f}日"
            if left < 86400: need.append("フライデーの耳のアプリの期限が" + ("切れました" if left < 0 else "明日までです") + "（家で iPhone のロックを外して2〜3分置いてください）")
        for nm in ("server", "watch", "matome"):
            ep = f"{M}/{nm}.err"
            if os.path.exists(ep) and os.path.getsize(ep) > 0 and now - os.path.getmtime(ep) < 3700:
                res[f"耳の{nm}のエラー"] = open(ep, errors="ignore").read()[-160:].replace("\n", " ")
        st_ = os.statvfs(HOME); free = st_.f_bavail * st_.f_frsize / 1e9; res["mini の空き"] = f"{free:.0f}GB"
        if free < 8: need.append(f"Mac mini の空きが{free:.0f}GB です（耳の書き起こし・動画の作業が止まる手前）")
    except Exception as ex: res["耳の点検"] = f"点検が失敗 {repr(ex)[:80]}"
    # 11/14 夜 塞いだ穴がまた開いてないか（本人「塞いだ穴がまた広がることはない？」）＝直しの印と動きの試験。朝5時台は遅い試験も
    try:
        a = sh("/usr/bin/python3", f"{HOME}/bin/friday-ana-mihari.py", *(["--basho"] if datetime.datetime.now().hour == 5 else []), t=120)
        res["穴の見張り"] = (a.stdout.strip().splitlines() or ["?"])[0][:60]
        if a.returncode == 1:
            need.append("前に塞いだ穴がまた開いています（今夜の直し係か別の作業が書き換えた可能性）：\n　" + "\n　".join(a.stdout.strip().splitlines()[:5]))
    except Exception as ex: res["穴の見張り"] = f"失敗 {repr(ex)[:60]}"
    # 11/14 夜 毎朝 5:20 の試験（mimi-shiken.py）の点が落ちたら知らせる（本人「今後どんどん精度落ちていきそう」）
    try:
        L = [json.loads(l) for l in open(f"{F}/mimi/shiken.jsonl") if l.strip()][-2:]
        if L:
            cur = L[-1]; res["耳の試験"] = f"{cur['ok']}/{cur['total']}（{cur['at'][5:16]}）"
            if now - datetime.datetime.fromisoformat(cur["at"]).timestamp() > 30 * 3600: need.append("耳の毎朝の試験が30時間回っていません")
            elif cur["fails"]: need.append(f"耳の試験が {cur['ok']}/{cur['total']} に落ちました：\n　" + "\n　".join(cur["fails"][:4]))
            elif len(L) == 2 and cur.get("sakimawari_sec_med") and L[0].get("sakimawari_sec_med") and cur["sakimawari_sec_med"] > max(20, L[0]["sakimawari_sec_med"] * 2):
                need.append(f"耳の先回りが遅くなっています（{L[0]['sakimawari_sec_med']}秒→{cur['sakimawari_sec_med']}秒）")
    except Exception as ex: res["耳の試験"] = f"読めず {repr(ex)[:50]}"
    # 11/14 夜 太り続ける記録の掃除：runs/ の14日より古い仕事フォルダ・agent.log が5MBを超えたら古い半分を .old へ
    try:
        import shutil
        rd = f"{F}/runs"; n_del = 0
        for nm in os.listdir(rd) if os.path.isdir(rd) else []:
            pth = os.path.join(rd, nm)
            if re.match(r"^20\d{6}_\d{4}", nm) and os.path.isdir(pth) and now - os.path.getmtime(pth) > 14 * 86400: shutil.rmtree(pth, ignore_errors=True); n_del += 1
        if n_del: fixed.append(f"古い仕事の記録を{n_del}個消した")
        al = f"{F}/agent.log"
        if os.path.exists(al) and os.path.getsize(al) > 5_000_000:
            L = open(al, encoding="utf-8", errors="ignore").read().splitlines(True); h = len(L) // 2
            open(al + ".old", "w", encoding="utf-8").write("".join(L[:h])); open(al, "w", encoding="utf-8").write("".join(L[h:])); fixed.append("agent.log を半分に")
    except Exception as ex: res["掃除"] = f"失敗 {repr(ex)[:60]}"
json.dump({"at": datetime.datetime.now().isoformat(timespec="minutes"), "me": ME, "res": res, "fixed": fixed, "need": need}, open(OUT, "w"), ensure_ascii=False, indent=1)
if fixed: log("直した：" + "・".join(fixed))
if need:
    log("本人に要る：" + "・".join(need))
    key = json.load(open(f"{HOME}/.config/line/friday.json"))["agent_key"]
    r = urllib.request.Request(f"https://friday-line.example.workers.dev/once?job=kenkou:{datetime.date.today()}",
                               headers={"x-agent-key": key, "x-agent": ME, "User-Agent": "friday-agent/1"})
    try:
        if json.load(urllib.request.urlopen(r, timeout=15)).get("run") is True:
            sh(f"{HOME}/bin/friday-send", "🔧 オーナー様、フライデーの点検でございます。\n" + "\n".join("・" + x for x in need))
    except Exception: pass
# 両方の結果を1枚に（朝のまとめが読む）
if ME == "air":
    other = sh(f"{HOME}/bin/mini", "run", "cat ~/owner-kotoba/friday/kenkou-mini.json", t=40).stdout
    parts = [open(OUT).read()] + ([other] if other.strip().startswith("{") else ["（mini に届かん）"])
    open(f"{F}/kenkou.md", "w").write(f"# フライデーの健康診断（{datetime.datetime.now():%m/%d %H:%M}）\n" + "\n".join(f"```\n{p}\n```" for p in parts))
