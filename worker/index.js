// フライデー（LINE 公式 @YOUR_BOT_ID）の受け口。2026-10-29
// LINE → ここ（Cloudflare・いつも動いとる）に溜める → Air と mini の両方が取りに来て、先に取った方が Claude で返事する。
// どっちか1台でも生きとったら返事が返る。
// 鍵：CHANNEL_SECRET・ACCESS_TOKEN・AGENT_KEY（wrangler secret）・OWNER（オーナーの userId）

const J = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json" } });

async function verify(req, body, secret) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const b64 = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return b64 === req.headers.get("x-line-signature");
}

async function line(env, path, payload) {
  return fetch("https://api.line.me/v2/bot/message/" + path, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: "Bearer " + env.ACCESS_TOKEN },
    body: JSON.stringify(payload),
  });
}

// 11/16 夜 KV（無料枠＝1日 読み10万・書き1000）が上限に当たって、05:00〜09:00 と 17:30〜 の間ぜんぶ 500＝フライデーが丸ごと黙った
// （本人「調べますで終わる・返答が全くない」）。待ち列・済み印・覚えた文・ボタン・1回だけの印は Durable Object（store）に置く。
// 古い KV は「前に覚えた文（msg:）・ボタン（ask:）・前の会話（history）」を読む時だけ見る（落ちても黙って進む）。絵（img:）だけ KV のまま。
function store(env) {
  const kv = env.FRIDAY, d = env.LOCK.get(env.LOCK.idFromName("store"));
  const call = (op, k, body, ttl) => d.fetch("https://lock/kv?op=" + op + "&k=" + encodeURIComponent(k) + (ttl ? "&ttl=" + ttl : ""), body == null ? undefined : { method: "POST", body });
  const S = {
    async get(k) {
      const r = await call("get", k);
      if (r.status === 200) {
        const v = await r.text();
        if (k !== "history" || (await call("get", "history_old")).status === 200) return v;
        try {   // 前の会話（KV）をまだ足せてない＝読めた時に前へ足す
          const old = JSON.parse((await kv.get("history")) || "[]"), m = JSON.stringify(old.concat(JSON.parse(v || "[]")).slice(-160));
          await call("put", "history", m); await call("put", "history_old", "1"); return m;
        } catch (e) { return v; }
      }
      if (/^(msg:|ask:)/.test(k)) { try { return await kv.get(k); } catch (e) { return null; } }
      if (k === "history") { try { const v = await kv.get(k); await call("put", "history", v || "[]"); await call("put", "history_old", "1"); return v; } catch (e) { return null; } }
      return null;
    },
    async put(k, v, o) {
      if (k.startsWith("img:")) return kv.put(k, v, o);
      await call("put", k, typeof v === "string" ? v : JSON.stringify(v), o && o.expirationTtl);
    },
    async delete(k) { await call("del", k); if (k.startsWith("ask:")) { try { await kv.delete(k); } catch (e) {} } },
    async getWithMetadata(k, o) { try { return await kv.getWithMetadata(k, o); } catch (e) { return { value: null, metadata: null }; } },
  };
  return S;
}

