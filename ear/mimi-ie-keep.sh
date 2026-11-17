#!/bin/zsh
# 家の耳の見張り（launchd・1分ごと）：録る係が動いてへんかったら画面の Terminal で起こす（マイクの許可は Terminal にある）
pgrep -f "mimi-ie-rec.py" >/dev/null && exit 0
[[ -f $HOME/owner-kotoba/friday/mimi/ie_off ]] && exit 0   # 止めたい時はこのファイルを置く
S='tell application "Terminal" to do script "python3 ~/bin/mimi-ie-rec.py; exit"'
osascript -e "$S" >/dev/null 2>&1
sleep 3; pgrep -f "mimi-ie-rec.py" >/dev/null && exit 0
# launchd からは直に動かせん時がある（iph と同じ逃げ道）
ssh -i $HOME/.ssh/id_ed25519_self -o BatchMode=yes localhost "osascript -e '$S'" >/dev/null 2>&1
