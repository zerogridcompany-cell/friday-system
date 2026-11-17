#!/bin/zsh
# フライデーの見張り（Air launchd com.owner.friday-watch・5分ごと）：mini の LINE で動いたトークを撮る→Claude（Opus）が提案を考える→フライデー（LINE @YOUR_BOT_ID）でオーナーに送る（10/29 オーナー）
# 記録＝~/owner-kotoba/friday/watch.log ／ 送った提案＝~/owner-kotoba/friday/sent.jsonl
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$HOME/.local/bin:$HOME/bin
F=~/owner-kotoba/friday; mkdir -p $F; LOG=$F/watch.log; LOCK=$F/watch.lock
[ -f ~/owner-kotoba/line-asa.lock ] && exit 0                     # 朝のカレンダー係が LINE を使っとる
[ -f $LOCK ] && [ $(( $(date +%s) - $(stat -f %m $LOCK) )) -lt 600 ] && exit 0
# Air と mini の両方から5分ごとに呼ばれる。同じ5分の枠は先に取った方だけが動く（Cloudflare friday-line /once）
ME=$( [ -d /Users/owner ] && echo mini || echo air ); SLOT=$(( $(date +%s) / 300 ))
# 11/03 オーナー「同じメッセージ送らないで」＝見張りは mini だけ。Air も動くと送った記録が2つに割れて同じ知らせが2回飛んだ（9:22 Air・9:28 mini）。Air は mini 経由でしか LINE を見れんので控えの意味も無い
[ $ME = air ] && exit 0
KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/line/friday.json')))['agent_key'])")
RUN=$($HOME/bin/fcurl -s -m 15 -A friday-agent/1 -H "x-agent-key: $KEY" -H "x-agent: $ME" "https://friday-line.example.workers.dev/once?job=fw:$SLOT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('run'))" 2>/dev/null)
[ "$RUN" = "True" ] || exit 0
touch $LOCK; trap 'rm -f $LOCK' EXIT
if [ $ME = mini ]; then
  ~/bin/gamen try fw || { echo "$(date '+%F %T') 画面を頼みが使用中→この回は飛ばす" >> $LOG; exit 0; }   # 11/03 画面の鍵
  trap 'rm -f $LOCK; ~/bin/gamen done fw' EXIT
  T=~/work/linemini/t; rm -f $T/fw/run/fin
  ssh -i ~/.ssh/id_ed25519_self -o BatchMode=yes localhost "osascript -e 'tell application \"Terminal\" to do script \"zsh ~/work/linemini/t/fw.sh > ~/work/linemini/t/fw/out.txt 2>&1; exit\"'" >/dev/null 2>>$LOG  # launchd から直に Terminal は動かせん＝自分への ssh 経由（10/29）
  for i in $(seq 1 60); do [ -f $T/fw/run/fin ] && break; sleep 3; done
else
  ~/bin/mini run "cd ~/work/linemini/t; rm -f fw/run/fin; cat > fw.scpt <<X
tell application \"Terminal\" to do script \"zsh ~/work/linemini/t/fw.sh > ~/work/linemini/t/fw/out.txt 2>&1; exit\"
X
osascript fw.scpt" >/dev/null 2>>$LOG || { echo "$(date '+%F %T') mini に届かん" >> $LOG; exit 1; }
  for i in $(seq 1 60); do ~/bin/mini run "test -f linemini/t/fw/run/fin" 2>/dev/null && break; sleep 3; done
fi
TS=$(date +%Y%m%d_%H%M); W=$F/runs/$TS; mkdir -p $W
if [ $ME = mini ]; then rsync -a ~/work/linemini/t/fw/run/ $W/; else rsync -a project-j-macmini:work/linemini/t/fw/run/ $W/ 2>>$LOG; fi
CH=0; [ -s $W/changed.txt ] && CH=$(grep -c . $W/changed.txt)
if [ "$CH" = "0" ]; then echo "$(date '+%F %T') 変化なし（一覧$(python3 -c "import json;print(len(json.load(open('$W/rows.json'))))" 2>/dev/null)行）" >> $LOG; rm -rf $W; exit 0; fi   # 11/13 変化0の回も1行（32時間黙っとって目隠しに気づけんかった）
IN=$W/input.md; : > $IN
for d in $W/*(N/); do c=${d:t}
  echo "\n## $c" >> $IN
  for t in $d/*.txt(NOn); do awk -F"\t" '{print ($5=="右" ? "【オーナー（右の吹き出し）】" : "") $4}' "$t"; done | awk '!seen[$0]++' >> $IN   # 11/04 右＝オーナー
done
tail -20 $F/sent.jsonl > $W/sent.txt 2>/dev/null; touch $W/sent.txt
sed -e "s#{INPUT}#$IN#" -e "s#{SENT}#$W/sent.txt#" ~/bin/friday-prompt.md > $W/prompt.md
cd $W && perl -e 'alarm shift; exec @ARGV' 540 ${CLAUDE_BIN:-claude} -p --model opus --permission-mode bypassPermissions < $W/prompt.md > $W/result.txt 2>>$LOG
J=$(grep -o 'FRIDAY {.*}' $W/result.txt | tail -1 | sed 's/^FRIDAY //')
echo "$(date '+%F %T') 動いた$CH件 → ${J:0:200}" >> $LOG
[ -z "$J" ] && exit 0
python3 - "$J" "$F/sent.jsonl" <<'PY'
import sys,json,subprocess,datetime
j=json.loads(sys.argv[1])
if not j.get("send"): sys.exit(0)
# 1日20通まで（11/13 ライトプラン 月5,000通）
today=datetime.date.today().isoformat(); n=0
try:
    for l in open(sys.argv[2]):
        if json.loads(l).get("day")==today: n+=1
except FileNotFoundError: pass
if n>=20: print("今日の上限"); sys.exit(0)   # 11/13 ライトプラン（月5,000通）にした＝8→20
import os
args=[os.path.expanduser("~/bin/friday-send"), j["text"]]
for lab,url in (j.get("links") or [])[:3]: args+=["--link",lab,url]
r=subprocess.run(args,capture_output=True,text=True)
open(sys.argv[2],"a").write(json.dumps({"day":today,"at":datetime.datetime.now().isoformat(timespec="minutes"),"text":j["text"],"result":r.stdout.strip()},ensure_ascii=False)+"\n")
PY
