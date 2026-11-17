"""耳の書き起こしの門（幻聴・〈パートナー〉さんの話・くり返し）。mimi-server が使う。試験 mimi-shiken.py も同じ物を呼ぶ＝本番と試験で門がずれん。
線を変える時は、必ず mimi-shiken.py を回して、録ってある本物の声（shiken/）が全部通るのを確かめる。"""
import re
BAD = re.compile(r"^(ご視聴ありがとうございました|ありがとうございました|字幕.*|Thank you|you|音楽|拍手|笑|♪.*|[\d,、.\s]*|次回もお楽しみに|チャンネル登録.*|最後までご視聴.*)$")
# whisper が静けさ・雑音から作りがちな決まり文句。その句だけの区切りで、自信の点が高くない時に捨てる
# （11/14 空港で「おやすみなさい」が -0.54・-0.49 で通った。静かな部屋で決めた -0.6 の線は外では合わん）
KIMARI = re.compile(r"^(おやすみなさい|お疲れ様でした|それではまた|バイバイ|じゃあね|音声|エンディング|はい)$")
PARTNER = re.compile(r"〈パートナー〉|〈パートナー〉|〈パートナー〉|〈パートナー〉|〈パートナー〉")
# 11/15 耳の原因調べ（genin_20261115.md）：書き起こしで「フライデー」が「プライで」「フライで」「フライデン」「フライディ」「フライダー」に化ける。
# 化けた名前を機械で拾う（先回りの係・受け口・門が同じ物を使う）。フライド（ポテト）・プライド・プライベートは拾わん
NAME = re.compile(r"[フプ]ライ(?:ディー?|デー?ン?|ダー|[エレテ]ー|デイ)|[フプ]ライで(?![きすしさ])|フライド(?=は(?:どう|何|聞)|[、,]|さん)|ふらいでー|[Ff]riday")   # 11/15 21:48「フライドはどう思う?」
# 11/15 22:01 テレビの音と混ざって「フライエーとメターズ見て、今日いくらスペンドしてるか見てほしい」＝名前が「フライエー」に化けて広告の話として捨てとった（本人「返答ない」）
# 22:03 「何でぇ聞こえてる? メタンス調べてよ」＝「聞こえてる？」の直後の頼みはフライデーへの呼びかけ
KIKOE = re.compile(r"聞こえて(?:る|ます|い)[^。]{0,3}[？?]?.{0,40}?(?:調べ|教え|見て|探し|確認し|やっ)て")
def yobu(t):
    """名前（化けた物も）で呼ばれとるか"""
    return bool(NAME.search(t or "") or KIKOE.search(t or ""))
# 11/16 本人「ピコって鳴るのは直せないのか」＝Mac に向かって「今はフライデーに話してない」「フライデーとの会話って」と話題にしただけで iPhone が鳴り、聞き返しの LINE も出た
# 名前のすぐ後ろが「に話し・に向かって・との・が・の・を・以外」＝話題にしとるだけ。「フライデー、」「フライデー 調べて」「フライデーに聞きたい」「フライデーはどう思う」＝呼びかけ
HANASHI = re.compile(r"(?:さん)?(?:に(?:は|も)?(?:向かって|向けて|話し|言っ|かけ|問いかけ|関し|つい|対し)|との|と(?:か|は|話|会話|喋)|が|の(?![、,])|を|って(?:いう|言う|の)|以外|じゃな|では?な|側|自体|へ)")
def namae_dake(t):
    """名前しか入ってない文か（11/16「フライデー、 フライデー、 フライデー、」＝雑音に、書き起こしへ教えた名前がそのまま出た物が1日で約20本）"""
    s = seiki(t)
    return "フライデー" in s and not re.sub(r"フライデー|[、。,.!?！？\s]", "", s)
def yobikake(t):
    """名前で「呼びかけ」とるか（話題にしただけは False）"""
    if KIKOE.search(t or ""): return True
    s = seiki(t)
    return any(not HANASHI.match(s[m.end():m.end() + 10]) for m in re.finditer("フライデー", s))
def seiki(t):
    """化けた名前を「フライデー」に直した文（係に渡す時に使う）"""
    return re.sub(r"[フプ]ライで(?![きすしさ])", "フライデー、", re.sub(r"[フプ]ライ(?:ディー?|デー?ン?|ダー|[エレテ]ー|デイ)|フライド(?=は(?:どう|何|聞)|[、,]|さん)|ふらいでー|[Ff]riday", "フライデー", t or ""))
# 本人の頼みの言葉（「〜してほしい」「調べて」「登録しといて」等）
TANOMI = re.compile(r"[てで](?:ほし[いく]|欲し[いく]|くれ|ください|もらえ|ちょうだい|おいて)|(?:調べ|教え|探し|登録し|確認し|予約し|追加し|頼ん)て|(?:止め|消し|入れ|送っ|呼ん|開い|進め)て(?:[。？?!！ ]|$)|しといて|入れといて|やっといて|聞こえて(?:る|い)|お願い(?:し|で|ね)|追加で|追加して|やって(?:よ|ね|[。！!？? ]|$)|見て(?:よ|ね)|[さっ]といて|(?:記録|メモ|録音)(?:し|して|っ)?と(?:い|っ)?て|覚えといて")   # 11/15 22:50「これは全部記録さっといて」（しといて の化け）   # 11/15 15:21「遂行だけ目指してやって」
def tanomi(t):
    return bool(TANOMI.search(t or ""))
