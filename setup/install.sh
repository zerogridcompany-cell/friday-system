#!/bin/zsh
# フライデーを自分の Mac に置く（コードを ~/bin へ写して、記録の木を穴つきで作る）。鍵・LINE の設定は README の「動かすのに要る物」
set -e
D=${0:A:h}/..
mkdir -p ~/bin
cp $D/agent/* $D/ear/* ~/bin/
cp $D/setup/friday-kikitori.py ~/bin/friday-kikitori
cp $D/setup/shitsumon.json ~/bin/friday-shitsumon.json
cp $D/setup/master-add ~/bin/master-add
chmod +x ~/bin/friday* ~/bin/mimi* ~/bin/master-add ~/bin/fa-idle 2>/dev/null || true
~/bin/friday-kikitori init
echo
echo "次：~/bin/friday-kikitori ask で、★の質問（約5分）に答える。残りはフライデーが LINE で少しずつ聞く"
