#!/usr/bin/env python3
"""オーナーの記録を Air と mini で合わせる（2026-11-02・オーナー「常に共有できてる状態・Wi-Fi に戻った段階ですぐ引き継ぐ」）
片方が止まっとった間に片方だけに残った物を、10分ごと＋ネットが変わった瞬間に両方へそろえる。消さん・上書きせん＝足りん分を足すだけ。
 ① kotoba.jsonl（言葉の倉庫・全部の行）＝id で足りん行を両方向に足す
 ② friday/会話/*.md（フライデーの往復）＝塊を合わせて時刻順に並べ直す
 ③ friday/media（写真・声）＝両方向に写す
使い方: friday-awase.py                … もう片方とつないで合わせる（launchd com.owner.friday-awase）
        friday-awase.py ids            … 自分の倉庫の id を1行ずつ出す
        friday-awase.py rows-missing   … 標準入力の id 一覧に無い行を JSON で出す
        friday-awase.py rows-absorb    … 標準入力の JSON の行を自分の倉庫に足す
        friday-awase.py kaiwa-dump     … 会話の塊を JSON で出す
        friday-awase.py kaiwa-absorb   … 標準入力の JSON の塊を足す
"""
import os, sys, json, re, glob, datetime, subprocess, tempfile, hashlib

HOME = os.path.expanduser("~")
WHO = "mini" if HOME == "/Users/owner" else "air"
KOTOBA = os.path.join(HOME, "owner-kotoba")
JL = os.path.join(KOTOBA, "kotoba.jsonl")
KAIWA = os.path.join(KOTOBA, "friday", "会話")
MEDIA = os.path.join(KOTOBA, "friday", "media")
LOG = os.path.join(KOTOBA, "friday", "awase.log")
OTHER = (["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", "mini-host"] if WHO == "air" else
         ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", "-i", os.path.join(HOME, ".ssh/id_ed25519_friday"), "owner@100.64.0.2"])
OTHER_RSYNC = ("mini-host:owner-kotoba/friday/media/" if WHO == "air" else "owner@100.64.0.2:owner-kotoba/friday/media/")
OTHER_SSH_OPT = ("ssh" if WHO == "air" else f"ssh -i {HOME}/.ssh/id_ed25519_friday")

def log(s):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f: f.write(f"{datetime.datetime.now():%F %T} [{WHO}] {s}\n")

def remote(cmd, stdin=None, timeout=180):
    p = subprocess.run(OTHER + [f"python3 ~/bin/friday-awase.py {cmd}"], input=stdin, capture_output=True, text=True, timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr.strip()[:160])
    return p.stdout

def row_key(r, line):
    return r.get("id") or hashlib.sha1(line.encode()).hexdigest()[:16]

def my_rows():
    """{id: 行}。id が無い古い行は行の中身の sha"""
    rows = {}
    if os.path.exists(JL):
        for l in open(JL, encoding="utf-8"):
            l = l.rstrip("\n")
            if not l.strip(): continue
            try: r = json.loads(l)
            except Exception: continue
            rows[row_key(r, l)] = r
    return rows

def append_rows(rows):
    mine = my_rows(); n = 0
    with open(JL, "a", encoding="utf-8") as f:
        for r in rows:
            k = row_key(r, json.dumps(r, ensure_ascii=False))
            if k in mine: continue
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); mine[k] = r; n += 1
    return n

HDR = re.compile(r"^### \d{2}:\d{2}（")

def parse_blocks(text):
    head, blocks, cur = [], [], None
    for line in text.splitlines():
        if HDR.match(line):
            if cur is not None: blocks.append(cur)
            cur = [line]
        elif cur is None: head.append(line)
        else: cur.append(line)
    if cur is not None: blocks.append(cur)
    norm = lambda b: "\n".join(b).rstrip()
    return "\n".join(head).strip(), [norm(b) for b in blocks if norm(b)]

def my_kaiwa():
    out = {}
    for p in sorted(glob.glob(os.path.join(KAIWA, "????-??-??.md"))):
        head, blocks = parse_blocks(open(p, encoding="utf-8").read())
        out[os.path.basename(p)] = {"head": head, "blocks": blocks}
    return out

def write_kaiwa(name, head, blocks):
    blocks = sorted(dict.fromkeys(blocks), key=lambda b: b[4:9])
    body = (head + "\n" if head else "") + "".join("\n" + b + "\n" for b in blocks)
    os.makedirs(KAIWA, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=KAIWA, prefix=".awase-")
    with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(body)
    os.replace(tmp, os.path.join(KAIWA, name))

def kaiwa_absorb(data):
    kaiwa = my_kaiwa(); n = 0
    for name, d in data.items():
        cur = kaiwa.get(name, {"head": "", "blocks": []})
        have = set(cur["blocks"]); new = [b for b in d["blocks"] if b not in have]
        if new: write_kaiwa(name, cur["head"] or d["head"], cur["blocks"] + new); n += len(new)
    return n

