#!/bin/zsh
# 11/14 フライデーの耳を Google Drive へ（オーナー「言葉は全部コンテキストとして Drive に」）
# 文字（書き起こし・まとめ・やる事）は30分ごとに写す。声の実物は3日たったら Drive へ移して mini を軽く（同じ道＝drive-fetch で戻せる）
export PATH=$HOME/.local/bin:$HOME/bin:/opt/homebrew/bin:/usr/bin:/bin
S=$HOME/owner-kotoba/friday/mimi; R=kotoba-gdrive:mac-mini/owner-kotoba/friday/mimi; LOG=$S/drive.log
rclone copy $S $R --exclude 'raw/**' --exclude '*.lock' --transfers 4 --log-file $LOG --log-level NOTICE --stats 0
rclone move $S/raw $R/raw --min-age 3d --transfers 4 --log-file $LOG --log-level NOTICE --stats 0
find $S/raw -type d -empty -mindepth 1 -delete 2>/dev/null
echo "$(date '+%F %T') ok" >> $LOG
