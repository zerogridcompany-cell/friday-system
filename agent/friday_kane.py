"""カードの利用可能額の即答（11/15 オーナー「調べて→調べました を1秒未満の勢いで」）。
声（mimi-watch）と LINE（friday_sokutou）の両方から呼ぶ。AI を起こさず、~/bin/kane の決まった道で読む。
ためた額が10分以内ならそれを返す（0.1秒）。古ければ読み直す（楽天 約1秒・アメックス 約8秒・PayPay は iPhone で約30秒）。"""
import os, re, sys, json, time, datetime, subprocess
HOME = os.path.expanduser("~"); J = HOME + "/owner-kotoba/friday/kane/kane.json"
CARD = [("amex", r"アメックス|アメ[ック]|AMEX|amex"), ("rakuten", r"楽天"), ("paypay", r"ペイペイ|PayPay|paypay|ぺいぺい"), ("epos", r"エポス")]
NAME = {"amex": "アメックス", "rakuten": "楽天カード", "epos": "エポスカード", "paypay": "PayPayカード"}
WHAT = re.compile(r"利用可能|可能額|可能金額|いくら使え|あといくら|残り.{0,4}(いくら|何円)|使える(額|金額|枠)|利用残高|利用算高|枠.{0,6}(残|空)|残高")
NOT = re.compile(r"履歴|明細|支払い方法|ペイメント|外し|止め|登録|銀行")   # 履歴や設定は即答やない＝AI の道へ
def cards(t):
    if not WHAT.search(t) or NOT.search(t): return []
    if "PayPay銀行" in t or "ペイペイ銀行" in t: return []
    return [k for k, p in CARD if re.search(p, t)]
def _load():
    try: return json.load(open(J))
    except Exception: return {}
def kotae(t, max_age=600, log=lambda s: None):
    """戻り値＝LINE に送る本文 か None（即答できん＝今までの道へ）"""
    ks = cards(t)
    if not ks or "epos" in ks or "paypay" in ks: return None   # 11/15 エポスはサイトが「接続できません」・PayPay は iPhone の画面が他の仕事と取り合いで2分止まった＝道が固まるまで今までの道（AI）へ
    now = datetime.datetime.now(); d = _load()
    def age(k):
        try: return (now - datetime.datetime.strptime(d[k]["at"], "%Y-%m-%dT%H:%M")).total_seconds()
        except Exception: return 1e9
    old = [k for k in ks if age(k) > max_age]
    if old:
        t0 = time.time()
        try: subprocess.run([sys.executable, HOME + "/bin/kane", "refresh", *old], capture_output=True, timeout=150)
        except Exception as e: log(f"kane 読み直し失敗 {e}")
        log(f"kane 読み直し {old} {time.time()-t0:.1f}秒"); d = _load(); now = datetime.datetime.now()
    if any(age(k) > max_age + 200 for k in ks): return None   # 読めんかった＝今までの道（AI が自分で調べる）へ
    rows = []
    for k in ks:
        v = d[k]; s = f"{NAME[k]}のご利用可能額は {v['kanou']:,}円です"
        if v.get("waku"): s += f"（枠 {v['waku']:,}円）"
        if v.get("seikyu"): s += f"。{v['seikyu']}"
        rows.append(s + f"。（{v['at'][11:]} 時点）")
    return "オーナー様、" + "\n".join(rows)
if __name__ == "__main__":
    for q in sys.argv[1:] or ["アメックスの利用可能額調べて", "楽天カードあといくら使える？", "アメックスの利用履歴を調べて", "〈店〉のアメックス外して", "PayPay銀行の残高"]:
        t0 = time.time(); r = kotae(q); print(f"[{(time.time()-t0)*1000:.0f}ms] {q} → {r or 'AIへ'}")
