#!/bin/zsh
# 11/01 オーナー「今日は一日 Mac mini から・切り替えずに」＝期限まで Air の返事係を止めておく。期限が来たら Air を元に戻して自分も消える
UNTIL="${1:-2026-11-02 04:00}"
END=$(date -j -f "%Y-%m-%d %H:%M" "$UNTIL" +%s)
LOG=~/owner-kotoba/friday/mini-only.log
AIR=(ssh -o ConnectTimeout=5 -o BatchMode=yes -i ~/.ssh/id_ed25519_hermes_macbook_obsidian owner@YOUR_TAILSCALE_IP)
touch ~/owner-kotoba/friday/mini_only
echo "$(date '+%F %T') 開始（期限 $UNTIL）" >> $LOG
stopped=0
while [ $(date +%s) -lt $END ]; do
  if "${AIR[@]}" 'launchctl print gui/$(id -u)/com.owner.friday-agent >/dev/null 2>&1 && launchctl bootout gui/$(id -u)/com.owner.friday-agent && echo STOPPED; touch ~/.friday-mini-only' 2>/dev/null | grep -q STOPPED; then
    echo "$(date '+%F %T') Air がつながった→Air の返事係を止めた" >> $LOG; stopped=1
  fi
  sleep 60
done
# 期限：Air の返事係を戻す（Air がオフなら、つながるまで最大12時間待つ）
for i in {1..720}; do
  if "${AIR[@]}" 'rm -f ~/.friday-mini-only; launchctl print gui/$(id -u)/com.owner.friday-agent >/dev/null 2>&1 || launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.owner.friday-agent.plist; echo OK' 2>/dev/null | grep -q OK; then
    echo "$(date '+%F %T') 期限→Air の返事係を戻した" >> $LOG; break
  fi
  sleep 60
done
rm -f ~/owner-kotoba/friday/mini_only
launchctl bootout gui/$(id -u)/com.owner.friday-mini-only 2>/dev/null
