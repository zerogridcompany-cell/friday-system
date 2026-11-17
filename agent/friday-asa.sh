#!/bin/zsh
# フライデーの朝のまとめ（Air launchd 7:00・mini launchd 7:12 の両方から。Cloudflare /once で1日1回だけ）2026-10-29
export PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/bin
F=~/owner-kotoba/friday; mkdir -p $F/asa; LOG=$F/asa.log; DAY=$(date +%Y%m%d)
ME=$( [ -d /Users/owner ] && echo mini || echo air )
KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/line/friday.json')))['agent_key'])")
RUN=$($HOME/bin/fcurl -s -m 15 -A friday-agent/1 -H "x-agent-key: $KEY" -H "x-agent: $ME" "https://friday-line.example.workers.dev/once?job=asa:$DAY" | python3 -c "import sys,json;print(json.load(sys.stdin).get('run'))" 2>/dev/null)
[ "$RUN" = "True" ] || exit 0
echo "$(date '+%F %T') [$ME] start" >> $LOG
cd ~ && ${CLAUDE_BIN:-claude} -p --model opus --permission-mode bypassPermissions < ~/bin/friday-asa-prompt.md > $F/asa/$DAY.out 2>>$LOG
J=$(grep -o 'FRIDAY {.*}' $F/asa/$DAY.out | tail -1 | sed 's/^FRIDAY //')
[ -z "$J" ] && { ~/bin/friday-send "おはよう。朝のまとめを作れんかった（$ME）。パソコンの記録 ~/owner-kotoba/friday/asa.log を見てな"; exit 1; }
python3 - "$J" <<'PY'
import sys,json,subprocess,os
j=json.loads(sys.argv[1])
try: w=subprocess.run(["python3",os.path.expanduser("~/bin/friday-quota.py")],capture_output=True,text=True,timeout=30).stdout.strip()
except Exception: w=""
a=[os.path.expanduser("~/bin/friday-send"), j["text"]+("\n\n"+w if w else "")]
for l,u in (j.get("links") or [])[:3]: a+=["--link",l,u]
print(subprocess.run(a,capture_output=True,text=True).stdout)
PY
echo "$(date '+%F %T') [$ME] sent" >> $LOG