# 11/15 夜 1日20通の上限の後、頼みの言葉が無い「質問」を中身を見ずに捨てとった（21:06「俺の家の近くだったらどこで」・21:42「電車でどうやったら簡単に行けんか」・21:48「フライデーはどう思う?」）
TOI = re.compile(r"[？?]|どこ|いつ|いくら|何時|何分|何円|どう(?:やっ|し|す|な|思)|どれ|なんで|何が|何を|何で|っけ|ないかな|あるかな")
# 11/15 夜 声紋の印（受け口が rec["hon"] に本人らしさを入れる）。iPhone の区切りだけ見分ける（家の EarPods はマイクが違って本人でも低い）
HON = 0.30
def koe_shirushi(r):
    h = r.get("hon")
    if h is None or not str(r.get("dev", "")).startswith("iPhone"): return ""
    return "👤" if h >= HON else ("🔈" if h < 0.2 else "")
def toi(t):
    """質問の形か（上限の後でも係に見せる）"""
    return bool(TOI.search(t or ""))
# 短くて自信の低い段でも、名前か頼みの言葉が入っとる物は捨てん（11/15「登録して」-0.64・「フライディありがとう」-0.77・「フライディー」-0.70 が消えとった）
KEEP = re.compile(NAME.pattern + r"|(?:調べ|教え|探し|登録し|確認し|追加し|止め|消し|入れ|送っ|呼ん)て")
DERA = re.compile(r"[\u0400-\u04FF\uAC00-\uD7AF]")
def _n(t): return t.strip().rstrip("。.！!？? 　")
def bad(t): return bool(BAD.match(_n(t)))
def seg_ok(s):
    # 11/17 本人「全く言ってない事ばかり記録に残る」＝でたらめ（外国語の動画・音楽）は同じ音の繰り返しで圧縮率が 7.55・本物の声は 1.76 まで（whisper の既定の線 2.4）
    if (s.get("compression_ratio") or 0) > 2.4: return False
    t = s.get("text", "").strip(); lp = s.get("avg_logprob", 0)
    if s.get("no_speech_prob", 0) >= 0.6 or bad(t): return False
    # 11/16 動画の音だけの区切りに、でたらめな外国語（「есто 출발」-3.55・「日本火 に取 Whatever drauf」）が出る＝キリル文字・ハングルの段、自信が -1.0 未満で英字4字以上が混ざる段は捨てる
    if DERA.search(t) or (lp < -1.0 and re.search(r"[A-Za-z]{4,}", t) and not KEEP.search(t)): return False
    if KIMARI.match(_n(t)) and lp < -0.3: return False
    if lp < -0.6 and len(t) <= 12:
        return bool(KEEP.search(t)) and lp >= -1.0
    return True
def moji(segs):
    """whisper の segments → 残す文字（空なら捨てる）"""
    txt = " ".join(s["text"].strip() for s in segs if seg_ok(s))
    ws = txt.split()
    if len(ws) >= 4 and len(set(ws)) <= max(1, len(ws) // 4): txt = ""      # 同じ句ばかり（「バターを作る」×13）
    txt = re.sub(r"(.{2,20}?)(?:\s*\1){3,}", r"\1", txt)
    if PARTNER.search(txt): txt = "（〈パートナー〉さんの話＝伏せた）"
    return txt

# 11/17 本人「お金をかけずに、俺らのプロダクトとして強くしたい」＝Mac 内蔵の聞き取り（Apple SpeechAnalyzer・ただ・1本 0.1秒）が中身は一番正確（本人だけの60本：Scribe とのずれ 13.6%・今の Whisper turbo 18.6%）。
# 弱みは名前（「フライデー」を「ぐらいで」「ライで」「裏で」と書く）＝名前は Whisper（辞書つき）が強い。2本を合わせる：ずれ 13.5%・呼びかけ 12/12本（Whisper だけ 11・Apple だけ 8）。測り＝mimi/wakeru/mado/bench.json
def awase(ap, wh):
    """Apple の読み（中身）＋Whisper の読み（名前）を1本に。Whisper が頭で名前を呼んどって Apple の頭に名前が無い時だけ、Apple の頭の化けを名前に替える"""
    ap = (ap or "").strip(); wh = (wh or "").strip()
    if not ap: return wh
    ws = seiki(wh); m = re.match(r"^.{0,3}?フライデー[、,\s]*", ws)
    if not m or "フライデー" in seiki(ap)[:10]: return ap
    ato = re.sub(r"[\s、。,.]", "", ws[m.end():])[:2]
    i = ap.find(ato) if len(ato) == 2 else -1
    if i < 0 and ato: i = ap.find(ato[0])
    return "フライデー、" + (ap[i:] if 0 <= i <= 8 else ap)
