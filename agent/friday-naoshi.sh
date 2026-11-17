#!/bin/zsh
# フライデーの毎晩の直し係（11/14 オーナー「学習・修正していく機能をずっと取り付けて」）。学び（4:10）の後の 4:45。
# 学びが出した「門の案」から、今もくり返しとる物を最大3つコードで直す。壊したら戻す。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/bin"
DAY=${1:-$(date -v-1d +%Y-%m-%d)}; STAMP=$(date +%Y%m%d)
F=$HOME/owner-kotoba/friday; mkdir -p $F/naoshi; touch $F/naoshi/sumi.md
[[ -f $F/manabi/mon_an.md ]] || { echo "$(date '+%F %T') 門の案なし"; exit 0; }
P=$(sed -e "s/{DAY}/$DAY/g" -e "s/{STAMP}/$STAMP/g" $HOME/bin/friday-naoshi-prompt.md)
CLAUDE=$HOME/.local/bin/claude; [[ -x $CLAUDE ]] || CLAUDE=claude
OUT=$(print -r -- "$P" | $CLAUDE -p --model opus --permission-mode bypassPermissions 2>&1 | grep "NAOSHI" | tail -1)
echo "$(date '+%F %T') $DAY ${OUT:-（結果の行なし）}" >> $F/naoshi/run.log
