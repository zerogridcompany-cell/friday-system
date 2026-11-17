#!/bin/zsh
# フライデーの毎晩の学び（2026-11-12〜）。引数なし＝昨日の会話。引数で日付 YYYY-MM-DD を渡すとその日。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/bin"
DAY=${1:-$(date -v-1d +%Y-%m-%d)}
SUN=no; [[ -z "$1" && $(date +%u) == 7 ]] && SUN=yes
F=$HOME/owner-kotoba/friday
[[ -f $F/会話/$DAY.md ]] || { echo "$(date '+%F %T') $DAY 会話なし"; exit 0; }
P=$(sed -e "s/{DAY}/$DAY/g" -e "s/{SUNDAY}/$SUN/g" $HOME/bin/friday-manabi-prompt.md)
CLAUDE=$HOME/.local/bin/claude; [[ -x $CLAUDE ]] || CLAUDE=claude
OUT=$(print -r -- "$P" | $CLAUDE -p --model opus --permission-mode bypassPermissions 2>&1 | tail -3)
echo "$(date '+%F %T') $DAY $OUT"
