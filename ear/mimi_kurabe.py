"""書き起こしの版と「声の有無の門」を、録ってある本物の声で比べる（11/14 オーナー「1でお願い」）。mlx-whisper の python で回す。
使い方：python mimi_kurabe.py <フォルダ> [turbo,large] → 1本ずつ：声の秒（VAD）・各版の文字・秒"""
import sys, os, json, time, glob, warnings
warnings.filterwarnings("ignore")
H = os.path.expanduser("~"); sys.path.insert(0, H + "/bin")
import numpy as np, torch, mlx_whisper, silero_vad, mimi_filter as FILT
from mlx_whisper.audio import load_audio
VAD = silero_vad.load_silero_vad()
MODELS = {"turbo": "mlx-community/whisper-large-v3-turbo", "large": "mlx-community/whisper-large-v3-mlx"}
def koe_sec(a):
    ts = silero_vad.get_speech_timestamps(torch.from_numpy(a), VAD, sampling_rate=16000, threshold=0.5, min_speech_duration_ms=250)
    return sum(t["end"] - t["start"] for t in ts) / 16000
def kiridashi(a, pad=0.35):
    """声の所だけ（前後 pad 秒つき・近い所はつなぐ）を並べた音。声が無ければ None"""
    ts = silero_vad.get_speech_timestamps(torch.from_numpy(a), VAD, sampling_rate=16000, threshold=0.5, min_speech_duration_ms=250)
    if not ts or sum(t["end"] - t["start"] for t in ts) < 0.4 * 16000: return None
    p = int(pad * 16000); segs = []
    for t in ts:
        s, e = max(0, t["start"] - p), min(len(a), t["end"] + p)
        if segs and s <= segs[-1][1] + 8000: segs[-1][1] = e
        else: segs.append([s, e])
    gap = np.zeros(4800, dtype=a.dtype)
    out = []
    for s, e in segs: out += [a[s:e], gap]
    return np.concatenate(out[:-1])
def kaku(a, m):
    t0 = time.time()
    r = mlx_whisper.transcribe(a, path_or_hf_repo=MODELS[m], language="ja", condition_on_previous_text=False, verbose=None)
    return FILT.moji(r.get("segments", [])), " ".join(s["text"].strip() for s in r.get("segments", [])), time.time() - t0
if __name__ == "__main__":
    d = sys.argv[1]; ms = (sys.argv[2] if len(sys.argv) > 2 else "turbo").split(",")
    out = []
    for f in sorted(glob.glob(d + "/*.m4a")):
        a = np.array(load_audio(f)); row = {"file": os.path.basename(f), "koe": round(koe_sec(a), 1), "len": round(len(a) / 16000, 1)}
        k = kiridashi(a)
        for m in ms:
            t, raw, s = kaku(a, m); row[m] = t; row[m + "_raw"] = raw; row[m + "_sec"] = round(s, 1)
            if k is not None: t, raw, s = kaku(k, m); row[m + "_kiri"] = t; row[m + "_kiri_sec"] = round(s, 1)
            else: row[m + "_kiri"] = ""; row[m + "_kiri_sec"] = 0
        out.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
