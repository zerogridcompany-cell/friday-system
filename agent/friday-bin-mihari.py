#!/usr/bin/env python3
"""便の見張り（mini の launchd・2分ごと）2026-11-11 オーナー「搭乗までは状況常に確認しておいて欲しい。この便もこの先の便も搭乗状況とか」
FlightAware の便のページ（trackpollBootstrap）＋FlightStats（11/11〜・荷物のベルト・到着の搭乗口）＋Flightradar24 の地図データ（11/11〜・離陸・位置・着陸）を読み、変わった時だけ LINE で知らせる：
  搭乗口・出発の遅れ（10分以上の動き）・機材・欠航/目的地変更・出発（押し出し）・着陸
＋決まった時刻の知らせ：搭乗開始・搭乗口が閉まる10分前。
窓＝出発の6時間前〜到着の2時間後。状態は bin_mihari.json。--test で読むだけ（送らん）。
時刻の表示＝出発地の時間（中国＝UTC+8）。日本に着く便の着陸は日本時間。"""
import os, re, sys, json, time, datetime, subprocess, urllib.request
HOME = os.path.expanduser("~"); F = f"{HOME}/owner-kotoba/friday"; ST = f"{F}/bin_mihari.json"; LOG = f"{F}/bin_mihari.log"
TEST = "--test" in sys.argv
CN = datetime.timezone(datetime.timedelta(hours=8)); JP = datetime.timezone(datetime.timedelta(hours=9))
# 便の台帳（足す時はここに1行）。board/close は搭乗券・航空会社の案内の時刻（出発地の時間）
BINS = [
    {"id": "XX123-0101", "fa": "XXX123", "name": "XX123", "date": "2026-01-01", "dep": "09:30", "tz": CN, "arr_tz": CN,
     "board": "08:50", "close": "09:10", "gate": None, "seat": None, "type": None, "to": "到着空港"},
    # 11/12 C：航空会社の公式の案内＝国際線の受付は出発50分前・搭乗口は出発20分前に閉まる。
    # 搭乗開始は公式に決まりが無い＝メモの目安（board_meyasu）。席＝予約の控えから。機材＝FlightAware
    {"id": "YY456-0103", "fa": "YYY456", "name": "YY456", "date": "2026-01-03", "dep": "09:40", "tz": CN, "arr_tz": JP,
     "board": "09:00", "board_meyasu": True, "close": "09:20", "gate": None, "seat": None, "type": None, "to": "到着空港"},
]
now = datetime.datetime.now(datetime.timezone.utc)
def log(s): open(LOG, "a").write(f"{datetime.datetime.now():%F %T} {s}\n")
def hm(ts, tz): return datetime.datetime.fromtimestamp(ts, tz).strftime("%H:%M") if ts else "?"
def send(text):
    if TEST: print("［送る］", text); return
    r = subprocess.run([f"{HOME}/bin/friday-send", text, "--reply"], capture_output=True, text=True, timeout=60)
    log(f"送った {text[:60]} → {r.stdout.strip()[:80]} {r.stderr.strip()[:80]}")
