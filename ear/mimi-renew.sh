#!/bin/zsh
# フライデーの耳の入れ直し（無料の登録は7日で切れる・11/14 オーナー「これで様子見」）。毎日12:05に見て、前の入れ直しから6日たっとったら入れ直す。
export PATH=$HOME/.local/bin:$HOME/bin:/opt/homebrew/bin:/usr/bin:/bin
D=$HOME/work/friday-mimi-ios; S=$D/last_install; LOG=$HOME/owner-kotoba/friday/mimi/renew.log
last=$(cat $S 2>/dev/null || echo 0); now=$(date +%s)
# 11/14 10分ごとに見る：期限（6日）か、新しい版の入れ直し待ち（pending）があって、iPhone が mini から見えとる時だけ（外出中は見えん）
# 11/14 持ち歩き（18 Pro Max）と家（15 Pro）の両方。入れる必要があって・mini から見えとる方を1台
h=$(date +%H); (( 10#$h >= 9 && 10#$h < 23 )) || exit 0
asked=$(cat $D/asked 2>/dev/null || echo 0); (( now - asked < 2*3600 )) && exit 0
DEVS=$(xcrun devicectl list devices 2>/dev/null)
DEV=""
for c in "YOUR_IPHONE_UDID|iPhone 18 Pro Max（持ち歩き）|pending|last_install"; do
  id=${c%%|*}; r=${c#*|}; na=${r%%|*}; r=${r#*|}; pf=${r%%|*}; ls=${r#*|}
  l=$(cat $D/$ls 2>/dev/null || echo 0)
  { [[ -f $D/$pf ]] || (( now - l >= 6*86400 )); } || continue
  print -r -- "$DEVS" | grep $id | grep -qE "available|connected" || continue
  # 家の 15 Pro はオーナー様が家に居る時（持ち歩きも mini から見える時）だけ＝外出中にロック解除を頼まん
  [[ $id == 00008130* ]] && { print -r -- "$DEVS" | grep YOUR_IPHONE_UDID | grep -qE "available|connected" || continue; }
  DEV=$id; NA=$na; PF=$D/$pf; LS=$D/$ls; break
done
[[ -n $DEV ]] || exit 0
python3 ~/bin/mimi_basho.py --ie || exit 0   # 11/14 夜 OwnTracks の最後の点が家から300m以内の時だけ頼む（devicectl の「見える」は外出中も残る＝20:41 に電車の中へ頼みが出かけた）
[[ -f /tmp/mimi-renew.running ]] && exit 0; touch /tmp/mimi-renew.running; echo $now > $D/asked
~/bin/friday-send "オーナー様、フライデーの耳を${NA}に入れます。お手すきの時にその iPhone のロックを外し、2〜3分そのままにしてください（20分お待ちします）。" --force >/dev/null
~/bin/gamen take mimi-renew; osascript -e 'tell application "iPhone Mirroring" to quit'; sleep 3
rm -f $D/b.log; osascript -e "tell application \"Terminal\" to do script \"$D/b.sh $DEV; exit\"" >/dev/null
for i in {1..150}; do grep -q DONE $D/b.log 2>/dev/null && break; sleep 10; done
if grep -q "INSTALL=0" $D/b.log; then
  date +%s > $LS; rm -f $PF; echo "$(date '+%F %T') 入れ直した $NA" >> $LOG
  ~/bin/friday-send "オーナー様、${NA}にフライデーの耳を入れました。次の期限は7日後です。初めての時は 設定→一般→VPNとデバイス管理 で開発元を「信頼」し、アプリを開いて「押すと聞く」を押してください（マイクと位置は「常に」）。" --force >/dev/null
else
  echo "$(date '+%F %T') だめ $(grep -m1 -E 'error' $D/b.log | cut -c1-150)" >> $LOG
  ~/bin/friday-send "オーナー様、フライデーの耳の入れ直しができませんでした（ロックが外れなかったようです）。2時間後にもう一度お願いいたします。" --force >/dev/null
fi
~/bin/gamen done mimi-renew; pgrep -x "iPhone Mirroring" >/dev/null || open -g -a "iPhone Mirroring"
rm -f /tmp/mimi-renew.running
