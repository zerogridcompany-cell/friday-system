# Friday — LINE で動く専属の秘書 bot

LINE で頼むと、調べ物・予約・メールや予定の確認・画面操作までやる秘書。
頭は Claude Code（`claude -p`・全部 Opus）。Mac mini 1台で常時動かす。

このリポは仕組みの共有用。持ち主の名前・連絡先・お金・予定などの私事は伏せてある
（`オーナー`・`〈人〉`・`〈店〉`・`owner@example.com`・`000-0000-0000` などは置き換えた跡）。
鍵・トークンは入っていない。そのままでは動かない（下の「動かすのに要る物」を自分の物に替える）。

## 全体の流れ

```
LINE ──▶ Cloudflare Worker（worker/）──▶ キュー（KV）
                                           │  取りに行く
iPhone アプリ（ios/）──声30秒ずつ──▶ 耳（ear/）──頼み──┘
                                           ▼
                                  返事の係（agent/friday-agent.py）
                                  claude -p（Opus）＋道具
                                           │
                                  検算 → 門（同じミス・数字・長さ）
                                           ▼
                                         LINE へ返事
```

## フォルダ

| フォルダ | 中身 |
|---|---|
| `worker/` | LINE の Webhook を受ける Cloudflare Worker。頼みをキューに積む・返事を送る・二重送信を止める鍵（Durable Object） |
| `agent/` | 返事の本体と、時間で回る係 |
| `ear/` | 耳。声を文字にして、頼みを拾う |
| `ios/` | 耳の iPhone アプリ（FridayMimi）。声を30秒ずつ Mac へ送る |
| `launchd/` | 常駐・定時実行の設定（macOS launchd） |
| `setup/` | 置き方（install.sh）と、持ち主の事を聞いて埋める道具（friday-kikitori・質問38個・master-add） |

## agent/ の主な物

| ファイル | 役目 |
|---|---|
| `friday-agent.py` | 返事の本体。キューから頼みを取り、`claude -p` に渡し、検算と門を通して LINE に返す |
| `friday-prompt.md` | フライデーの人格と決まり（執事の日本語・外に出す行為は本人の言葉の1回だけ 等） |
| `friday_fast.py` `friday_sokutou.py` | すぐ返せる頼みの近道 |
| `friday_onaji.py` | 同じミスを繰り返さん門 |
| `friday_shougou.py` | 返事の中身を記録と照らす |
| `friday-tick.py` `friday-watch.sh` | 定期の見回り |
| `friday-mail.sh` `friday-asa.sh` `friday-plan.sh` | メールの知らせ・朝の報告・予定 |
| `friday-bin-mihari.py` `friday-ichi-mihari.py` | 飛行機の便・位置の見張り |
| `friday-yakusoku.py` | 「あとでやります」と言うた約束を落とさん |
| `friday-manabi.sh` | 毎晩、その日の会話から学び直す |
| `friday-sakimawari.py` | 毎晩、「記録にない」と止まった返事を拾って通し直す |
| `friday-naoshi.sh` | 毎晩、まだ止まる物を直し係が直す |
| `friday-ana-mihari.py` `friday-mikake-test.py` | 決まりの抜け・見かけの試験 |
| `fa-idle` | 仕事が走ってない時だけ本体を入れ替える（途中の仕事を切らん） |

## ear/ の主な物

| ファイル | 役目 |
|---|---|
| `mimi-server.py` | iPhone からの声を受ける口（Tailscale の中だけで待つ） |
| `mimi_kiku.py` | 聞く本体。声の有無の門（Silero VAD）→声の所だけ切り出し→Whisper（mlx）で文字に。区切りごとに何語か測り、英語は英語で書く |
| `mimi-apple-kiku.swift` | Mac 内蔵の聞き取り（日本語）。Whisper の読みと合わせる |
| `mimi_filter.py` | 幻聴・雑音・動画の音を落とす。名前で呼ばれたかを見る |
| `mimi-watch.py` | 聞こえた言葉から「頼み」を拾って、返すか・動くかを決める |
| `mimi-matome.py` | 会話ごとのまとめ。聞き違いを Opus が直して、元の言葉と並べて残す |
| `mimi-shiken.py` | 耳の試験（正解つきの例を全部通す） |

