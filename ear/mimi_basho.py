#!/usr/bin/env python3
"""11/14 夜 オーナー「位置情報と耳の情報でさらに正確に」＝緯度経度を言葉にする（どこ・止まっとるか歩きか乗り物か・速さ・向き）。
mimi-watch・mimi-matome が import して文に混ぜる。
点の元＝①OwnTracks の記録（~/work/nearby/loc.db・静かな時も貯まる）②耳の声に付いた場所（mimi.jsonl）。新しい方・細かい方を使う。
地名＝OSM nominatim／駅＝HeartRails Express。約100m の升で7日ためる（同じ所に何回も聞かん・取れんかった時はためん）。"""
import json, os, math, time, datetime, sqlite3, urllib.request
HOME = os.path.expanduser("~"); D = HOME + "/owner-kotoba/friday/mimi"; C = D + "/basho_cache.json"
DB = HOME + "/work/nearby/loc.db"; USER = "YOUR_OWNTRACKS_USER"
JST = datetime.timezone(datetime.timedelta(hours=9))
def _km(a, b): return math.hypot((a["lat"] - b["lat"]) * 111, (a["lon"] - b["lon"]) * 91)
def _ts(r): return datetime.datetime.fromisoformat(r["at"]).timestamp()
def _get(url, t=8):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "friday-mimi/1.0"}), timeout=t))
def chimei(lat, lon):
    k = f"{lat:.3f},{lon:.3f}"
    try: c = json.load(open(C))
    except Exception: c = {}
    v = c.get(k)
    if isinstance(v, dict) and time.time() - v.get("t", 0) < 7 * 86400: return v["s"]
    ok = True; area = eki = name = ""
    try:
        a = _get(f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=17&accept-language=ja&lat={lat}&lon={lon}").get("address", {})
        name = next((a[x] for x in ("railway", "station", "amenity", "shop", "building", "tourism") if a.get(x)), "")
        parts = []
        for x in ("city", "town", "suburb", "neighbourhood", "quarter"):
            w = a.get(x, "")
            if not w or any(w in q for q in parts): continue
            parts = [q for q in parts if q not in w] + [w]   # 「◯◯」と「◯◯一丁目」は細かい方だけ残す
        area = "".join(parts)
    except Exception: ok = False
    try:   # 一番近い駅と路線（日本の駅だけ・500m 以内）
        st = [x for x in _get(f"https://express.heartrails.com/api/json?method=getStations&x={lon}&y={lat}").get("response", {}).get("station", [])
              if int(str(x.get("distance", "9999m")).rstrip("m")) <= 500]
        if st: eki = st[0]["name"] + "駅（" + "・".join(dict.fromkeys(x["line"] for x in st if x["name"] == st[0]["name"]))[:40] + "）"
    except Exception:
        if 24 < lat < 46 and 122 < lon < 146: ok = False   # 日本の中で取れんかった時だけ「取れんかった」扱い
    s = "・".join(x for x in ((eki + "の近く") if eki else (name + "の近く" if name else ""), area) if x)
    if s and ok:
        c[k] = {"s": s, "t": time.time()}
        if len(c) > 3000: c = dict(sorted(c.items(), key=lambda kv: kv[1].get("t", 0) if isinstance(kv[1], dict) else 0)[-2000:])
        tmp = C + ".tmp"; json.dump(c, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, C)
    return s
def ten(recs, until=None, mins=12):
    """until（ISO・無ければ今）までの mins 分の点。OwnTracks を先に、足りん時は耳の点"""
    t1 = datetime.datetime.fromisoformat(until).timestamp() if until else time.time()
    t0 = t1 - mins * 60; p = []
    try:
        db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=3)
        for ts, lat, lng, acc, spd in db.execute("select ts,lat,lng,acc,speed from locs where user=? and ts between ? and ? order by ts", (USER, t0 * 1000, t1 * 1000)):
            if lat and lng: p.append({"t": ts / 1000, "lat": lat, "lon": lng, "acc": acc or 50, "spd": spd})
        db.close()
    except Exception: pass
    for r in recs:
        if r.get("lat") and not r.get("ie"):
            t = _ts(r)
            if t0 <= t <= t1: p.append({"t": t, "lat": r["lat"], "lon": r["lon"], "acc": r.get("acc") or 100, "spd": None})
    p = [x for x in p if x["acc"] < 200]; p.sort(key=lambda x: x["t"]); return p
def ugoki(p):
    """点の並びから 止まっとる／歩き／乗り物・速さ・向き。GPS の揺れ（精度の2倍より小さい動き）は「止まっている」"""
    if len(p) < 2: return ""
    last = p[-1]; old = [x for x in p if 90 <= last["t"] - x["t"] <= 600]
    if not old: return ""
    a = old[0]; sec = last["t"] - a["t"]; km = _km(a, last); kmh = km / sec * 3600
    b = old[-1]; kmh2 = _km(b, last) / max(1, last["t"] - b["t"]) * 3600   # 直近（1.5〜分）の速さ＝駅で止まった・走り出したを拾う
    yure = (a["acc"] + last["acc"]) * 2 / 1000
    if km < yure or kmh < 3: return "止まっている"   # 11/15 家の中で「歩いている（時速約2km）」と出た＝GPS の揺れ
    if max(kmh, kmh2) < 7.5: return f"歩いている（時速約{kmh:.0f}km）"
    dy, dx = last["lat"] - a["lat"], (last["lon"] - a["lon"]) * 0.82
    hou = "北 北東 東 南東 南 南西 西 北西".split()[round((math.degrees(math.atan2(dx, dy)) % 360) / 45) % 8]
    return f"乗り物で移動中（時速約{max(kmh, kmh2):.0f}km・{hou}へ・{int(sec // 60)}分で{km:.1f}km）"
def kotoba(recs, until=None):
    """先回り・まとめに渡す1行。例：◯◯駅（◯◯線…）の近く・◯◯区◯◯（35.0000,139.0000・19:58 時点）／乗り物で移動中（時速約60km・東へ）"""
    p = ten(recs, until)
    if not p: p = ten(recs, until, mins=180)[-1:]   # 12分点が無い時は3時間まで戻って最後の1点（場所だけ・動きは言わん）
    if not p: return "不明"
    last = p[-1]
    at = datetime.datetime.fromtimestamp(last["t"], JST).strftime("%H:%M")
    s = ugoki(p)
    return f"{chimei(last['lat'], last['lon'])}（{last['lat']:.5f},{last['lon']:.5f}・{at} 時点）" + (f"／{s}" if s else "")
IE = (35.0000, 139.0000)   # 家（耳の記録の「🏠」と同じ点）
def ie_ni_iru():
    p = ten([], None, mins=20)
    return bool(p) and _km({"lat": IE[0], "lon": IE[1]}, p[-1]) < 0.3
if __name__ == "__main__":
    import sys
    if "--ie" in sys.argv: sys.exit(0 if ie_ni_iru() else 1)
    recs = [json.loads(l) for l in open(D + "/mimi.jsonl") if l.strip()]
    print(kotoba(recs, sys.argv[1] if len(sys.argv) > 1 else None))