def fa(ident, date, tz):
    r = urllib.request.Request(f"https://www.flightaware.com/live/flight/{ident}",
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"})
    s = urllib.request.urlopen(r, timeout=25).read().decode("utf-8", "ignore")
    d = json.loads(re.search(r"var trackpollBootstrap = (\{.*?\});\s*</script>", s, re.S).group(1))
    for f in d["flights"].values():
        for a in f.get("activityLog", {}).get("flights", []):
            sch = (a.get("gateDepartureTimes") or {}).get("scheduled")
            if sch and datetime.datetime.fromtimestamp(sch, tz).strftime("%F") == date: return a
    return None
def fr24(name):
    """Flightradar24 の地図データ（feed.js・便名で引く）。clickhandler と api は Cloudflare で止まる＝地図データだけ使う。
    返す＝{lat, lon, alt(ft), spd(kt), gnd(0/1), ts, reg, type, frm, to} か None（まだ電波なし）"""
    r = urllib.request.Request(f"https://data-cloud.flightradar24.com/zones/fcgi/feed.js?flight={name}&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=1&air=1&vehicles=0&estimated=1&maxage=14400&gliders=0&stats=0",
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Referer": "https://www.flightradar24.com/"})
    d = json.loads(urllib.request.urlopen(r, timeout=25).read().decode("utf-8", "ignore"))
    for k, v in d.items():
        if isinstance(v, list) and len(v) > 16 and v[13] == name:
            return {"id": k, "lat": v[1], "lon": v[2], "alt": v[4], "spd": v[5], "gnd": v[14], "ts": v[10], "type": v[8], "reg": v[9], "frm": v[11], "to": v[12]}
    return None
def fstats(name, date):
    """FlightStats の便のページ（__NEXT_DATA__）。2026-11-11 オーナー「あらゆる情報でスピーディに」で足した。
    FlightAware に無い＝到着の荷物のベルト・到着ターミナル・到着の搭乗口・機体番号。返す＝flight の dict か None"""
    al, num = re.match(r"([A-Z0-9]{2})(\d+)", name).groups(); y, m, d = date.split("-")
    r = urllib.request.Request(f"https://www.flightstats.com/v2/flight-tracker/{al}/{num}?year={y}&month={int(m)}&date={int(d)}",
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"})
    s = urllib.request.urlopen(r, timeout=25).read().decode("utf-8", "ignore")
    i = s.find("__NEXT_DATA__ = ")
    if i < 0: return None
    j, _ = json.JSONDecoder().raw_decode(s[i + 16:])
    fl = j.get("props", {}).get("initialState", {}).get("flightTracker", {}).get("flight") or None
    if not fl or not (fl.get("schedule") or {}).get("scheduledDeparture", "").startswith(date): return None
    return fl
st = json.load(open(ST)) if os.path.exists(ST) else {}
for b in BINS:
    tz = b["tz"]; dep = datetime.datetime.strptime(f"{b['date']} {b['dep']}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    s = st.setdefault(b["id"], {"gate": b["gate"], "type": b["type"], "est": None, "sent": []})
    if s.get("done") and not TEST: continue
    if not TEST and not (dep - datetime.timedelta(hours=6) <= now <= dep + datetime.timedelta(hours=8)): continue
    def once(key, text):
        if key in s["sent"]: return
        send(text); s["sent"].append(key) if not TEST else None
    # 決まった時刻の知らせ
    loc = now.astimezone(tz)
    for k, t, msg in (("board", b["board"], "搭乗開始のお時間です"), ("close10", b["close"], None)):
        if not t: continue
        at = datetime.datetime.strptime(f"{b['date']} {t}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        if k == "close10": at -= datetime.timedelta(minutes=10)
        if at <= now <= at + datetime.timedelta(minutes=8):
            g = s.get("gate") or "未定"
            if k == "board" and b.get("board_meyasu"): once(k, f"オーナー様、{t}、{b['name']}の搭乗開始の目安のお時間です。搭乗口は{g}、お席は{b['seat'] or '搭乗券のとおり'}です。搭乗口は{b['close']}に閉まります。")
            elif k == "board": once(k, f"オーナー様、{t}、{b['name']}の{msg}。搭乗口は{g}、お席は{b['seat'] or '搭乗券のとおり'}です。")
            else: once(k, f"オーナー様、{b['name']}の搭乗口（{g}）は{b['close']}に閉まります。あと10分です。まだでしたら搭乗口へお急ぎください。")
    # Flightradar24（2026-11-11 オーナー「飛行機に関してはフライトレーダーとかで見ておいて」）
    try:
        r = fr24(b["name"])
        if r and datetime.datetime.fromtimestamp(r["ts"], tz).strftime("%F") == b["date"]:
            s["fr24"] = {**r, "seen": now.isoformat(timespec="seconds")}
            if TEST: print(b["id"], "FR24", r)
            if r["gnd"] == 0 and r["alt"] > 500:
                once("takeoff", f"✈️ オーナー様、{b['name']}は離陸いたしました（Flightradar24・{hm(r['ts'], tz)}時点で高度{r['alt']:,}ft）。{b['to']}へ向かっております。")
                s["air"] = True
            if r["gnd"] == 1 and s.get("air"):
                once("land", f"オーナー様、{b['name']}は{hm(r['ts'], b['arr_tz'])}に{b['to']}へ着陸いたしました（Flightradar24）。" + (f"お荷物は{s['belt']}番のベルトです。" if s.get("belt") else "") + "おつかれさまでございました。")
        elif TEST: print(b["id"], "FR24 まだ電波なし")
    except Exception as e: log(f"{b['id']} FR24 読めん {e}")
    try:
        fl = fstats(b["name"], b["date"])
        if fl:
            ap = fl.get("arrivalAirport") or {}; dp = fl.get("departureAirport") or {}; stt = fl.get("status") or {}; sc = fl.get("schedule") or {}
            if TEST: print(b["id"], "FS", stt.get("status"), "dep gate", dp.get("gate"), "arr T", ap.get("terminal"), "gate", ap.get("gate"), "belt", ap.get("baggage"), "eta", sc.get("estimatedActualArrival"))
            if stt.get("statusCode") == "C": once("cancel", f"🔴 オーナー様、{b['name']}が欠航と表示されております（FlightStats）。航空会社のアプリで、振替の便をお確かめください。")
            if stt.get("diverted"): once("divert", f"🔴 オーナー様、{b['name']}は{b['to']}以外へ目的地が変わったと表示されております（FlightStats）。")
            # 着いた後に要る物＝荷物のベルト・到着の搭乗口（出た時・変わった時）
            belt = ap.get("baggage")
            if belt and belt != s.get("belt"):
                send(f"🧳 オーナー様、{b['name']}の預け荷物は{ap.get('terminal') and 'T' + str(ap['terminal']) + 'の' or ''}{belt}番のベルトに出る予定です（FlightStats）。" + (f"（{s['belt']}番から変わりました）" if s.get("belt") else ""))
                s["belt"] = belt
            ag = ap.get("gate")
            if ag and ag != s.get("arr_gate"):
                if s.get("arr_gate"): send(f"オーナー様、{b['name']}の到着の搭乗口が{s['arr_gate']}から{ag}に変わりました（FlightStats）。")
                s["arr_gate"] = ag
            # 出発の搭乗口は FlightAware より先に出ることがある
            dg = dp.get("gate")
            if dg and dg != s.get("gate") and fl.get("isScheduled"):
                if s.get("gate"): send(f"⚠️ オーナー様、{b['name']}の搭乗口が{s['gate']}から{dg}に変わりました（FlightStats）。")
                s["gate"] = dg
            s["fs"] = {"status": stt.get("status"), "eta": sc.get("estimatedActualArrival"), "belt": belt, "seen": now.isoformat(timespec="seconds")}
            if fl.get("isLanded") and sc.get("estimatedActualArrivalRunway") is not None:
                t_ = (sc.get("estimatedActualArrival") or "")[11:16]
                once("land", f"オーナー様、{b['name']}は{t_}に{b['to']}へ着陸いたしました（FlightStats）。" + (f"お荷物は{belt}番のベルトです。" if belt else "") + "おつかれさまでございました。")
    except Exception as e: log(f"{b['id']} FlightStats 読めん {e}")
    try: a = fa(b["fa"], b["date"], tz)
    except Exception as e: log(f"{b['id']} 読めん {e}"); continue
    if not a: log(f"{b['id']} その日の便がまだ出てない"); continue
    o = a.get("origin") or {}; de = a.get("destination") or {}
    gd = a.get("gateDepartureTimes") or {}; to = a.get("takeoffTimes") or {}; ld = a.get("landingTimes") or {}; ga = a.get("gateArrivalTimes") or {}
    if TEST: print(b["id"], "gate", o.get("gate"), "type", a.get("aircraftType"), "est", hm(gd.get("estimated"), tz), "act", hm(gd.get("actual"), tz), "status", a.get("flightStatus"))
    if a.get("cancelled"): once("cancel", f"🔴 オーナー様、{b['name']}が欠航と表示されております（FlightAware）。航空会社のアプリで、振替の便をお確かめください。")
    if a.get("diverted"): once("divert", f"🔴 オーナー様、{b['name']}は{b['to']}以外へ目的地が変わったと表示されております（FlightAware）。")
    g = o.get("gate")
    if g and g != s.get("gate") and not gd.get("actual"):
        if s.get("gate"): send(f"⚠️ オーナー様、{b['name']}の搭乗口が{s['gate']}から{g}に変わりました。")
        s["gate"] = g
    t = a.get("aircraftType")
    if t and s.get("type") and t != s["type"] and not gd.get("actual"):
        send(f"オーナー様、{b['name']}の機材が{s['type']}から{t}に変わったと表示されております（FlightAware）。お席は搭乗券のとおりです。")
    if t: s["type"] = t
    est, sch = gd.get("estimated"), gd.get("scheduled")
    if est and sch and not gd.get("actual"):
        base = s.get("est") or sch
        if abs(est - base) >= 600:
            late = (est - sch) // 60
            send(f"⚠️ オーナー様、{b['name']}の出発予定が{hm(est, tz)}に変わりました（定刻{hm(sch, tz)}・{'約' + str(late) + '分遅れ' if late > 0 else '定刻どおり'}）。到着予定は{hm(ga.get('estimated'), b['arr_tz'])}です。")
            s["est"] = est
        elif not s.get("est"): s["est"] = est
    if to.get("actual"):
        once("takeoff", f"✈️ オーナー様、{b['name']}は{hm(to['actual'], tz)}に離陸いたしました（FlightAware）。{b['to']}には{hm(ga.get('estimated'), b['arr_tz'])}ごろ到着の見込みです。")
    # 飛んどる間の到着予定のずれ（10分以上）
    ge = ga.get("estimated")
    if ge and to.get("actual") and not ld.get("actual"):
        if s.get("eta") and abs(ge - s["eta"]) >= 600:
            send(f"オーナー様、{b['name']}の到着予定が{hm(s['eta'], b['arr_tz'])}から{hm(ge, b['arr_tz'])}に変わりました（FlightAware）。")
            s["eta"] = ge
        elif not s.get("eta"): s["eta"] = ge
    if gd.get("actual"):
        once("out", f"✈️ オーナー様、{b['name']}は{hm(gd['actual'], tz)}に搭乗口を離れました（定刻{hm(sch, tz)}）。{b['to']}には{hm(ga.get('estimated'), b['arr_tz'])}ごろ到着の見込みです。")
    if ld.get("actual"):
        once("land", f"オーナー様、{b['name']}は{hm(ld['actual'], b['arr_tz'])}に{b['to']}へ着陸いたしました（FlightAware）。" + (f"お荷物は{s['belt']}番のベルトです。" if s.get("belt") else "") + "おつかれさまでございました。")
        # 11/12 C：着陸だけで done にするとベルトを見に行かん＝ベルトを知らせたか、着陸から90分たったら終わり
        if s.get("belt") or now.timestamp() > ld["actual"] + 5400: s["done"] = True
if not TEST: json.dump(st, open(ST, "w"), ensure_ascii=False, indent=1)
