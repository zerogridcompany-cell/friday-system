#!/Users/owner/.local/share/uv/tools/mlx-whisper/bin/python
"""耳の「聞く」本体（11/14 夜 オーナー「囁き声でも正確に・幻聴もなくなるんじゃないか → 1でお願い」）
① 声の有無の門（Silero VAD）：声が 0.4 秒未満の区切りは書き起こしに回さん＝幻聴の元を断つ（本物の声で測った：幻聴4本は声 0.0 秒）
② 声の所だけ切り出して書き起こす：空港の「◯◯空港って何時まで」は丸ごとだと空・切り出すと読めた（0.9秒）
③ 版は入れっぱなし＝1本 約1秒（前は毎回読み込みで 2.2 秒）。版の名前は mimi/model.txt（無ければ turbo）
使い方：受け口（mimi-server.py）が子として起こし、1行に声の道を書くと「RES {json}」を1行返す。試験は `mimi_kiku.py --one <声>`。"""
import sys, os, json, time, warnings
warnings.filterwarnings("ignore")
H = os.path.expanduser("~"); sys.path.insert(0, H + "/bin")
os.environ["PATH"] = H + "/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")
import numpy as np, torch, mlx_whisper, silero_vad, mimi_filter as FILT
from mlx_whisper.audio import load_audio
VAD = silero_vad.load_silero_vad()
MF = H + "/owner-kotoba/friday/mimi/model.txt"
def model():
    try: m = open(MF).read().strip()
    except Exception: m = ""
    return m or "mlx-community/whisper-large-v3-turbo"
MIN_KOE = 0.4
JISHO = "フライデー、"
# 11/18 本人「聞くって英語対応してる？→やって」＝区切りごとに何語かを先に測り、英語がはっきり勝った時だけ英語で書き起こす。
# 止める時は mimi/eigo_off を置く。線＝EN_P（英語の確率）以上。日本語の試験 46本は全部 ja のまま（測り＝mimi/shiken/eigo.json）
EN_P = 0.80
JISHO_EN = "Friday,"
def gengo(k):
    """声が何語か（"en" か "ja"）と英語の確率。だめな時は ja"""
    if os.path.exists(H + "/owner-kotoba/friday/mimi/eigo_off"): return "ja", 0.0
    try:
        import mlx.core as mx
        from mlx_whisper.transcribe import ModelHolder
        from mlx_whisper.audio import log_mel_spectrogram, pad_or_trim, N_FRAMES, N_SAMPLES
        from mlx_whisper.decoding import detect_language
        md = ModelHolder.get_model(model(), mx.float16)
        mel = log_mel_spectrogram(k, n_mels=md.dims.n_mels, padding=N_SAMPLES)
        seg = pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16)
        _, pr = detect_language(md, seg)
        pr = pr[0] if isinstance(pr, list) else pr
        pe = float(pr.get("en", 0.0))
        return ("en" if pe >= EN_P else "ja"), round(pe, 3)
    except Exception:
        return "ja", 0.0
def kiridashi(a, pad=0.35):
    ts = silero_vad.get_speech_timestamps(torch.from_numpy(a), VAD, sampling_rate=16000, threshold=0.5, min_speech_duration_ms=250)
    koe = sum(t["end"] - t["start"] for t in ts) / 16000
    if koe < MIN_KOE: return None, koe
    p = int(pad * 16000); segs = []
    for t in ts:
        s, e = max(0, t["start"] - p), min(len(a), t["end"] + p)
        if segs and s <= segs[-1][1] + 8000: segs[-1][1] = e
        else: segs.append([s, e])
    gap = np.zeros(4800, dtype=a.dtype); out = []
    for s, e in segs: out += [a[s:e], gap]
    return np.concatenate(out[:-1]), koe
def nokosu(a, keep, pad=0.2):
    m = np.zeros(len(a), dtype=bool)
    for s, e in keep: m[max(0, int((s - pad) * 16000)):int((e + pad) * 16000)] = True
    return m
