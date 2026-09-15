import Cocoa
import WebKit

// 离屏渲染 index.html 并截图，用于无屏幕录制权限时的视觉自检。
// 用法: snapshot_tool <outPrefix> <index.html 路径>
// 产出三张: <prefix>_default.png（未设置）、<prefix>_signed.png（狮子座+1990）、<prefix>_year.png（仅出生年）

let outPrefix = CommandLine.arguments[1]
let htmlURL = URL(fileURLWithPath: CommandLine.arguments[2])

final class Delegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var cleared = false

    func applicationDidFinishLaunching(_ n: Notification) {
        window = NSWindow(contentRect: NSRect(x: -4000, y: 100, width: 320, height: 900),
                          styleMask: [.titled], backing: .buffered, defer: false)
        webView = WKWebView(frame: window.contentView!.bounds)
        webView.navigationDelegate = self
        window.contentView!.addSubview(webView)
        window.orderFrontRegardless()
        webView.loadFileURL(htmlURL, allowingReadAccessTo: htmlURL.deletingLastPathComponent())
    }

    func snap(_ tag: String, then: @escaping () -> Void) {
        let wv = webView!
        wv.evaluateJavaScript("document.body.scrollHeight") { res, _ in
            let h = CGFloat((res as? NSNumber)?.doubleValue ?? 700)
            self.window.setContentSize(NSSize(width: 320, height: h))
            self.webView.frame = NSRect(x: 0, y: 0, width: 320, height: h)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                let conf = WKSnapshotConfiguration()
                conf.rect = NSRect(x: 0, y: 0, width: 320, height: h)
                wv.takeSnapshot(with: conf) { img, err in
                    if let img = img, let tiff = img.tiffRepresentation,
                       let rep = NSBitmapImageRep(data: tiff),
                       let png = rep.representation(using: .png, properties: [:]) {
                        let path = "\(outPrefix)_\(tag).png"
                        try? png.write(to: URL(fileURLWithPath: path))
                        print("saved:", path)
                    } else {
                        print("snapshot failed:", err?.localizedDescription ?? "?")
                    }
                    then()
                }
            }
        }
    }

    func webView(_ wv: WKWebView, didFinish navigation: WKNavigation!) {
        // 先清空 localStorage（该工具的数据会跨运行残留），再从头来
        if !cleared {
            cleared = true
            wv.evaluateJavaScript("localStorage.clear(); location.reload(); 'ok'") { _, _ in }
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            self.snap("default") {
                wv.evaluateJavaScript(
                    "localStorage.setItem('fa_sign','狮子座'); localStorage.setItem('fa_birth','1990-6-15-6'); render(); document.getElementById('meOverlay').hidden = true; 'ok'"
                ) { res, err in
                    if let err = err {
                        print("❌ JS 异常:", err.localizedDescription)
                        // 再执行一次逐行排查
                        wv.evaluateJavaScript("""
                            try {
                                localStorage.setItem('fa_sign','狮子座');
                                localStorage.setItem('fa_birth','1990-6-15-6');
                                'step1 ok'
                            } catch(e) { 'step1 error: ' + e.message }
                        """) { r1, _ in print("step1:", r1 ?? "?") }
                        wv.evaluateJavaScript("""
                            try { render(); 'render ok' } catch(e) { 'render error: ' + e.message }
                        """) { r2, _ in print("step2:", r2 ?? "?") }
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                        self.snap("full") { NSApp.terminate(nil) }
                    }
                }
            }
        }
    }
}

let app = NSApplication.shared
let d = Delegate()
app.delegate = d
app.setActivationPolicy(.accessory)
app.run()
