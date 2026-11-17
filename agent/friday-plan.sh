#!/bin/zsh
# フライデーの時刻の段取り：今日の予定から「いつ・何を送るか」を決めて plan/<日付>.json に置く（Air・mini 両方から・Cloudflare /once で1回だけ）2026-10-31
# 送るのは friday-tick.py（5分ごと）。オーナー 10/31「時間ベースで先回り・ルートも添えて・疑似AGI」
export PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/bin
F=~/owner-kotoba/friday; mkdir -p $F/plan; LOG=$F/plan.log; DAY=$(date +%Y%m%d); SLOT=$(date +%H)
ME=$( [ -d /Users/owner ] && echo mini || echo air )
KEY=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/line/friday.json')))['agent_key'])")
RUN=$($HOME/bin/fcurl -s -m 15 -A friday-agent/1 -H "x-agent-key: $KEY" -H "x-agent: $ME" "https://friday-line.example.workers.dev/once?job=plan:$DAY:$SLOT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('run'))" 2>/dev/null)
[ "$RUN" = "True" ] || [ "$1" = "--force" ] || exit 0
echo "$(date '+%F %T') [$ME] start $SLOT" >> $LOG
cd ~ && perl -e 'alarm shift; exec @ARGV' 1500 ${CLAUDE_BIN:-claude} -p --model opus --permission-mode bypassPermissions < ~/bin/friday-plan-prompt.md > $F/plan/$DAY-$SLOT.out 2>>$LOG
J=$(grep -o 'FRIDAY_PLAN {.*}' $F/plan/$DAY-$SLOT.out | tail -1 | sed 's/^FRIDAY_PLAN //')
[ -z "$J" ] && { echo "$(date '+%F %T') [$ME] 計画が出んかった" >> $LOG; exit 1; }
python3 - "$J" "$F/plan/$DAY.json" <<'PY'
import sys,json,os
new=json.loads(sys.argv[1]).get("items",[]); p=sys.argv[2]
sys.path.insert(0,os.path.expanduser("~/bin")); import friday_planio as PIO   # 11/14 夜 鍵つきで書く
def _re(old):
    keep=[i for i in old["items"] if i.get("status") or i.get("src")]   # 送った・飛ばした物・メール/約束/場所から足した物は残す
    ids={i["id"] for i in keep}
    for i in new:
        if i["id"] in ids: i["id"]+="b"
        i["status"]=None; keep.append(i)
    return {"items":keep}
PIO.naosu(p,_re)
print(len(new))
PY
N=$(python3 -c "import json;print(sum(1 for i in json.load(open('$F/plan/$DAY.json'))['items'] if not i.get('status')))")
echo "$(date '+%F %T') [$ME] 予定の知らせ $N 件" >> $LOG
# もう片方にも置く（どっちが生きとっても送れるように）
OT=$( [ $ME = air ] && echo project-j-macmini || echo air ); scp -q $F/plan/$DAY.json $OT:owner-kotoba/friday/plan/ 2>>$LOG || true  # 11/02 両方向・11/09 Air オフでも失敗扱いにせん
