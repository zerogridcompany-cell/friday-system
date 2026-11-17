#!/usr/bin/env python3
"""フライデー（LINE）のこの月の送信数を見て、月200通を超えそうなら1行出す（朝のまとめに足す）。10/29"""
import json, os, urllib.request, datetime, calendar
d = json.load(open(os.path.expanduser("~/.config/line/friday.json")))
H = {"Authorization": "Bearer " + d["access_token"]}
g = lambda u: json.load(urllib.request.urlopen(urllib.request.Request("https://api.line.me/v2/bot/message/quota" + u, headers=H)))
used = g("/consumption").get("totalUsage", 0); lim = g("").get("value", 200)
t = datetime.date.today(); days = calendar.monthrange(t.year, t.month)[1]
proj = round(used / t.day * days)
if proj > lim * 0.9 or used > lim * 0.8:
    print(f"⚠️ フライデーから先に送る分：今月 {used}/{lim}通（このままやと月末に約{proj}通）。超えたら月末まで先回りの知らせが止まる（返事は止まらん）")
