import SwiftUI
import AVFoundation
import CoreLocation
import AudioToolbox

// フライデーの耳（2026-11-13）：iPhone のマイクで聞き続け、30秒ずつ（声がある所だけ）場所と一緒に Mac mini へ送る。
// mini 側＝~/bin/mimi-server.py（文字にする）→ ~/bin/mimi-watch.py（先回りの LINE）。

@main
struct FridayMimiApp: App {
    @StateObject private var ear = Ear.shared
    var body: some Scene {
        WindowGroup { ContentView().environmentObject(ear) }
    }
}

struct ContentView: View {
    @EnvironmentObject var ear: Ear
    var body: some View {
        VStack(spacing: 22) {
            Text("フライデーの耳").font(.largeTitle.bold())
            Button(action: { ear.on ? ear.stop() : ear.start() }) {
                Text(ear.on ? "聞いています（押すと止める）" : "止まっています（押すと聞く）")
                    .font(.title3.bold()).frame(maxWidth: .infinity).padding(.vertical, 18)
                    .background(ear.on ? Color.green : Color.gray.opacity(0.3))
                    .foregroundColor(ear.on ? .white : .primary).cornerRadius(14)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text(ear.status)
                Text("mini に送った数：\(ear.sent)　送信待ち：\(ear.pending)")
                Text("最後に送った時刻：\(ear.lastSent)")
                Text("場所：\(ear.locText)")
                Text("mini との接続：\(ear.ping)")
            }.font(.callout).frame(maxWidth: .infinity, alignment: .leading)
            Button("mini に届くか試す") { ear.checkPing() }.font(.callout)
            Spacer()
            Text("声がある30秒だけを送ります。電話中は止まり、終わると自動で戻ります。")
                .font(.footnote).foregroundColor(.secondary)
        }
        .padding(20)
        .onAppear { ear.checkPing() }
    }
}

// 11/14 どの iPhone か（iPhone19,7＝持ち歩き・iPhone16,1＝家に置く 15 Pro）
let deviceModel: String = {
    var u = utsname(); uname(&u)
    return withUnsafeBytes(of: &u.machine) { b in String(decoding: b.prefix(while: { $0 != 0 }), as: UTF8.self) }
}()

