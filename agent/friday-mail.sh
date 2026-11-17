#!/bin/zsh
# フライデーのメール見張り（Air と mini の launchd・15分ごと・Cloudflare /once で1回）2026-10-29
export PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/bin
F=~/owner-kotoba/friday; mkdir -p $F/mail; LOG=$F/mail.log
ME=$( [ -d /Users/owner ] && echo mini || echo air ); [ $ME = air ] && sleep 120  # 11/02 mini に先に枠を取らせる
SLOT=$(( $(date +%s) / 900 ))
KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/line/friday.json')))['agent_key'])")
RUN=$($HOME/bin/fcurl -s -m 15 -A friday-agent/1 -H "x-agent-key: $KEY" -H "x-agent: $ME" "https://friday-line.example.workers.dev/once?job=mail:$SLOT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('run'))" 2>/dev/null)
[ "$RUN" = "True" ] || exit 0
# 11/11 宿・旅行会社から相手が書いてきた連絡（忘れ物・質問）は AI の判断を通さず決まりで必ず送る（本人「絶対」）
[ $ME = mini ] && python3 $HOME/bin/friday-yado-mail.py >> $LOG 2>&1
# Air で即時の見張り（friday-mail-now）が生きとる間は、そっちに任せる（2回送らん）10/31
if [ $ME = air ] && pgrep -x Mail >/dev/null && [ $(( $(date +%s) - $(cat $F/mail/now_beat 2>/dev/null || echo 0) )) -lt 1800 ]; then exit 0; fi
# 見る範囲＝1つ前の15分の枠（after〜before）。枠ごとに1台だけが見る＝2台で重ならん
SINCE=$(( (SLOT-1)*900 )); UNTIL=$(( SLOT*900 ))
# 11/14 夜 失敗した枠は二度と見てへんかった（3日で288枠のうち24枠＝約8%が抜け）＝最後に見終えた時刻から見る（6時間より前には戻らん）
LAST=$(cat $F/mail/last_ok 2>/dev/null || echo 0)
(( LAST > 0 && LAST < SINCE && SINCE - LAST <= 21600 )) && SINCE=$LAST
touch $F/mail/sent_ids.txt; tail -60 $F/mail/sent_ids.txt > $F/mail/recent_ids.txt
sed -e "s#{SINCE}#$SINCE before:$UNTIL#" -e "s#{SENT}#$F/mail/recent_ids.txt#" ~/bin/friday-mail-prompt.md > $F/mail/prompt.md
cd ~ && perl -e 'alarm shift; exec @ARGV' 420 ${CLAUDE_BIN:-claude} -p --model opus --settings '{"disableAllHooks":true}' \
  --allowedTools "Read,mcp__claude_ai_Gmail__search_threads,mcp__claude_ai_Gmail__get_thread,mcp__claude_ai_Gmail__get_message,mcp__claude_ai_Google_Calendar__list_events,mcp__claude_ai_Google_Calendar__create_event" \
  < $F/mail/prompt.md > $F/mail/last.out 2>>$LOG
J=$(grep -o 'FRIDAY {.*}' $F/mail/last.out | tail -1 | sed 's/^FRIDAY //')
echo "$(date '+%F %T') [$ME] ${J:0:160}" >> $LOG
[ -z "$J" ] && exit 0
echo $UNTIL > $F/mail/last_ok   # ここまで見終えた
python3 - "$J" "$F" <<'PY'
import sys,json,subprocess,os,datetime
j=json.loads(sys.argv[1]); F=sys.argv[2]
if not j.get("send"): sys.exit(0)
ids=[i for i in j.get("ids") or []]
old=set(open(F+"/mail/sent_ids.txt").read().split())
if ids and all(i in old for i in ids): sys.exit(0)
# 1日の上限（LINE 無料枠 月200通）：メールは1日5通まで
today=datetime.date.today().isoformat(); cnt=os.path.join(F,"mail","count_"+today)
n=int(open(cnt).read()) if os.path.exists(cnt) else 0
isogi=bool(j.get("isogi"))   # 11/11 宿・便・旅行の相手からの連絡（忘れ物・質問・変更）は必ず届ける＝1日の上限も取っとき枠も越える
if n>=8 and not isogi: sys.exit(0)   # 11/14 本人「あげて」＝月5,000通に変えたので 2→8通（11/03 は月200通の頃の「1日2通」）
r=subprocess.run([os.path.expanduser("~/bin/friday-send"), j["text"]]+(["--isogi"] if isogi else []),capture_output=True,text=True)
open(F+"/mail.log","a").write(datetime.datetime.now().strftime("%F %T")+" send→ "+(r.stdout.strip() or r.stderr.strip())[:200]+"\n")
if "sent" in r.stdout or "次の返事で伝える" in r.stdout or "error 429" in r.stdout:
    open(cnt,"w").write(str(n+1))
    with open(F+"/mail/sent_ids.txt","a") as f: f.write("\n".join(ids)+"\n")
PY
