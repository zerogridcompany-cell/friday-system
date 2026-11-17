"""11/14 夜 plan/<日>.json を4つの係（tick・plan.sh・yakusoku・電話の決まり）が鍵なしで丸ごと書いとった＝後から書いた係が、間に足された知らせを消す筋があった。
ここを通して書く：鍵（.lock）を取る→今のファイルを読み直す→直す→置き換えで書く。"""
import json, os, fcntl, contextlib
@contextlib.contextmanager
def kagi(p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(lk, fcntl.LOCK_UN)
def yomu(p):
    try: return json.load(open(p))
    except Exception: return {"items": []}
def kaku(p, plan):
    plan["items"].sort(key=lambda i: i["at"])
    with open(p + ".tmp", "w") as f: json.dump(plan, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
def naosu(p, fn):
    """鍵の中で読み直して fn(plan) で直して書く。fn は plan を返す（None なら書かん）"""
    with kagi(p):
        plan = fn(yomu(p))
        if plan is not None: kaku(p, plan)
        return plan
def awasete_kaku(p, mine, new_ids=()):
    """長く持っとった mine（古い写し）を、今のファイルに合わせて書く：同じ id は mine の中身（送った印など）で上書き・
    mine が自分で足した物（new_ids）は足す・その間に他の係が足した物は残す・他の係が消した物は戻さん"""
    def fn(now):
        by = {i["id"]: i for i in mine["items"]}; have = set()
        out = []
        for i in now["items"]:
            have.add(i["id"]); out.append(by.get(i["id"], i))
        out += [i for i in mine["items"] if i["id"] not in have and i["id"] in set(new_ids)]
        now["items"] = out; return now
    return naosu(p, fn)
