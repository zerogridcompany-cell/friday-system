#!/usr/bin/env python3
"""フライデーの耳（11/13 オーナー「iPhone に組み込める何か・常に mini にコンテキストが送られる」）
iPhone アプリ FridayMimi が30秒ずつの声（m4a）と場所を POST /up に送る → 保存 → mlx_whisper で文字 → ~/owner-kotoba/friday/mimi/<日付>.md に1行ずつ。
待ち受けは Tailscale の 100.64.0.1:8840 だけ（0.0.0.0 にせん）。鍵＝~/.config/friday/mimi.key（x-key）。"""
import http.server, os, sys, json, time, datetime, subprocess, threading, queue, re
import urllib.parse
HOME = os.path.expanduser("~"); D = HOME + "/owner-kotoba/friday/mimi"; RAW = D + "/raw"
KEY = open(HOME + "/.config/friday/mimi.key").read().strip()
WH = HOME + "/.local/bin/mlx_whisper"; Q = queue.Queue()
JST = datetime.timezone(datetime.timedelta(hours=9))
def log(*a):
    with open(D + "/server.log", "a") as f: f.write(datetime.datetime.now(JST).strftime("%m-%d %H:%M:%S ") + " ".join(map(str, a)) + "\n")
IE = {"iPhone16,1", "mini-ie"}   # 11/14 家に置く iPhone 15 Pro（持ち歩きは iPhone19,7）
BAD = re.compile(r"^(ご視聴ありがとうございました|ありがとうございました|字幕.*|Thank you|you|音楽|拍手|笑|♪.*|[\d,、.\s]*|次回もお楽しみに|チャンネル登録.*|最後までご視聴.*)$")
sys.path.insert(0, HOME + "/bin"); import mimi_filter as FILT
ISOGI = re.compile(r"たい|ほしい|欲しい|探し|調べ|どこ|何時|なんじ|いつ|予約|頼|買[いうおっ]|呼ん|教えて|フライデー|タクシー|忘れ|困っ|どうしよ|何分|行き方|開いて|空いて|して|やって|お願い|ちゃって|確認|見て|進めて|送って|止めて|キャンセル|変更|確定|まだ|どう|？|\?")
PARTNER = re.compile(r"〈パートナー〉|〈パートナー〉|〈パートナー〉|〈パートナー〉|〈パートナー〉")
def bad(t): return bool(BAD.match(t.strip().rstrip("。.！!？? 　")))   # 11/14 夜 「ご視聴ありがとうございました。」が句点つきで通っとった   # 11/14 静かな部屋の幻聴（音楽・数字の並び）も捨てる
KIKU = {"p": None}
HB_LAST = {}
def kiku(path, t=120, keep=None):
    """聞く本体（子）に声の道を渡して結果を受け取る。子が居らん・死んだ時は起こし直す。返事が無ければ None"""
    import select
    for _ in range(2):
        p = KIKU["p"]
        try:
            if p is None or p.poll() is not None:
                p = KIKU["p"] = subprocess.Popen([HOME + "/.local/share/uv/tools/mlx-whisper/bin/python", HOME + "/bin/mimi_kiku.py"],
                                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
                if not _res(p, 180): raise RuntimeError("起きん")
            p.stdin.write(path + ("\t" + json.dumps(keep) if keep else "") + "\n"); p.stdin.flush()
            r = _res(p, t)
            if r is not None: return r
        except Exception as e: log("kiku 子の失敗", repr(e)[:80])
        try: KIKU["p"].kill()
        except Exception: pass
        KIKU["p"] = None
    return None
# 11/15 夜 声の持ち主（本人「テレビの環境下で正確に聞き取れるように」）＝声紋の子（~/bin/koe_id.py・別の箱 ~/.venvs/koe）。区間ごとの「本人らしさ」の一番高い値を返す
ACK = {}   # 11/16 v5 受け取りの音：区切りの名前 → 名前で呼ばれたか（アプリが /ack で聞いて、呼ばれとったら短く鳴らす）
KOEP = {"p": None}
def koe_hon(path, t=30):
    for _ in range(2):
        p = KOEP["p"]
        try:
            if p is None or p.poll() is not None:
                p = KOEP["p"] = subprocess.Popen([HOME + "/.venvs/koe/bin/python", HOME + "/bin/koe_id.py"],
                                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
                if not _res(p, 180): raise RuntimeError("起きん")
            p.stdin.write(path + "\n"); p.stdin.flush()
            r = _res(p, t)
            if r is not None and "kukan" in r:
                s = [k["sim"] for k in r["kukan"]]
                return round(max(s), 3) if s else None
        except Exception as e: log("koe 子の失敗", repr(e)[:80])
        try: KOEP["p"].kill()
        except Exception: pass
        KOEP["p"] = None
    return None
# 11/17 声紋の窓分け（本人「テレビ・周りの声の中でも本人の頼みを正確に」）＝1.25秒の窓ごとの本人らしさ。高い窓（0.35 以上）があって周りの声も混ざっとる区切りだけ、
# 本人の窓だけをもう1回読む（hon_text）。11/16 の 2,269本で測った：全部を窓で切ると友達との会話の文字が崩れる＝今の読みは変えん。
# 使い道は1つ＝今の読みに呼びかけが無くて本人の窓だけの読みにある時（周りの声に埋もれた「フライデー、スマホどこ?」）と、呼びかけの区切りの半分以上が周りの声の時に、本人の窓の読みを正にする（元は zen に残す）。止める時は mimi/mado_off を置く
def koe_mado(path, t=30):
    for _ in range(2):
        p = KOEP["p"]
        try:
            if p is None or p.poll() is not None: return None   # 子は koe_hon が起こす（直前に呼ばれとる）
            p.stdin.write("MADO " + path + "\n"); p.stdin.flush()
            r = _res(p, t)
            if r is not None and "mado" in r: return r["mado"]
            return None
        except Exception as e: log("mado 子の失敗", repr(e)[:80]); return None
def mado_yomi(path, rec, txt):
    if os.path.exists(D + "/mado_off") or rec.get("ie") or not str(rec.get("dev", "")).startswith("iPhone"): return txt
    m = koe_mado(path)
    if not m or not m.get("n"): return txt
    rec["mado"] = [m["nokori"], m["n"], m["max"]]
    if not m["keep"] or m["nokori"] >= 0.9 * m["n"] or (m["max"] or 0) < 0.35: return txt   # ほぼ全部本人（9割以上）なら読み直さん
    r = kiku(path, 60, m["keep"])
    if r is None or "err" in r: return txt
    ht = r.get("text", ""); rec["hon_text"] = ht
    y0, y1 = FILT.yobikake(txt), FILT.yobikake(ht)
    if y1 and (not y0 or m["nokori"] / m["n"] < 0.5):
        rec["zen"] = txt; log("mado 本人の窓の読みを正に", os.path.basename(path), "%d/%d" % (m["nokori"], m["n"])); return ht
    if y0 and not y1 and m["nokori"] / m["n"] < 0.5: rec["yobi_hoka"] = 1   # 呼びかけが本人の窓に無い（今は印だけ・動きは変えん）
    return txt
# 11/17 Mac 内蔵の聞き取り（~/bin/mimi-apple-kiku・元 mimi-apple-kiku.swift）。本人の声の区切り（hon 0.30 以上）だけ、Apple の中身＋Whisper の名前を合わせた読みを正にする（元の Whisper は wh に残す）。
# Apple の読みが Whisper の半分より短い時は替えん。止める時は mimi/apple_off を置く
APP = {"p": None}
def apple_yomi(path, t=20):
    for _ in range(2):
        p = APP["p"]
        try:
            if p is None or p.poll() is not None:
                p = APP["p"] = subprocess.Popen([HOME + "/bin/mimi-apple-kiku"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
                if not _res(p, 60): raise RuntimeError("起きん")
            p.stdin.write(path + "\n"); p.stdin.flush()
            r = _res(p, t)
            if r is not None and "text" in r: return r["text"]
            if r is not None: return None
        except Exception as e: log("apple 子の失敗", repr(e)[:80])
        try: APP["p"].kill()
        except Exception: pass
        APP["p"] = None
    return None
def apple_awase(path, rec, txt):
    if rec.get("lang") == "en": return txt   # 11/18 Mac 内蔵の聞き取りは日本語だけ＝英語の区切りは Whisper の読みのまま
    if os.path.exists(D + "/apple_off") or rec.get("ie") or not str(rec.get("dev", "")).startswith("iPhone") or (rec.get("hon") or 0) < 0.30: return txt
    ap = apple_yomi(path)
    if not ap: return txt
    rec["ap"] = ap
    n = lambda x: re.sub(r"[\s、。,.?？!！]", "", x)
    if len(n(ap)) < 0.5 * len(n(txt)) or FILT.bad(ap): return txt
    t2 = FILT.awase(ap, txt)
    if t2 != txt: rec["wh"] = txt
    return t2
def _res(p, t):
    import select
    end = time.time() + t
    while time.time() < end:
        if not select.select([p.stdout], [], [], 1.0)[0]:
            if p.poll() is not None: return None
            continue
        line = p.stdout.readline()
        if not line: return None
        if line.startswith("RES "): return json.loads(line[4:])
    return None
def worker():
    while True:
        path, meta = Q.get()
        try:
            # 11/14 夜 聞く本体（mimi_kiku.py＝声の有無の門＋声の所だけ切り出し＋版は入れっぱなし）。だめな時だけ前の道（mlx_whisper を毎回起こす）
            txt = None; r = kiku(path)
            lang = None
            if r is not None and "err" not in r:
                txt = r.get("text", ""); koe = r.get("koe"); lang = r.get("lang")   # 11/18 英語の区切りは lang="en"
            else:
                log("kiku だめ→前の道", (r or {}).get("err", "返事なし")[:80]); koe = None
                out = path + ".dir"; os.makedirs(out, exist_ok=True)
                subprocess.run([WH, path, "--model", "mlx-community/whisper-large-v3-turbo", "--language", "ja",
                                "--output-format", "json", "--output-dir", out, "--condition-on-previous-text", "False"],
                               capture_output=True, timeout=300,
                               env=dict(os.environ, PATH=HOME + "/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"))
                js = [f for f in os.listdir(out) if f.endswith(".json")]
                segs = json.load(open(os.path.join(out, js[0]))).get("segments", []) if js else []
                txt = FILT.moji(segs)
                subprocess.run(["rm", "-rf", out])
            at = meta.get("at") or datetime.datetime.now(JST).isoformat()
            t = datetime.datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(JST)
            rec = {"at": t.isoformat(timespec="seconds"), "text": txt, "lat": meta.get("lat"), "lon": meta.get("lon"),
                   "acc": meta.get("acc"), "file": os.path.basename(path), "dev": meta.get("dev") or "", "ie": meta.get("dev") in IE}
            # 11/15 v4 アプリが「ほかのアプリ（動画・音楽）が鳴っとった割合」ta と「声の処理」vp を送る＝動画の音の区切りに印
            if meta.get("ta") is not None: rec["douga"] = round(meta["ta"], 2); rec["vp"] = meta.get("vp")
            if lang: rec["lang"] = lang
            if txt:
                try: rec["hon"] = koe_hon(path)   # 11/15 夜 声紋の本人らしさ（0.30 以上＝本人・テレビは最大 0.26）
                except Exception: pass
                try:
                    t3 = apple_awase(path, rec, txt)
                    if t3 and t3 != txt: txt = rec["text"] = t3
                except Exception as e: log("apple だめ", repr(e)[:80])
                try:
                    t2 = mado_yomi(path, rec, txt)
                    if t2 and t2 != txt: txt = rec["text"] = t2
                except Exception as e: log("mado だめ", repr(e)[:80])
            with open(D + "/mimi.jsonl", "a") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            try:
                ACK[os.path.basename(path)] = 1 if (txt and not rec["ie"] and FILT.yobikake(txt)) else 0   # 11/16 話題にしただけでは鳴らさん
                if len(ACK) > 400:
                    for k in sorted(ACK)[:200]: ACK.pop(k, None)
            except Exception: pass
            if txt:
                with open(D + "/" + t.strftime("%Y-%m-%d") + ".md", "a") as f:
                    loc = " 🏠家" if rec["ie"] else ((" 📍%.4f,%.4f" % (rec["lat"], rec["lon"])) if rec["lat"] else "")
                    if (rec.get("douga") or 0) >= 0.5: loc += " 🎬"
                    if rec.get("lang") == "en": loc += " 🌐"   # 11/18 英語で書き起こした区切り
                    f.write("- " + t.strftime("%H:%M:%S") + loc + " " + txt + "\n")
            log("ok", os.path.basename(path), len(txt), "" if koe is None else f"声{koe}秒")
            # 11/14 夜 オーナー「聞いてから LINE が返るまでをもっと速く」＝願い・頼みの言葉が出たら、1分ごとの見回りを待たずに先回りの係をすぐ起こす
            # 11/18 英語で本人の声やない区切り（動画・周りの人）は、名前で呼ばれた時だけすぐ起こす
            eigo_hoka = rec.get("lang") == "en" and (rec.get("hon") or 0) < FILT.HON and not FILT.yobu(txt or "")
            if eigo_hoka: pass
            elif txt and not rec["ie"] and (ISOGI.search(txt) or FILT.yobu(txt) or FILT.tanomi(txt)) and time.time() - t.timestamp() < 300:   # 11/15 化けた名前（プライで等）でもすぐ起こす
                try: subprocess.Popen([sys.executable, HOME + "/bin/mimi-watch.py"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception: pass
            try: os.remove(path + ".meta")   # 済んだ印＝meta を消す（残っとる物は起こし直した時にやり直す）
            except OSError: pass
        except Exception as e:
            log("err", path, repr(e)[:200])
            try:   # 3回だめなら諦める（壊れた声で詰まらせん）
                m = json.load(open(path + ".meta")); m["try"] = m.get("try", 0) + 1
                if m["try"] >= 3: os.remove(path + ".meta")
                else: json.dump(m, open(path + ".meta", "w"))
            except Exception: pass
def yarinaoshi():
    """11/14 夜 起こし直すと待ち行列（メモリの中）が消えて、届いたのに文字にならん声が出る＝meta が残っとる声を並べ直す"""
    n = 0
    for day in sorted(os.listdir(RAW))[-2:] if os.path.isdir(RAW) else []:
        for f in sorted(os.listdir(f"{RAW}/{day}")):
            if f.endswith(".m4a.meta"):
                p = f"{RAW}/{day}/{f[:-5]}"
                try:
                    if os.path.exists(p): Q.put((p, json.load(open(p + ".meta")))); n += 1
                    else: os.remove(p + ".meta")
                except Exception: pass
    if n: log("やり直し", n, "本")
threading.Thread(target=worker, daemon=True).start()
yarinaoshi()
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, code, obj):
        try:
            b = json.dumps(obj).encode(); self.send_response(code); self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError): pass   # アプリが眠って接続が切れただけ
    def do_GET(self):
        if self.path == "/ping": return self._j(200, {"ok": True, "q": Q.qsize()})
        if self.path.startswith("/ack"):   # 11/16 v5 書き起こしが済むまで最大20秒待って「名前で呼ばれたか」を返す
            if self.headers.get("x-key") != KEY: return self._j(403, {"ok": False})
            fn = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("f", [""])[0]
            end = time.time() + 20
            while fn not in ACK and time.time() < end: time.sleep(0.25)
            return self._j(200, {"ok": True, "yobi": ACK.get(fn, 0), "done": fn in ACK})
        if self.path.startswith("/hb"):   # 11/14 アプリの心拍（1分ごと）＝止まったら mimi-watch が LINE で知らせる
            if self.headers.get("x-key") != KEY: return self._j(403, {"ok": False})
            import urllib.parse as up
            qs = dict(up.parse_qsl(up.urlparse(self.path).query))
            hp = D + ("/hb_ie.json" if qs.get("dev") in IE else "/hb.json")
            # 11/15 耳の原因調べ：12:04〜14:07 に声が1本も届かんかったのに、心拍の中身が残っとらんで「止めたのか・マイクが黙っとったのか」が分からんかった
            # → 心拍の様子が変わった時と10分ごとに hb.log へ1行（見張り mon_mimi.py が読む）
            try:
                key = "|".join(str(qs.get(k, "")) for k in ("dev", "on", "run", "st", "bg"))
                last = HB_LAST.get(qs.get("dev", ""), ("", 0))
                if key != last[0] or time.time() - last[1] > 600:
                    HB_LAST[qs.get("dev", "")] = (key, time.time())
                    with open(D + "/hb.log", "a") as f: f.write(datetime.datetime.now(JST).strftime("%m-%d %H:%M:%S ") + json.dumps(qs, ensure_ascii=False) + "\n")
            except Exception: pass
            # 11/15 v4 心拍の中身（音の大きさ lvl・送った keep・捨てた drop・動画 oa）を毎分残す＝声が届かん時に「マイクが黙っとる／静かすぎで捨てとる」を分ける
            if "lvl" in qs:
                try:
                    with open(D + "/hb_oto.jsonl", "a") as f:
                        f.write(json.dumps({"t": int(time.time()), **{k: qs.get(k) for k in ("dev", "on", "run", "bg", "vp", "lvl", "keep", "drop", "oa")}}, ensure_ascii=False) + "\n")
                except Exception: pass
            with open(hp + ".tmp", "w") as f: json.dump(qs | {"t": time.time()}, f, ensure_ascii=False)
            os.replace(hp + ".tmp", hp)
            # 11/15 v4 声の処理（エコー消し）のオン／オフを返す＝mimi/app_conf.json の vp（入れ直し不要で切り替え）
            try: vp = int(json.load(open(D + "/app_conf.json")).get("vp", 1))
            except Exception: vp = 1
            return self._j(200, {"ok": True, "vp": vp})
        self._j(404, {})
    def do_POST(self):
        if self.headers.get("x-key") != KEY: return self._j(403, {"ok": False})
        if self.path != "/up": return self._j(404, {})
        n = int(self.headers.get("content-length", 0))
        if n <= 0 or n > 20_000_000: return self._j(400, {"ok": False})
        body = self.rfile.read(n)
        def fl(k):
            try: return float(self.headers.get(k))
            except Exception: return None
        meta = {"at": self.headers.get("x-at"), "lat": fl("x-lat"), "lon": fl("x-lon"), "acc": fl("x-acc"), "dev": self.headers.get("x-dev") or "",
                "ta": fl("x-ta"), "vp": fl("x-vp")}
        day = datetime.datetime.now(JST).strftime("%Y-%m-%d"); os.makedirs(RAW + "/" + day, exist_ok=True)
        p = f"{RAW}/{day}/{int(time.time()*1000)}.m4a"
        with open(p, "wb") as f: f.write(body)
        with open(p + ".meta", "w") as f: json.dump(meta, f)
        Q.put((p, meta))
        if meta["dev"] not in IE:   # 家に置いた iPhone の場所は「オーナー様の今の場所」にせん
            with open(D + "/last_loc.json", "w") as f: json.dump(meta | {"recv": time.time()}, f)
        self._j(200, {"ok": True, "f": os.path.basename(p)})
http.server.ThreadingHTTPServer(("100.64.0.1", 8840), H).serve_forever()
