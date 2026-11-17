#!/usr/bin/env python3
"""家の耳（11/14）：Mac mini に挿した EarPods のマイクで家の音を30秒ずつ録り、声がある物だけ mimi-server に送る。
マイクの許可は Terminal にある＝画面の Terminal から動かす（mimi-ie-keep.sh が見張って落ちとったら起こす）。iPhone を使わんのでミラーリングとぶつからん。"""
import os, re, subprocess, time, json, urllib.request, glob, signal, sys
HOME = os.path.expanduser("~"); SP = HOME + "/owner-kotoba/friday/mimi/ie_spool"; os.makedirs(SP, exist_ok=True)
FF = HOME + "/.local/bin/ffmpeg" if os.path.exists(HOME + "/.local/bin/ffmpeg") else "/opt/homebrew/bin/ffmpeg"
KEY = open(HOME + "/.config/friday/mimi.key").read().strip()
URL = "http://100.64.0.1:8840"; DEV = "mini-ie"; GATE = -33.0   # 30秒の中の一番大きい音がこれ（dB）より小さければ送らん＝無音・遠い雑音
LOG = HOME + "/owner-kotoba/friday/mimi/ie_rec.log"
def log(s):
    with open(LOG, "a") as f: f.write(time.strftime("%m-%d %H:%M:%S ") + s + "\n")
def mic():
    out = subprocess.run([FF, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""], capture_output=True, text=True).stderr
    for name in ("EarPods", "USB", "マイク"):
        for l in out.splitlines():
            m = re.search(r"\] \[(\d+)\] (.*)$", l)
            if m and name in m.group(2) and "iPhone" not in m.group(2): return m.group(2).strip().lstrip("‎")
    return None
def hb(st):
    try:
        q = urllib.parse.urlencode({"on": "1", "run": "1" if st == "聞いています" else "0", "st": st, "dev": DEV, "stopsec": "0"})
        urllib.request.urlopen(urllib.request.Request(f"{URL}/hb?{q}", headers={"x-key": KEY}), timeout=8)
    except Exception: pass
import urllib.parse
name = mic()
if not name: log("マイクが見つからん（EarPods を挿して）"); hb("マイクが見つからん"); sys.exit(1)
log(f"start {name}")
p = subprocess.Popen([FF, "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-i", ":" + name, "-ac", "1", "-ar", "16000",
                      "-c:a", "aac", "-b:a", "32k", "-f", "segment", "-segment_time", "30", "-reset_timestamps", "1", "-strftime", "1",
                      SP + "/%Y%m%d-%H%M%S.m4a"])
last_hb = 0
try:
    while p.poll() is None:
        fs = sorted(glob.glob(SP + "/*.m4a"))
        for f in fs[:-1]:   # 一番新しいのは録っとる途中
            r = subprocess.run([FF, "-hide_banner", "-i", f, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
            m = re.search(r"max_volume: (-?[\d.]+) dB", r); mx = float(m.group(1)) if m else -99
            if mx > GATE:
                ts = os.path.basename(f)[:15]; at = time.strftime("%Y-%m-%dT%H:%M:%S+09:00", time.strptime(ts, "%Y%m%d-%H%M%S"))
                try:
                    rq = urllib.request.Request(URL + "/up", data=open(f, "rb").read(), method="POST",
                                                headers={"x-key": KEY, "x-dev": DEV, "x-at": at, "content-type": "audio/mp4"})
                    urllib.request.urlopen(rq, timeout=30)
                except Exception as e:
                    log(f"送れん {e}"); break   # 次の回にもう一度
            os.remove(f)
        if time.time() - last_hb > 60: hb("聞いています"); last_hb = time.time()
        time.sleep(5)
finally:
    p.send_signal(signal.SIGINT); log(f"end rc={p.poll()}"); hb("止まっています")
