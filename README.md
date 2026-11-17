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

## 動かすのに要る物（自分の物に替える）

- Claude Code（`claude` コマンド・ログイン済み）
- LINE Messaging API のチャネル（トークンは Worker の secret に）
- Cloudflare Workers ＋ KV（`worker/wrangler.toml` の `YOUR_KV_NAMESPACE_ID`）
- macOS（launchd）・Python 3・mlx-whisper・silero-vad
- Tailscale（iPhone → Mac の声の道）
- `/Users/owner`・`com.owner.*`・`owner-kotoba`（記録の置き場）を自分の環境の名前に
