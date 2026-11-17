"""1つの仕事に1人の門（11/14 オーナー「LINE の中でフライデーの人格が2つある。今これで進めとるのに、新しいやり方の提案・同じタスクを新しく始めてます、が来る。一貫して1タスクに1人」）
先回りの係（plan・見張り・耳・まとめ 等）が friday-send で送る前に、
今オーナー様と返事係がやっとる仕事・直近3時間の会話と照らす。同じ仕事の別案・やり直し・やってない事の「いたしました」は送らん。"""
import os, re, json, time, datetime, subprocess
F = os.path.expanduser("~/owner-kotoba/friday")
LOG = F + "/hitori.log"
def log(s):
    with open(LOG, "a") as f: f.write(f"{datetime.datetime.now():%m-%d %H:%M:%S} {s}\n")

def running_jobs():
    """agent.log の「取った」で「返した」がまだ無い物＝返事係が今やっとる仕事"""
    try: lines = open(F + "/agent.log", encoding="utf-8").read().splitlines()[-600:]
    except Exception: return []
    tor, ret = {}, set()
    for l in lines:
        m = re.search(r"取った (\S+) 「(.*?)」", l)
        if m: tor[m.group(1)] = l[:16] + " " + m.group(2)
        m = re.search(r"返した (\S+)", l)
        if m: ret.add(m.group(1))
    cut = (datetime.datetime.now() - datetime.timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M")
    return [v for k, v in tor.items() if k not in ret and v[:16] >= cut]

def recent_talk(hours=3):
    now = datetime.datetime.now(); out = []
    for d in sorted({now.strftime("%Y-%m-%d"), (now - datetime.timedelta(hours=hours)).strftime("%Y-%m-%d")}):
        try: t = open(f"{F}/会話/{d}.md", encoding="utf-8").read()
        except Exception: continue
        for blk in re.split(r"\n(?=### )", t):
            m = re.match(r"### (\d\d):(\d\d)", blk)
            if not m: continue
            at = datetime.datetime.strptime(f"{d} {m.group(1)}:{m.group(2)}", "%Y-%m-%d %H:%M")
            if now - at <= datetime.timedelta(hours=hours): out.append(blk[:900])
    return "\n".join(out)[-9000:]

P = """あなたはフライデー（オーナー様専属の LINE 執事 AI）の「1つの仕事に1人」の門。
フライデーには返事係（オーナー様と LINE で話して仕事を進める本体）と、先回りの係（予定・見張り・耳）がいる。
オーナー様の訴え：「今これで進めとるのに、別の係から新しいやり方の提案や、同じ仕事をまた新しく始めます、が来る。人格が2つあるみたい。1つの仕事に1人にして」

今、返事係がやっとる仕事:
{jobs}

直近3時間のオーナー様と返事係の会話:
{talk}

{koe}先回りの係が今送ろうとしとる文:
{text}

判定：
- DROP＝この文が、上の会話や今やっとる仕事と同じ件について、①別のやり方・やり直し・新しく始める提案 ②もう話した事のくり返し ③返事係が決めた・進めとる事と食い違う案 ④誰もやってない事を「いたしました／手配しました／準備しました」と言う、のどれか。
- 🔴フライデーの耳は iPhone のマイクの声を全部文字にして残しとる（~/owner-kotoba/friday/mimi/）。「記録しております」「会話は残しております」は本当にやっとる事＝④に当たらん（11/15 23:01「会話記録しといて」への返事を④で止めて本人「全然ダメ」）。
- SEND＝会話に出てない新しい件、またはその件の新しい事実（新しいメールや連絡が届いた・時刻が迫った・状況が変わった）を、返事係の進め方に沿って知らせるだけの文。
- 🔴「オーナー様が今、声に出した言葉」がある時：それはオーナー様が今フライデーに向けて口で聞いた・頼んだ事。その質問・頼みに答える文は SEND（声で聞かれたのに返事が無いのが一番困る）。DROP にするのは、直近の会話でまったく同じ質問にもう答えていて、文に新しい中身が1つも無い時と、④（やってない事を「いたしました」）の時だけ。同じ件でも、聞かれた事が違えば（乗り場の番号は答え済み→今度は「そこまで何分」）SEND。
最後の1行だけ：HITORI SEND か HITORI DROP と、理由を20字で"""

def mon(text):
    """送ってええなら None、止めるなら理由"""
    jobs = running_jobs(); talk = recent_talk()
    if not jobs and not talk.strip(): return None
    claude = os.path.expanduser("~/.local/bin/claude")
    try:
        # 11/14 夜 速く：決まりを読まん軽い起動（判定に要る物は全部この指示文の中）
        KEI = os.path.expanduser("~/friday-work/kei"); kei = os.path.isdir(KEI) and not os.path.exists(F + "/kei_off")
        r = subprocess.run([claude, "-p", "--model", "opus", "--settings", '{"disableAllHooks":true}'] + (["--setting-sources", "project"] if kei else []),
                           input=P.format(jobs="\n".join(jobs) or "（なし）", talk=talk or "（なし）", text=text[:1500],
                                          koe=("オーナー様が今、声に出した言葉（耳が拾った物・聞き間違いを含む）:\n" + os.environ["FRIDAY_KOE"][:1200] + "\n\n") if os.environ.get("FRIDAY_KOE") else ""),
                           text=True, capture_output=True, timeout=60, cwd=KEI if kei else None,
                           env={**os.environ, **({"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"} if kei else {})})
        m = re.findall(r"HITORI (SEND|DROP)\s*(.*)", r.stdout)
    except Exception as e:
        log(f"判定できず（送る）{e}"); return None
    if not m: log("判定の形が違う（送る）"); return None
    v, why = m[-1]
    log(f"{v} {why.strip()[:40]} ｜ {text[:80]!r}")
    return why.strip() or "同じ仕事" if v == "DROP" else None
