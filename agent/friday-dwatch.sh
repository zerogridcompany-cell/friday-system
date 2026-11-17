#!/bin/zsh
# フライデーの Discord 見張り（mini launchd com.owner.friday-dwatch・5分ごと）
# 11/01 オーナー「今後 Discord も LINE と一緒に確認して。サーバーAのメインと、〈会社〉のメインチャット」
# mini の Discord アプリ（CDP 9339）で サーバーA・〈会社〉 の main-chat の新しい発言を読む→Claude（Opus）が知らせるか決める→フライデーで送る
# LINE の見張り（friday-watch.sh）と同じ prompt・同じ sent.jsonl・同じ1日8通の枠
export PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$HOME/.local/bin:$HOME/bin
F=~/owner-kotoba/friday; LOG=$F/dwatch.log; LOCK=$F/dwatch.lock
[ -d /Users/owner ] || exit 0   # Discord アプリがあるのは mini だけ
[ -f $LOCK ] && [ $(( $(date +%s) - $(stat -f %m $LOCK) )) -lt 600 ] && exit 0
touch $LOCK; trap 'rm -f $LOCK' EXIT
TS=$(date +%Y%m%d_%H%M); W=$F/runs/d_$TS; mkdir -p $W
~/bin/friday-discord.py $W > $W/changed.txt 2>>$LOG
if [ ! -s $W/changed.txt ]; then rm -rf $W; exit 0; fi
IN=$W/input.md; : > $IN
for d in $W/*(N/); do echo "\n## ${d:t}" >> $IN; cut -f4 $d/0.txt >> $IN; done
tail -20 $F/sent.jsonl > $W/sent.txt 2>/dev/null; touch $W/sent.txt
sed -e "s#{INPUT}#$IN#" -e "s#{SENT}#$W/sent.txt#" ~/bin/friday-prompt.md > $W/prompt.md
cd $W && ${CLAUDE_BIN:-claude} -p --model opus --permission-mode bypassPermissions < $W/prompt.md > $W/result.txt 2>>$LOG
J=$(grep -o 'FRIDAY {.*}' $W/result.txt | tail -1 | sed 's/^FRIDAY //')
echo "$(date '+%F %T') Discord $(grep -c . $W/changed.txt)か所 → ${J:0:200}" >> $LOG
[ -z "$J" ] && exit 0
python3 - "$J" "$F/sent.jsonl" <<'PY'
import sys,json,subprocess,datetime,os
j=json.loads(sys.argv[1])
if not j.get("send"): sys.exit(0)
today=datetime.date.today().isoformat(); n=0
try:
    for l in open(sys.argv[2]):
        if json.loads(l).get("day")==today: n+=1
except FileNotFoundError: pass
if n>=8: print("今日の上限"); sys.exit(0)
args=[os.path.expanduser("~/bin/friday-send"), j["text"]]
for lab,url in (j.get("links") or [])[:3]: args+=["--link",lab,url]
r=subprocess.run(args,capture_output=True,text=True)
open(sys.argv[2],"a").write(json.dumps({"day":today,"at":datetime.datetime.now().isoformat(timespec="minutes"),"text":j["text"],"result":r.stdout.strip(),"from":"discord"},ensure_ascii=False)+"\n")
PY
