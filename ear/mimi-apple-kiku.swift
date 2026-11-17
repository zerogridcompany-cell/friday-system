import Foundation
import Speech
import AVFoundation
// 使い方：kiku <声の道...>  1本ごとに「RES {json}」を1行。標準入力から道を1行ずつでも可。
@main struct Kiku {
    static func yomu(_ path: String, _ locale: Locale) async throws -> String {
        let transcriber = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [], attributeOptions: [])
        let analyzer = SpeechAnalyzer(modules: [transcriber])
        let file = try AVAudioFile(forReading: URL(fileURLWithPath: path))
        async let text: String = {
            var s = ""
            for try await r in transcriber.results { s += String(r.text.characters) }
            return s
        }()
        if let last = try await analyzer.analyzeSequence(from: file) { try await analyzer.finalizeAndFinish(through: last) } else { await analyzer.cancelAndFinishNow() }
        return try await text
    }
    static func main() async {
        let locale = Locale(identifier: "ja-JP")
        do {
            let sup = await SpeechTranscriber.supportedLocales.map { $0.identifier(.bcp47) }
            let ins = await SpeechTranscriber.installedLocales.map { $0.identifier(.bcp47) }
            FileHandle.standardError.write("対応 \(sup.contains("ja-JP")) 入っとる \(ins.contains("ja-JP"))\n".data(using: .utf8)!)
            let t = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [], attributeOptions: [])
            if let req = try await AssetInventory.assetInstallationRequest(supporting: [t]) { try await req.downloadAndInstall() }
        } catch { FileHandle.standardError.write("準備だめ \(error)\n".data(using: .utf8)!) }
        func dasu(_ p: String) async {
            let t0 = Date()
            var o: [String: Any] = ["file": (p as NSString).lastPathComponent]
            do { o["text"] = try await yomu(p, locale) } catch { o["err"] = "\(error)" }
            o["sec"] = Date().timeIntervalSince(t0)
            let d = try! JSONSerialization.data(withJSONObject: o, options: [])
            print("RES " + String(data: d, encoding: .utf8)!); fflush(stdout)
        }
        let paths = Array(CommandLine.arguments.dropFirst())
        if !paths.isEmpty { for p in paths { await dasu(p) }; return }
        print("RES {\"ready\": true}"); fflush(stdout)
        while let l = readLine() { if !l.isEmpty { await dasu(l) } }
    }
}