## 設計で大事にした事

- **全部同じ賢いモデルで**：返事・検算・縮め・耳の読みを軽いモデルに分けたら、賢い返事を軽いモデルが書き直して質が落ちた。全部 Opus に揃えた
- **門で止める**：注意書きを足すより、送る前に機械で確かめる（同じミス・数字の出所・長さ・二重送信）
- **「無い」と言う前に探す**：記録に無い世の中の事は検索してから答える
- **外に出す行為は本人の言葉の1回だけ**：送信・購入・予約・公開
- **毎晩自分で直す**：止まった返事・ミスを夜のうちに拾って通し直し、直らん物だけ赤として残す
- **試験を先に**：道具を直したら試験を全部通してから入れ替える

## 持ち主の事は「聞いて」埋める（setup/）

フライデーは持ち主の事（呼び名・住んでいる街・好み・決まり・今進めている事…）を知っていて初めて賢く動く。
このリポには前の持ち主の情報は入っていない。代わりに **穴（ノード）つきの記録の木** があり、新しい持ち主に聞いて埋めていく。

```
owner-kotoba/master/
├── MASTER.md        幹＝30秒で分かる持ち主（呼び名・口調・街・時間帯・仕事・目標）
└── 枝/
    ├── 01_人.md         家族・大事な人・触れない人・住所（鍵へ）
    ├── 02_話し方.md     返事の長さ・音声入力で化ける言葉・急ぎの合図
    ├── 03_好みと目標.md 好き・苦手・予約と旅の好み
    ├── 04_仕事と会社.md 働き方・よく出る相手・仕事の時間
    ├── 05_道具とスキル.md 予定・メール・移動・よく使うサービス
    ├── 06_今やっとる事.md 進めている事と期限
    ├── 07_決まりとミス.md やってはいけない事・朝の報告・嫌な事
    └── 08_お金と手続き.md カード（番号は書かない）・定期の支払い・期限
```

穴は1行ずつ `- [ ] 00.yobina｜呼び名：（未記入）` の形。質問は全部で38個（`setup/shitsumon.json`・★7個が必須）。

1. `setup/install.sh` ＝コードを `~/bin` に写して、記録の木を穴つきで作る
2. `friday-kikitori ask` ＝★の質問にターミナルで答える（約5分）
3. 残りの穴は **フライデーが LINE で聞く**。毎回読む脳（脳.md）に「まだ知らん事」と次の質問が入り、返事の最後に1日3問まで、1問ずつ聞く。頼みに要る事が穴なら、「記録にありません」で止まらずにその場で聞く
4. 答えは `friday-kikitori fill` で木に書き込まれる。住所・電話などは鍵（キーチェーン）にだけ入り、記録には鍵の名前だけ残る。「言いたくない」と言えばもう聞かない
5. 聞かれていない事も、会話で本人がはっきり言った事は毎晩の学び（friday-manabi.sh）が拾って、穴を埋めるか枝に足す（`master-add`）

今の埋まり具合は `friday-kikitori status`。

## 動かすのに要る物（自分の物に替える）

- Claude Code（`claude` コマンド・ログイン済み）
- LINE Messaging API のチャネル（トークンは Worker の secret に）
- Cloudflare Workers ＋ KV（`worker/wrangler.toml` の `YOUR_KV_NAMESPACE_ID`）
- macOS（launchd）・Python 3・mlx-whisper・silero-vad
- Tailscale（iPhone → Mac の声の道）
- `/Users/owner`・`com.owner.*`・`owner-kotoba`（記録の置き場）を自分の環境の名前に