EDA = os.path.join(KOTOBA, "master", "枝")
OTHER_HOME = "/Users/owner" if WHO == "mini" else "/Users/owner"
def localize(t): return t.replace(OTHER_HOME, HOME)

def my_eda():
    return {os.path.basename(p): open(p, encoding="utf-8").read() for p in sorted(glob.glob(os.path.join(EDA, "*.md")))}

def merge_lines(mine, theirs):
    """相手にあって自分に無い行を、相手での「前の行」の後ろに差す（無ければ末尾）。消さん・並べ替えん"""
    ml = mine.splitlines(); tl = localize(theirs).splitlines(); have = set(ml); added = 0
    for i, l in enumerate(tl):
        if not l.strip() or l in have: continue
        pos = len(ml)
        for j in range(i - 1, -1, -1):
            if tl[j].strip() and tl[j] in have:
                pos = len(ml) - 1 - ml[::-1].index(tl[j]) + 1; break
        ml.insert(pos, l); have.add(l); added += 1
    return ("\n".join(ml) + "\n") if added else mine, added

def eda_absorb(data):
    n = 0; os.makedirs(EDA, exist_ok=True); mine = my_eda()
    for name, text in data.items():
        cur = mine.get(name)
        if cur is None:
            new, k = localize(text), text.count("\n")
        else:
            new, k = merge_lines(cur, text)
        if k:
            fd, tmp = tempfile.mkstemp(dir=EDA, prefix=".awase-")
            with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(new)
            os.replace(tmp, os.path.join(EDA, name)); n += k
    return n

def main():
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a == "eda-dump":
        json.dump(my_eda(), sys.stdout, ensure_ascii=False); return
    if a == "eda-absorb":
        n = eda_absorb(json.load(sys.stdin)); print(n); log(f"eda-absorb 行{n}"); return
    if a == "ids":
        sys.stdout.write("\n".join(my_rows().keys())); return
    if a == "rows-missing":
        have = set(sys.stdin.read().split())
        json.dump([r for k, r in my_rows().items() if k not in have], sys.stdout, ensure_ascii=False); return
    if a == "rows-absorb":
        n = append_rows(json.load(sys.stdin)); print(n); log(f"rows-absorb 行{n}"); return
    if a == "kaiwa-dump":
        json.dump(my_kaiwa(), sys.stdout, ensure_ascii=False); return
    if a == "kaiwa-absorb":
        n = kaiwa_absorb(json.load(sys.stdin)); print(n); log(f"kaiwa-absorb 塊{n}"); return

    # ── 両方向 ──
    try:
        mine = my_rows()
        got = append_rows(json.loads(remote("rows-missing", "\n".join(mine.keys()))))          # 相手にあって自分に無い行
        oth = set(remote("ids").split())
        send = [r for k, r in mine.items() if k not in oth]
        gave = int(remote("rows-absorb", json.dumps(send, ensure_ascii=False)).strip() or 0) if send else 0
        oth_dump = json.loads(remote("kaiwa-dump"))
        ok = kaiwa_absorb(oth_dump)
        oth_k = {n: set(d["blocks"]) for n, d in oth_dump.items()}
        send_k = {n: {"head": d["head"], "blocks": [b for b in d["blocks"] if b not in oth_k.get(n, set())]} for n, d in my_kaiwa().items()}
        send_k = {n: d for n, d in send_k.items() if d["blocks"]}
        gk = int(remote("kaiwa-absorb", json.dumps(send_k, ensure_ascii=False)).strip() or 0) if send_k else 0
        ge = eda_absorb(json.loads(remote("eda-dump")))                                             # 枝：相手の行を自分に
        ge2 = int(remote("eda-absorb", json.dumps(my_eda(), ensure_ascii=False)).strip() or 0)      # 枝：自分の行を相手に
    except Exception as e:
        log(f"もう片方に届かん: {e}"); print(f"届かん: {e}"); return
    m = {}
    os.makedirs(MEDIA, exist_ok=True)
    for tag, src, dst in (("もらった", OTHER_RSYNC, MEDIA + "/"), ("渡した", MEDIA + "/", OTHER_RSYNC)):
        try:
            p = subprocess.run(["rsync", "-a", "--ignore-existing", "-e", OTHER_SSH_OPT, "--rsync-path", "mkdir -p ~/owner-kotoba/friday/media && rsync",
                                "--itemize-changes", src, dst], capture_output=True, text=True, timeout=300)
            m[tag] = sum(1 for l in p.stdout.splitlines() if l.startswith(">f"))
            if p.returncode: log(f"media 写し失敗 {tag}: {p.stderr.strip()[:120]}")
        except Exception as e: log(f"media 写し失敗 {tag}: {e}"); m[tag] = "?"
    s = f"もらった 行{got} 塊{ok} 枝{ge} 写真{m.get('もらった')} ／ 渡した 行{gave} 塊{gk} 枝{ge2} 写真{m.get('渡した')}"
    log("合わせた: " + s); print(s)

if __name__ == "__main__":
    main()