final class Ear: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = Ear()

    @Published var on = UserDefaults.standard.bool(forKey: "on")
    @Published var status = "止まっています"
    @Published var sent = UserDefaults.standard.integer(forKey: "sent")
    @Published var pending = 0
    @Published var lastSent = "まだ"
    @Published var locText = "まだ"
    @Published var ping = "未確認"

    private let engine = AVAudioEngine()
    private var converter: AVAudioConverter?
    private let outFmt = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16000, channels: 1, interleaved: false)!
    private let q = DispatchQueue(label: "friday.ear.audio")
    private var file: AVAudioFile?
    private var fileURL: URL?
    private var chunkStart = Date()
    private var chunkFrames: AVAudioFramePosition = 0
    private var chunkLoud: Float = 0
    private let loc = CLLocationManager()
    private var lastLoc: CLLocation?
    private var timer: Timer?
    private var uploading = false
    private var lastAudio = Date()
    private var stoppedAt: Date?
    private var ticks = 0
    // 11/15 v4 オーナー「動画を流しながら話すと文字が化ける」＝iPhone で鳴っとる動画の音が声を埋めとった（11:48〜11:58 動画の音楽が音割れの大きさ）
    // ① 声の処理（Apple のエコー消し＋雑音消し）。オン／オフは mini の心拍の返事（vp）で切り替える＝入れ直し不要
    // ② 区切りごとに「ほかのアプリが音を出しとった割合」(ta) を mini へ＝その区切りの文字は動画の音として扱える
    private var vp = UserDefaults.standard.bool(forKey: "vp")
    private var vpNow = false
    private var oaChecks = 0
    private var oaHits = 0
    private var oaLast = Date.distantPast
    // 11/15 v4 心拍に中身（原因調べ 残り1：12:04〜14:07 に声が届かんかった＝止めたのか・マイクが黙っとったのか分からんかった）
    // 直近の心拍からの「一番大きい音」「送った区切り」「捨てた区切り（静かすぎ）」「ほかのアプリが鳴っとった秒」
    private var hbPeak: Float = 0
    private var hbKeep = 0
    private var hbDrop = 0
    private var hbOA = 0

    private let chunkSec = 30.0
    // 11/14 夜 オーナー「聞いてから LINE が返るまでをもっと速く」＝話し終わり（1.2秒の静けさ）で区切ってすぐ送る。30秒の区切り待ちをやめる
    private let pauseSec = 1.2
    private let minSec = 3.0
    private var spoke = false
    private var quietFrames: AVAudioFramePosition = 0
    private var koePeak: Float = 0
    private let loudLine: Float = 0.008      // この RMS を1回も超えん30秒は送らん（無音・遠い雑音）

    private var url: URL { URL(string: Bundle.main.object(forInfoDictionaryKey: "MimiURL") as? String ?? "")! }
    private var key: String { Bundle.main.object(forInfoDictionaryKey: "MimiKey") as? String ?? "" }
    private var queueDir: URL {
        let u = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("q")
        try? FileManager.default.createDirectory(at: u, withIntermediateDirectories: true)
        return u
    }

    override init() {
        super.init()
        loc.delegate = self
        loc.desiredAccuracy = kCLLocationAccuracyHundredMeters
        loc.distanceFilter = 30
        let nc = NotificationCenter.default
        nc.addObserver(self, selector: #selector(interrupted(_:)), name: AVAudioSession.interruptionNotification, object: nil)
        nc.addObserver(self, selector: #selector(restartSoon), name: .AVAudioEngineConfigurationChange, object: engine)
        nc.addObserver(self, selector: #selector(restartSoon), name: AVAudioSession.mediaServicesWereResetNotification, object: nil)
        nc.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
            guard let self = self, self.on, !self.engine.isRunning else { return }
            self.startEngine()
        }
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.tick() }
        if on { DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.start() } }
    }

    // MARK: 始める・止める
    func start() {
        on = true
        UserDefaults.standard.set(true, forKey: "on")
        AVAudioApplication.requestRecordPermission { ok in
            DispatchQueue.main.async {
                guard ok else { self.status = "マイクが許可されていません（設定 → フライデーの耳 → マイク）"; return }
                self.loc.requestAlwaysAuthorization()
                self.loc.allowsBackgroundLocationUpdates = true
                self.loc.pausesLocationUpdatesAutomatically = false
                self.loc.showsBackgroundLocationIndicator = false
                self.loc.startUpdatingLocation()
                self.loc.startMonitoringSignificantLocationChanges()
                self.startEngine()
            }
        }
    }

    func stop() {
        on = false
        UserDefaults.standard.set(false, forKey: "on")
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        q.async { self.closeChunk() }
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        loc.stopUpdatingLocation()
        status = "止まっています"
        heartbeat()   // 11/14 夜 オーナー「俺が意図的に止めてる」＝止めた瞬間に on=0 を mini へ（1分待つと眠って届かん→見張りが「落ちた」と誤報）
    }

    private func startEngine() {
        do {
            let s = AVAudioSession.sharedInstance()
            // 音楽や動画を止めずに聞く（mixWithOthers）
            try s.setCategory(.playAndRecord, mode: .default, options: [.mixWithOthers, .defaultToSpeaker, .allowBluetoothA2DP])
            try? s.setAllowHapticsAndSystemSoundsDuringRecording(true)   // v5 録りながら震えと音を出す
            try s.setActive(true)
            let input = engine.inputNode
            if input.isVoiceProcessingEnabled != vp { try input.setVoiceProcessingEnabled(vp) }
            if vp {
                if #available(iOS 17.0, *) {   // 動画の音を小さくせん（下げ幅は最小）
                    input.voiceProcessingOtherAudioDuckingConfiguration = AVAudioVoiceProcessingOtherAudioDuckingConfiguration(enableAdvancedDucking: false, duckingLevel: .min)
                }
                _ = engine.mainMixerNode   // 声の処理は出口側とつながっとらんと動かん
            }
            vpNow = vp
            let inFmt = input.outputFormat(forBus: 0)
            guard inFmt.sampleRate > 0, inFmt.channelCount > 0 else { status = "マイクが使えません（他のアプリが使用中）"; retryLater(); return }
            converter = AVAudioConverter(from: inFmt, to: outFmt)
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 4096, format: inFmt) { [weak self] buf, _ in
                guard let self = self, let out = self.convert(buf) else { return }
                self.q.async { self.write(out) }
            }
            engine.prepare()
            try engine.start()
            lastAudio = Date()
            status = vp ? "聞いています（声の処理オン）" : "聞いています"
        } catch {
            status = "開始できません：\(error.localizedDescription)"
            retryLater()
        }
    }

    private func retryLater() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) { if self.on && !self.engine.isRunning { self.startEngine() } }
    }

    @objc private func interrupted(_ n: Notification) {
        guard let raw = n.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
        if type == .began {
            q.async { self.closeChunk() }
            DispatchQueue.main.async { self.status = "一時停止中（電話・ほかのアプリ）" }
        } else {
            restartSoon()
        }
    }

    @objc private func restartSoon() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
            guard self.on else { return }
            self.engine.inputNode.removeTap(onBus: 0)
            self.engine.stop()
            self.startEngine()
        }
    }

    // MARK: 音を30秒ずつ m4a に
    private func convert(_ buf: AVAudioPCMBuffer) -> AVAudioPCMBuffer? {
        guard let conv = converter else { return nil }
        let cap = AVAudioFrameCount(Double(buf.frameLength) * outFmt.sampleRate / buf.format.sampleRate) + 64
        guard let out = AVAudioPCMBuffer(pcmFormat: outFmt, frameCapacity: cap) else { return nil }
        var given = false
        var err: NSError?
        conv.convert(to: out, error: &err) { _, st in
            if given { st.pointee = .noDataNow; return nil }
            given = true
            st.pointee = .haveData
            return buf
        }
        return (err == nil && out.frameLength > 0) ? out : nil
    }

    private func write(_ b: AVAudioPCMBuffer) {
        if file == nil { openChunk() }
        guard let f = file else { return }
        if Date().timeIntervalSince(oaLast) >= 1 {   // 1秒に1回：ほかのアプリ（動画・音楽）が鳴っとるか
            oaLast = Date()
            let s = AVAudioSession.sharedInstance()
            oaChecks += 1
            if s.isOtherAudioPlaying || s.secondaryAudioShouldBeSilencedHint { oaHits += 1; hbOA += 1 }
        }
        if let ch = b.floatChannelData?[0] {
            var sum: Float = 0
            let n = Int(b.frameLength)
            for i in 0..<n { sum += ch[i] * ch[i] }
            let rms = (sum / Float(max(n, 1))).squareRoot()
            chunkLoud = max(chunkLoud, rms)
            hbPeak = max(hbPeak, rms)
            // 11/15 オーナー「聞いてからの応答速度」＝周りに音（動画・テレビ・街）があると 0.008 を下回らず、話し終わりを取れんで30秒待っとった（今朝の区切り 15〜35秒）
            // → 直近の声の大きさ（koePeak）の3割を下回ったら「話し終わり」。静かな部屋では今まで通り 0.008
            koePeak = max(koePeak * 0.99, rms)
            let quietLine = max(loudLine, koePeak * 0.3)
            if rms >= max(loudLine * 1.5, koePeak * 0.5) { spoke = true; quietFrames = 0 }
            else if rms < quietLine { quietFrames += AVAudioFramePosition(n) }
        }
        do { try f.write(from: b) } catch { closeChunk(); return }
        chunkFrames += AVAudioFramePosition(b.frameLength)
        DispatchQueue.main.async { self.lastAudio = Date() }
        let sec = Double(chunkFrames) / outFmt.sampleRate
        if sec >= chunkSec { closeChunk() }
        else if spoke && sec >= minSec && Double(quietFrames) / outFmt.sampleRate >= pauseSec {
            closeChunk()
            DispatchQueue.main.async { self.uploadNext() }   // 5秒ごとの見回りを待たずに送る
        }
    }

    private func openChunk() {
        let u = FileManager.default.temporaryDirectory.appendingPathComponent("c-\(Int(Date().timeIntervalSince1970 * 1000)).m4a")
        let settings: [String: Any] = [AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 16000,
                                       AVNumberOfChannelsKey: 1, AVEncoderBitRateKey: 32000]
        file = try? AVAudioFile(forWriting: u, settings: settings, commonFormat: .pcmFormatFloat32, interleaved: false)
        fileURL = u
        chunkStart = Date()
        chunkFrames = 0
        chunkLoud = 0
        spoke = false
        quietFrames = 0
        oaChecks = 0
        oaHits = 0
    }

    private func closeChunk() {
        guard let u = fileURL else { return }
        file = nil            // ここで書き終わる
        fileURL = nil
        let fm = FileManager.default
        guard chunkLoud >= loudLine, chunkFrames > Int64(outFmt.sampleRate * 2) else { hbDrop += 1; try? fm.removeItem(at: u); return }
        hbKeep += 1
        let base = "\(Int(chunkStart.timeIntervalSince1970 * 1000))"
        let dst = queueDir.appendingPathComponent(base + ".m4a")
        try? fm.moveItem(at: u, to: dst)
        var meta: [String: Any] = ["at": ISO8601DateFormatter().string(from: chunkStart),
                                   "ta": oaChecks > 0 ? Double(oaHits) / Double(oaChecks) : 0, "vp": vpNow ? 1 : 0]
        if let l = lastLoc {
            meta["lat"] = l.coordinate.latitude
            meta["lon"] = l.coordinate.longitude
            meta["acc"] = l.horizontalAccuracy
        }
        if let d = try? JSONSerialization.data(withJSONObject: meta) {
            try? d.write(to: queueDir.appendingPathComponent(base + ".json"))
        }
    }

    // MARK: 5秒ごと：見張り＋送る
    private func tick() {
        if on && (!engine.isRunning || Date().timeIntervalSince(lastAudio) > 20) {
            status = "マイクを戻しています…"
            restartSoon()
            lastAudio = Date()
        }
        if on && !engine.isRunning { if stoppedAt == nil { stoppedAt = Date() } } else { stoppedAt = nil }
        ticks += 1
        if ticks % 12 == 1 { heartbeat() }   // 1分ごと
        uploadNext()
    }

    // 11/14 心拍：mini に「生きとる・マイクが動いとるか」を1分ごとに知らせる（止まったらフライデーが LINE で知らせる）
    private func heartbeat() {
        var c = URLComponents(string: url.absoluteString.replacingOccurrences(of: "/up", with: "/hb"))!
        let stop = stoppedAt.map { Int(Date().timeIntervalSince($0)) } ?? 0
        c.queryItems = [URLQueryItem(name: "on", value: on ? "1" : "0"), URLQueryItem(name: "run", value: engine.isRunning ? "1" : "0"),
                        URLQueryItem(name: "stopsec", value: "\(stop)"), URLQueryItem(name: "q", value: "\(pending)"),
                        URLQueryItem(name: "st", value: status),
                        URLQueryItem(name: "bg", value: UIApplication.shared.applicationState == .background ? "1" : "0"),
                        URLQueryItem(name: "dev", value: deviceModel), URLQueryItem(name: "v", value: "5"),
                        URLQueryItem(name: "vp", value: vpNow ? "1" : "0")]
        q.sync {   // 音の数は音の列で数えとる＝同じ列で読んで0に戻す
            let db = hbPeak > 0 ? Int((20 * log10(hbPeak)).rounded()) : -120
            c.queryItems! += [URLQueryItem(name: "lvl", value: "\(db)"), URLQueryItem(name: "keep", value: "\(hbKeep)"),
                              URLQueryItem(name: "drop", value: "\(hbDrop)"), URLQueryItem(name: "oa", value: "\(hbOA)")]
            hbPeak = 0; hbKeep = 0; hbDrop = 0; hbOA = 0
        }
        var r = URLRequest(url: c.url!); r.timeoutInterval = 10
        r.setValue(key, forHTTPHeaderField: "x-key")
        URLSession.shared.dataTask(with: r) { data, _, _ in
            // mini の返事 {"vp":0|1} で声の処理を切り替える
            guard let d = data, let j = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any], let want = j["vp"] as? Int else { return }
            DispatchQueue.main.async {
                let w = want == 1
                guard w != self.vp else { return }
                self.vp = w
                UserDefaults.standard.set(w, forKey: "vp")
                if self.on { self.restartSoon() }
            }
        }.resume()
    }

    // 11/16 v5 mini の書き起こしを最大20秒待って、名前で呼ばれとったら「ポン」と震え
    private func ack(_ fn: String) {
        var c = URLComponents(string: url.absoluteString.replacingOccurrences(of: "/up", with: "/ack"))!
        c.queryItems = [URLQueryItem(name: "f", value: fn)]
        var r = URLRequest(url: c.url!); r.timeoutInterval = 25
        r.setValue(key, forHTTPHeaderField: "x-key")
        URLSession.shared.dataTask(with: r) { data, _, _ in
            guard let d = data, let j = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any], (j["yobi"] as? Int) == 1 else { return }
            DispatchQueue.main.async { self.chime() }
        }.resume()
    }
    private var chimePlayer: AVAudioPlayer?
    private func chime() {
        // 2つの音（880Hz→1320Hz・各0.09秒）をその場で作る＝音のファイルを持たん
        let sr = 44100.0; var pcm = [Int16]()
        for (hz, dur) in [(880.0, 0.09), (1320.0, 0.12)] {
            let n = Int(sr * dur)
            for i in 0..<n {
                let env = min(1.0, Double(i) / 200.0) * min(1.0, Double(n - i) / 600.0)
                pcm.append(Int16(sin(2 * .pi * hz * Double(i) / sr) * env * 9000))
            }
        }
        var d = Data()
        func u32(_ v: UInt32) { var x = v.littleEndian; d.append(Data(bytes: &x, count: 4)) }
        func u16(_ v: UInt16) { var x = v.littleEndian; d.append(Data(bytes: &x, count: 2)) }
        let bytes = UInt32(pcm.count * 2)
        d.append("RIFF".data(using: .ascii)!); u32(36 + bytes); d.append("WAVEfmt ".data(using: .ascii)!)
        u32(16); u16(1); u16(1); u32(44100); u32(88200); u16(2); u16(16)
        d.append("data".data(using: .ascii)!); u32(bytes)
        pcm.withUnsafeBufferPointer { d.append(Data(buffer: $0)) }
        chimePlayer = try? AVAudioPlayer(data: d)
        chimePlayer?.volume = 0.6
        chimePlayer?.play()
        AudioServicesPlaySystemSound(1519)   // 短い震え
    }

    private func pendingFiles() -> [URL] {
        let fm = FileManager.default
        var files = ((try? fm.contentsOfDirectory(at: queueDir, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension == "m4a" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
        while files.count > 600 {   // 圏外が長い時に iPhone を埋めん（約70MB）
            let old = files.removeFirst()
            try? fm.removeItem(at: old)
            try? fm.removeItem(at: old.deletingPathExtension().appendingPathExtension("json"))
        }
        return files
    }

    private func uploadNext() {
        let files = pendingFiles()
        pending = files.count
        guard !uploading, let f = files.first else { return }
        let metaURL = f.deletingPathExtension().appendingPathExtension("json")
        let meta = ((try? JSONSerialization.jsonObject(with: Data(contentsOf: metaURL))) as? [String: Any]) ?? [:]
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 30
        req.setValue(key, forHTTPHeaderField: "x-key")
        req.setValue("audio/mp4", forHTTPHeaderField: "content-type")
        req.setValue(deviceModel, forHTTPHeaderField: "x-dev")
        for (k, h) in [("at", "x-at"), ("lat", "x-lat"), ("lon", "x-lon"), ("acc", "x-acc"), ("ta", "x-ta"), ("vp", "x-vp")] {
            if let v = meta[k] { req.setValue("\(v)", forHTTPHeaderField: h) }
        }
        uploading = true
        URLSession.shared.uploadTask(with: req, fromFile: f) { data, resp, err in
            DispatchQueue.main.async {
                self.uploading = false
                if err == nil, (resp as? HTTPURLResponse)?.statusCode == 200 {
                    // 11/16 v5 受け取りの音：mini が「名前で呼ばれた」と読んだら短く鳴らす（聞こえたかその場で分かる）
                    if let d = data, let j = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any], let fn = j["f"] as? String { self.ack(fn) }
                    try? FileManager.default.removeItem(at: f)
                    try? FileManager.default.removeItem(at: metaURL)
                    self.sent += 1
                    UserDefaults.standard.set(self.sent, forKey: "sent")
                    self.lastSent = Date().formatted(date: .omitted, time: .standard)
                    self.ping = "OK"
                    self.uploadNext()
                } else {
                    self.ping = "届きません（Tailscale がオフ？）"
                }
            }
        }.resume()
    }

    func checkPing() {
        let p = URL(string: url.absoluteString.replacingOccurrences(of: "/up", with: "/ping"))!
        var r = URLRequest(url: p); r.timeoutInterval = 8
        URLSession.shared.dataTask(with: r) { _, resp, err in
            DispatchQueue.main.async {
                self.ping = (err == nil && (resp as? HTTPURLResponse)?.statusCode == 200) ? "OK" : "届きません（Tailscale がオフ？）"
            }
        }.resume()
    }

    // MARK: 場所
    func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        guard let l = locs.last else { return }
        lastLoc = l
        locText = String(format: "%.4f, %.4f（±%.0fm）", l.coordinate.latitude, l.coordinate.longitude, l.horizontalAccuracy)
    }

    func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {}
}
