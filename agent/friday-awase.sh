#!/bin/zsh
# フライデーの記録を Air⇔mini で合わせる（launchd com.owner.friday-awase）
# 動く時＝10分ごと＋ネットが変わった瞬間（WatchPaths resolv.conf＝Wi-Fi に戻った時。オーナー 11/02「戻った段階ですぐ mini の情報を引き継ぐ」）
# ネット復帰の直後は Tailscale がまだ寝とる事があるので、届かん時は 15 秒おきに 4 回まで待つ
export PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
LOG="$HOME/owner-kotoba/friday/awase.log"
for i in 1 2 3 4; do
  out=$(python3 "$HOME/bin/friday-awase.py" 2>&1)
  if [[ "$out" == もらった* ]]; then exit 0; fi
  [[ $i -lt 4 ]] && sleep 15
done
echo "$(date '+%F %T') [sh] 4回とも届かんかった: ${out:0:120}" >> "$LOG"
