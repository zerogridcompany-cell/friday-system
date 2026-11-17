#!/usr/bin/env /usr/bin/python3
"""フライデーの Discord 見張り（11/01 オーナー「今後 Discord も LINE と一緒に確認して。サーバーAのメインと、〈会社〉のメインチャット」）。
mini の Discord デスクトップアプリ（ログイン済み）を CDP 9339 で読むだけ。送らん・反応せん。
  friday-discord.py <run の出力フォルダ>   … 新しい発言があったチャンネルごとに <フォルダ>/<名前>/0.txt を作り、名前を1行ずつ出す
  friday-discord.py --peek                  … 状態を変えずに直近を見るだけ
状態＝~/owner-kotoba/friday/discord_last.json（チャンネルごとの最後の発言ID）。
"""
import json, os, subprocess, sys, time, urllib.request
import websocket

PORT = 9339
CHANNELS = [  # (見張りの名前, サーバーID, チャンネルID)
    ("Discord_サーバーA_main-chat", "YOUR_GUILD_ID_A", "YOUR_CHANNEL_ID_A"),
    ("Discord_〈会社〉_main-chat", "YOUR_GUILD_ID_B", "YOUR_CHANNEL_ID_B"),  # 11/01 仕事の連絡が来た所
]
STATE = os.path.expanduser("~/owner-kotoba/friday/discord_last.json")

READ = r"""(async(g,c)=>{
 const w=ms=>new Promise(r=>setTimeout(r,ms));
 const gi=document.querySelector('[data-list-item-id=guildsnav___'+g+']'); if(!gi) return 'NOGUILD';
 gi.click(); await w(1800);
 const ci=document.querySelector('[data-list-item-id=channels___'+c+']'); if(!ci) return 'NOCHANNEL';
 ci.click();
 let last='',same=0;
 for(let i=0;i<20;i++){await w(500);const L=document.querySelectorAll('li[id^=chat-messages-'+c+']');
   const k=L.length?L[L.length-1].id:''; if(k&&k===last){if(++same>=2)break}else{same=0;last=k}}
 let who='';
 return JSON.stringify([...document.querySelectorAll('li[id^=chat-messages-'+c+']')].slice(-15).map(li=>{
  const a=li.querySelector('[id^=message-username-]'); if(a) who=a.innerText.split('\n')[0].replace(/[,、]\s*$/,'').trim();
  const t=li.querySelector('time'); const m=li.querySelectorAll('[id^=message-content-]');
  const acc=li.querySelector('[id^=message-accessories-]');
  return {id:li.id.split('-').pop(),who:who,when:t?t.getAttribute('datetime'):'',
   text:(m.length?m[m.length-1].innerText:'')+(acc&&acc.innerText&&!/リアクション/.test(acc.innerText)?' ［添付・埋め込み］'+acc.innerText.slice(0,80).replace(/\n/g,' '):'')}}))
})"""


def port_up():
    try:
        return [t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3))
                if t["type"] == "page" and "discord.com" in t["url"]]
    except Exception:
        return []


def ensure_app():
    tabs = port_up()
    if tabs:
        return tabs[0]
    # 🔴 ふつうに開いた Discord は CDP が無い＝1回だけ閉じて、ポート付きで開き直す（ログインは残る）
    subprocess.run(["osascript", "-e", 'tell application "Discord" to quit'], capture_output=True)
    time.sleep(5)
    subprocess.run(["open", "-g", "-a", "Discord", "--args", f"--remote-debugging-port={PORT}",
                    "--remote-allow-origins=http://127.0.0.1"], capture_output=True)
    for _ in range(30):
        time.sleep(2)
        tabs = port_up()
        if tabs:
            time.sleep(6)  # 画面が描けるまで
            return tabs[0]
    sys.exit("Discord の CDP がつながらん")


def main():
    peek = "--peek" in sys.argv
    out = None if peek else sys.argv[1]
    tab = ensure_app()
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=60, origin="http://127.0.0.1")
    n = 0

    def js(e):
        nonlocal n
        n += 1
        ws.send(json.dumps({"id": n, "method": "Runtime.evaluate",
                            "params": {"expression": e, "returnByValue": True, "awaitPromise": True}}))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == n:
                return r["result"]["result"].get("value")

    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    for name, g, c in CHANNELS:
        v = js(f"{READ}('{g}','{c}')")
        if not v or not v.startswith("["):
            print(f"#{name}: 読めん（{v}）", file=sys.stderr)
            continue
        msgs = json.loads(v)
        if not msgs:
            continue
        if peek:
            print(f"== {name}")
            for m in msgs[-5:]:
                print(f"  {m['when'][:16]} {m['who']}: {m['text'][:100]}")
            continue
        seen = state.get(c)
        new = [m for m in msgs if seen and int(m["id"]) > int(seen)]
        state[c] = max(msgs, key=lambda m: int(m["id"]))["id"]
        if not new:
            continue  # 初回は「ここまで読んだ」を覚えるだけ
        d = os.path.join(out, name.replace("/", "／"))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "0.txt"), "w") as f:
            f.write("0\t0\t0\t（Discord・文字はそのまま。日時は日本時間）\n")
            for m in new:
                when = ""
                if m["when"]:
                    t = time.strptime(m["when"][:19], "%Y-%m-%dT%H:%M:%S")
                    when = time.strftime("%m/%d %H:%M", time.localtime(time.mktime(t) - time.timezone))
                for i, line in enumerate((m["text"] or "（文字なし）").split("\n")):
                    if line.strip():
                        f.write(f"0\t0\t0\t{when} {m['who'] or '（名前読めず）'}：{line}\n" if i == 0 else f"0\t0\t0\t　{line}\n")
        print(name)
    if not peek:
        json.dump(state, open(STATE, "w"))
    ws.close()


main()