export default {
  async fetch(req, env0) {
    const env = { FRIDAY: store(env0), LOCK: env0.LOCK, ACCESS_TOKEN: env0.ACCESS_TOKEN, CHANNEL_SECRET: env0.CHANNEL_SECRET, OWNER: env0.OWNER,
                  AGENT_KEY: env0.AGENT_KEY, PHONE_TOOL_KEY: env0.PHONE_TOOL_KEY };   // 下の env.FRIDAY は全部 store を通る
    const url = new URL(req.url);

    // LINE からの webhook
    if (url.pathname === "/webhook" && req.method === "POST") {
      const body = await req.text();
      if (!(await verify(req, body, env.CHANNEL_SECRET))) return new Response("bad sig", { status: 401 });
      const ev = JSON.parse(body).events || [];
      for (const e of ev) {
        if (e.source?.userId !== env.OWNER) continue;          // オーナー以外は相手にせん
        let item;
        if (e.type === "message") {
          const m = e.message;
          let text = m.type === "text" ? m.text : `（${m.type}を受け取った）`;
          // 11/09 位置情報：座標・住所を落とさず渡す
          if (m.type === "location") text = `（位置情報を受け取った：${m.title ? m.title + "・" : ""}${m.address || ""}・緯度${m.latitude},経度${m.longitude}・https://www.google.com/maps?q=${m.latitude},${m.longitude}）`;
          // 10/31 引用返信：LINE は引用元の番号（quotedMessageId）しか送ってこん＝覚えとる中身を添える
          let quoted = null;
          if (m.quotedMessageId) {
            quoted = await env.FRIDAY.get("msg:" + m.quotedMessageId);
            text = `（引用返信：「${quoted ? quoted.slice(0, 600) : "引用元の中身は記録に無い（古いメッセージ）"}」に対して）\n${text}`;
          }
          // 11/14 写真・動画・スタンプ・位置も覚える（引用された時に「どの写真か」分かる＝mini の media/<日付>/<id>.jpg と同じ番号）
          const kioku = m.type === "text" ? m.text.slice(0, 1500) : `（${m.type} id=${m.id}${m.type === "sticker" ? " スタンプ" : ""}${m.type === "location" ? " " + (m.title || "") + " " + (m.address || "") + " " + m.latitude + "," + m.longitude : ""}${m.type === "file" ? " " + (m.fileName || "") : ""}）`;
          await env.FRIDAY.put("msg:" + m.id, "オーナー：" + kioku, { expirationTtl: 60 * 60 * 24 * 60 });
          item = { id: `${Date.now()}_${m.id}`, text, type: m.type, mid: m.id, quoted, qid: m.quotedMessageId || null };
        } else if (e.type === "postback") {
          // 10/31 ボタン（送って／やめて）。ask:<id> に Claude が置いた「やる事」を付けて渡す
          const p = new URLSearchParams(e.postback.data || "");
          const aid = p.get("ask"), c = p.get("c");
          const ask = aid ? JSON.parse((await env.FRIDAY.get("ask:" + aid)) || "null") : null;
          if (ask) await env.FRIDAY.delete("ask:" + aid);      // 1回押したら終わり（2回目は効かん）
          const label = ask ? (c === "ok" ? ask.label : ask.no_label) : "（古いボタン）";
          item = { id: `${Date.now()}_pb`, text: `（ボタン）「${label}」を押した`, type: "postback", choice: c, ask: ask || { expired: true } };
        } else continue;
        const q = JSON.parse((await env.FRIDAY.get("queue")) || "[]");
        q.push({ ...item, at: new Date(e.timestamp).toISOString(), replyToken: e.replyToken });
        await env.FRIDAY.put("queue", JSON.stringify(q.slice(-20)));
        await fetch("https://api.line.me/v2/bot/chat/loading/start", {
          method: "POST", headers: { "content-type": "application/json", authorization: "Bearer " + env.ACCESS_TOKEN },
          body: JSON.stringify({ chatId: env.OWNER, loadingSeconds: 60 }),
        }).catch(() => {});
      }
      return new Response("ok");
    }

    // 11/11 フライデーが作った・拾った絵を LINE に画像で出すための置き場（読むだけは鍵なし・名前は推測できん長さ・30日で消える）
    if (url.pathname.startsWith("/img/") && req.method === "GET") {
      const id = url.pathname.slice(5).replace(/\.(jpg|png)$/, "");
      const { value, metadata } = await env.FRIDAY.getWithMetadata("img:" + id, { type: "arrayBuffer" });
      if (!value) return new Response("none", { status: 404 });
      return new Response(value, { headers: { "content-type": (metadata && metadata.ct) || "image/jpeg", "cache-control": "public, max-age=86400" } });
    }

    // 10/31 電話の途中で分からん事を、Mac のフライデー（Opus・全部の記録）に聞く。答えが出るまで最大110秒待つ
    if (url.pathname === "/tool/ask" && req.method === "POST") {
      if (req.headers.get("x-phone-key") !== env.PHONE_TOOL_KEY) return new Response("no", { status: 403 });
      const { question } = await req.json();
      let id = `${Date.now()}_phone`;
      // 11/14 夜 電話の係が同じ質問を3秒で5回投げて、5回とも別々に答えを作っとった（11/14 09:05）＝60秒以内の同じ質問は最初の1件の答えを待つ
      const qk = "phq_" + String(question || "").replace(/\s+/g, "").slice(0, 300);
      const first = await (await env.LOCK.get(env.LOCK.idFromName("claim")).fetch("https://lock/?id=" + encodeURIComponent(qk) + "&who=" + id + "&ttl=60")).text();
      if (first.startsWith("taken:")) id = first.slice(6);
      else {
        const q = JSON.parse((await env.FRIDAY.get("queue")) || "[]");
        q.push({ id, text: String(question || "").slice(0, 2000), type: "phone_ask", at: new Date().toISOString(), replyToken: null });
        await env.FRIDAY.put("queue", JSON.stringify(q.slice(-20)));
      }
      for (let i = 0; i < 55; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const a = await env.FRIDAY.get("phone_ans:" + id);
        if (a) return J({ answer: a });
      }
      return J({ answer: "（確認に時間がかかっています。通話のあと LINE でお送りすると伝えてください）" });
    }

    // ここから下は Air・mini 用（AGENT_KEY が要る）
    if (req.headers.get("x-agent-key") !== env.AGENT_KEY) return new Response("no", { status: 403 });
    const who = req.headers.get("x-agent") || "?";

    // 11/11 絵を置く（Air・mini から）。返す url を LINE の画像に使う
    if (url.pathname === "/img" && req.method === "POST") {
      const ct = req.headers.get("content-type") || "image/jpeg";
      const buf = await req.arrayBuffer();
      if (buf.byteLength > 1000000) return J({ ok: false, why: "1MB を超えとる" }, 413);
      const id = [...crypto.getRandomValues(new Uint8Array(16))].map(b => b.toString(16).padStart(2, "0")).join("");
      await env.FRIDAY.put("img:" + id, buf, { expirationTtl: 60 * 60 * 24 * 30, metadata: { ct } });
      return J({ ok: true, url: `${url.origin}/img/${id}.${ct.includes("png") ? "png" : "jpg"}` });
    }

    // 生きとる印
    if (url.pathname === "/beat") {
      await env.FRIDAY.put("beat:" + who, new Date().toISOString());
      return J({ ok: true });
    }
    if (url.pathname === "/status") {
      return J({ air: await env.FRIDAY.get("beat:air"), mini: await env.FRIDAY.get("beat:mini"),
                 queue: JSON.parse((await env.FRIDAY.get("queue")) || "[]").length });
    }

    // 未処理のメッセージを1件取る（3分の予約つき・先に取った方が勝ち）
    if (url.pathname === "/claim") {
      const q = JSON.parse((await env.FRIDAY.get("queue")) || "[]");
      for (const msg of q) {
        if (await env.FRIDAY.get("done:" + msg.id)) {           // 11/14 夜 もう返した物は渡さん・11/16 列からも外す
          const q3 = JSON.parse((await env.FRIDAY.get("queue")) || "[]").filter(x => x.id !== msg.id);
          await env.FRIDAY.put("queue", JSON.stringify(q3));
          continue;
        }
        // 10/30 KV は同時に2台が「取った」になった＝1つだけの Durable Object で順番に決める
        const lock = env.LOCK.get(env.LOCK.idFromName("claim"));
        const got = await (await lock.fetch("https://lock/?id=" + encodeURIComponent(msg.id) + "&who=" + who)).text();
        if (got !== "ok") continue;
        const hist = JSON.parse((await env.FRIDAY.get("history")) || "[]");
        return J({ msg, history: hist.slice(-80) });
      }
      return J({ msg: null });
    }

    // 返事を送って片付ける
    if (url.pathname === "/answer" && req.method === "POST") {
      const { id, text, links, ask, images } = await req.json();
      const q = JSON.parse((await env.FRIDAY.get("queue")) || "[]");
      const msg = q.find(x => x.id === id);
      if (!msg) return J({ ok: false, why: "もう処理済み" });
      // 11/14 夜 待ち行列（KV）は同時の書き戻しで後勝ち＝消したはずの id が残って25分後にもう1通届いとった。届いた id は別の鍵に覚えて、二度は送らん
      if (await env.FRIDAY.get("done:" + id)) {
        await env.FRIDAY.put("queue", JSON.stringify(q.filter(x => x.id !== id)));
        return J({ ok: false, why: "もう処理済み" });
      }
      if (msg.type === "phone_ask") {   // 電話の質問への答え＝LINE には送らず、待っとる電話に返す
        await env.FRIDAY.put("phone_ans:" + id, String(text).slice(0, 1500), { expirationTtl: 600 });
        await env.FRIDAY.put("done:" + id, "1", { expirationTtl: 172800 });
        const q2 = JSON.parse((await env.FRIDAY.get("queue")) || "[]").filter(x => x.id !== id);
        await env.FRIDAY.put("queue", JSON.stringify(q2));
        return J({ ok: true, via: "phone" });
      }
      let m = { type: "text", text: String(text).slice(0, 4900) };
      if (links && links.length) m = { type: "template", altText: String(text).slice(0, 390),
        template: { type: "buttons", text: String(text).slice(0, 160), actions: links.slice(0, 3).map(([l, u]) => ({ type: "uri", label: String(l).slice(0, 20), uri: u })) } };
      if (ask) m.quickReply = await makeAsk(env, ask);
      // 11/11 本人「短く・写真やビジュアルで」＝返事に絵を最大4枚つける（返信の鍵で送れば無料・1回で5つまで）
      const ims = (images || []).filter(u => /^https:\/\//.test(u)).slice(0, 4).map(u => ({ type: "image", originalContentUrl: u, previewImageUrl: u }));
      const ms = [m, ...ims];
      if (m.quickReply && ims.length) { ims[ims.length - 1].quickReply = m.quickReply; delete m.quickReply; }   // ボタンは最後の吹き出しにしか出ん
      let r = msg.replyToken ? await line(env, "reply", { replyToken: msg.replyToken, messages: ms }) : { ok: false };   // 返信は無料
      let via = "reply";
      if (!r.ok) { r = await line(env, "push", { to: env.OWNER, messages: ms }); via = "push"; }
      if (r.ok) {
        await env.FRIDAY.put("done:" + id, "1", { expirationTtl: 172800 });
        await remember(env, r, String(text), ims.length);
        const hist = JSON.parse((await env.FRIDAY.get("history")) || "[]");
        hist.push({ at: msg.at, me: msg.text }, { at: new Date().toISOString(), friday: text, by: who });
        await env.FRIDAY.put("history", JSON.stringify(hist.slice(-160)));
        const q2 = JSON.parse((await env.FRIDAY.get("queue")) || "[]").filter(x => x.id !== id);
        await env.FRIDAY.put("queue", JSON.stringify(q2));
      }
      return J({ ok: r.ok, via, status: r.status });
    }

    // 10/31 ボタンを作る（friday-send など push 側から）。返す quickReply をそのままメッセージに付ける
    if (url.pathname === "/ask" && req.method === "POST") {
      return J({ quickReply: await makeAsk(env, await req.json()) });
    }

    // 10/31 電話のあと：通話の記録をオーナーの一言と同じ列に入れる＝返事係が約束を LINE で果たす（返信の鍵は無い＝push）
    if (url.pathname === "/enqueue" && req.method === "POST") {
      const { text } = await req.json();
      const q = JSON.parse((await env.FRIDAY.get("queue")) || "[]");
      q.push({ id: `${Date.now()}_call`, text: String(text).slice(0, 6000), type: "call", at: new Date().toISOString(), replyToken: null });
      await env.FRIDAY.put("queue", JSON.stringify(q.slice(-20)));
      return J({ ok: true });
    }

    // 10/31 Mac から送った文（friday-send）も覚える
    if (url.pathname === "/remember" && req.method === "POST") {
      const { ids, text, nimg } = await req.json();
      const L = (ids || []).length;
      for (let i = 0; i < L; i++) await env.FRIDAY.put("msg:" + ids[i], oboe(String(text), i, L, Number(nimg) || 0), { expirationTtl: 60 * 60 * 24 * 60 });
      return J({ ok: true });
    }

    // 決まった時刻の仕事を1回だけにする（例 job=line-asa:2026-10-30）
    if (url.pathname === "/once") {
      const job = url.searchParams.get("job");
      const k = "once:" + job;
      if (await env.FRIDAY.get(k)) return J({ run: false, by: await env.FRIDAY.get(k) });
      await env.FRIDAY.put(k, who, { expirationTtl: 60 * 60 * 30 });
      return J({ run: (await env.FRIDAY.get(k)) === who });
    }

    return new Response("friday", { status: 404 });
  },
};

// 送った文を、LINE がくれる番号（sentMessages[].id）で覚える＝あとで引用返信された時に中身が分かる
// 11/16 本人「メッセージ不具合」＝文＋絵2枚を全部同じ文で覚えとった→絵を引用されても1枚目か2枚目か分からん。絵は「N枚目」として覚える（絵は送った順に後ろに並ぶ）
function oboe(text, i, n, nimg) {
  const k = n - nimg;
  return i < k ? "フライデー：" + text.slice(0, 1500)
               : `フライデー：（この返事に付けた絵の${i - k + 1}枚目＝番号${i - k + 1}の絵が引用された。オーナー様は${i - k + 1}番を指しとる）` + text.slice(0, 1400);
}
async function remember(env, res, text, nimg = 0) {
  try {
    const sm = (await res.clone().json()).sentMessages || [];
    for (let i = 0; i < sm.length; i++) await env.FRIDAY.put("msg:" + sm[i].id, oboe(text, i, sm.length, nimg), { expirationTtl: 60 * 60 * 24 * 60 });
  } catch (e) {}
}

// ボタン（送って／やめて）：やる事を KV に1日置いて、押されたら postback で受け取る
async function makeAsk(env, ask) {
  const aid = crypto.randomUUID().slice(0, 12);
  const a = { label: String(ask.label || "やって").slice(0, 20), no_label: String(ask.no_label || "やめて").slice(0, 20),
              action: String(ask.action || ""), made: new Date().toISOString() };
  await env.FRIDAY.put("ask:" + aid, JSON.stringify(a), { expirationTtl: 86400 });
  const b = (c, l) => ({ type: "action", action: { type: "postback", label: l, data: `ask=${aid}&c=${c}`, displayText: l } });
  return { items: [b("ok", a.label), b("no", a.no_label)] };
}

// 予約の帳面（1つだけ・同時に来ても1件ずつ処理される）
export class Lock {
  constructor(state) { this.state = state; }
  async fetch(req) {
    const u = new URL(req.url), id = u.searchParams.get("id"), who = u.searchParams.get("who");
    if (u.pathname === "/kv") {   // 11/16 置き場（store）＝KV の代わり。値 {v, e:切れる時刻(ms)・0=切れん}
      const op = u.searchParams.get("op"), k = "kv:" + u.searchParams.get("k"), t = Date.now();
      if (op === "get") {
        const c = await this.state.storage.get(k);
        if (!c || (c.e && c.e < t)) { if (c) await this.state.storage.delete(k); return new Response("", { status: 404 }); }
        return new Response(c.v);
      }
      if (op === "put") {
        const ttl = Number(u.searchParams.get("ttl")) || 0;
        await this.state.storage.put(k, { v: await req.text(), e: ttl ? t + ttl * 1000 : 0 });
        if (Math.random() < 0.02) {   // 切れた物の掃除（少しずつ）
          const cur = (await this.state.storage.get("gc")) || "kv:";
          const part = await this.state.storage.list({ prefix: "kv:", startAfter: cur, limit: 500 });
          let last = "kv:";
          for (const [kk, vv] of part) { last = kk; if (vv.e && vv.e < t) await this.state.storage.delete(kk); }
          await this.state.storage.put("gc", part.size < 500 ? "kv:" : last);
        }
        return new Response("ok");
      }
      if (op === "del") { await this.state.storage.delete(k); return new Response("ok"); }
      return new Response("?", { status: 400 });
    }
    const now = Date.now(), cur = await this.state.storage.get(id);
    const ttl = (Number(u.searchParams.get("ttl")) || 1500) * 1000;   // 11/14 夜 鍵ごとに長さを決められる（電話の同じ質問＝60秒）
    if (cur && now - cur.t < ttl) return new Response(cur.who === who ? "mine" : "taken:" + cur.who);
    await this.state.storage.put(id, { who, t: now });
    // 古い予約は掃除
    const all = await this.state.storage.list();
    for (const [k, v] of all) if (now - v.t > 86400 * 1000) await this.state.storage.delete(k);
    return new Response("ok");
  }
}