def kiku(path, keep=None):
    # 11/17 声紋の窓分け：受け口が「本人の窓」keep を渡したら、そこだけ残して書き起こす。周りの声の読み hoka は mimi/mado_hoka がある時だけ（全部の読みは受け口が zen に残す）
    t0 = time.time(); a = np.array(load_audio(path)); hoka = None
    if keep:
        m = nokosu(a, keep); b = np.where(m, 0, a).astype(a.dtype); a = np.where(m, a, 0).astype(a.dtype)
        kb, koeb = (kiridashi(b) if os.path.exists(H + "/owner-kotoba/friday/mimi/mado_hoka") else (None, 0))   # 周りの声の読みは今は使わん＝約1秒の節約（要る時は mimi/mado_hoka を置く）
        if kb is not None and koeb >= 1.5:
            try: hoka = FILT.moji(mlx_whisper.transcribe(kb, path_or_hf_repo=model(), language="ja", condition_on_previous_text=False, verbose=None, temperature=0.0).get("segments", []))
            except Exception: hoka = None
        res = _kiku(a, t0)
        if hoka: res["hoka"] = hoka
        res["mado"] = 1; res["sec"] = round(time.time() - t0, 2)
        return res
    return _kiku(a, t0)
def _kiku(a, t0):
    k, koe = kiridashi(a)
    if k is None: return {"text": "", "koe": round(koe, 2), "sec": round(time.time() - t0, 2), "why": "声なし"}
    # 11/16 本人「テレビの環境下で正確に」＝書き起こしに名前を先に教える（「フライエー」「フライド」「フライで」→「フライデー」12/14 が直った・テレビ45本に辞書の言葉が勝手に出たのは0）。
    # 辞書を長くすると動画の音に「カード会社の名前、〈人〉」を書いた＝「フライデー、」だけにする。辞書ありで空になった時だけ辞書なしで読み直す（「登録して」が消えた）
    lang, pe = gengo(k)
    if lang == "en":
        kw = dict(path_or_hf_repo=model(), language="en", condition_on_previous_text=False, verbose=None, temperature=0.0)
        r = mlx_whisper.transcribe(k, initial_prompt=JISHO_EN, **kw); segs = r.get("segments", [])
        if not FILT.moji(segs) or FILT.namae_dake(FILT.moji(segs)):
            r = mlx_whisper.transcribe(k, **kw); segs = r.get("segments", [])
        return {"text": FILT.moji(segs), "raw": " ".join(x["text"].strip() for x in segs)[:300], "koe": round(koe, 2),
                "sec": round(time.time() - t0, 2), "lang": "en", "pen": pe}
    kw = dict(path_or_hf_repo=model(), language="ja", condition_on_previous_text=False, verbose=None, temperature=0.0)   # 11/17 温度0＝同じ音は毎回同じ文字（読み直しのくじ引きで、外国語の動画が3回に1回でたらめなカタカナになっとった）
    r = mlx_whisper.transcribe(k, initial_prompt=JISHO, **kw)
    segs = r.get("segments", [])
    # 11/16 夜 名前しか出んかった時も辞書なしで読み直す＝雑音・他人の声に「フライデー、」が勝手に出て、聞き返しの LINE が何十通も出た。本当に名前だけ呼んだ時は辞書なしでも名前が出る
    if not FILT.moji(segs):
        r = mlx_whisper.transcribe(k, **kw); segs = r.get("segments", [])
    elif FILT.namae_dake(FILT.moji(segs)):
        # 辞書なしでも名前が出た時だけ残す。出んかったら捨てる（読み直しで出た別の文は採らん＝動画の音のでたらめが入る）
        r2 = mlx_whisper.transcribe(k, **kw); s2 = r2.get("segments", [])
        if not FILT.yobu(FILT.moji(s2)):
            return {"text": "", "raw": " ".join(s["text"].strip() for s in segs)[:300], "koe": round(koe, 2), "sec": round(time.time() - t0, 2), "why": "名前だけ（辞書の空耳）"}
        segs = s2
    return {"text": FILT.moji(segs), "raw": " ".join(s["text"].strip() for s in segs)[:300], "koe": round(koe, 2),
            "sec": round(time.time() - t0, 2), "pen": pe}
if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--one":
        print("RES " + json.dumps(kiku(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else None), ensure_ascii=False)); sys.exit(0)
    try: kiku(H + "/owner-kotoba/friday/mimi/shiken/koe/1794643131581.m4a")   # 版を先に読み込んでおく
    except Exception: pass
    print("RES " + json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        p = line.strip()
        if not p: continue
        try:
            if "\t" in p: p, kp = p.split("\t", 1); res = kiku(p, json.loads(kp))
            else: res = kiku(p)
        except Exception as e: res = {"err": repr(e)[:200]}
        print("RES " + json.dumps(res, ensure_ascii=False), flush=True)
