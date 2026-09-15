import Cocoa
import WebKit

// 每日运势 · 桌面悬浮算命小助手（原生 macOS 版）
// 无边框悬浮面板 + 原生标题栏（可拖动/关闭）+ WKWebView 渲染运势内容。

let APP_ID = "com.zcode.fortune-assistant"
let CONFIG_PATH = NSHomeDirectory() + "/.fortune_assistant.json"
let PID_PATH = NSHomeDirectory() + "/.fortune_assistant.pid"
let AGENT_PLIST = NSHomeDirectory() + "/Library/LaunchAgents/\(APP_ID).plist"
let HEADER_H: CGFloat = 62
let WIN_W: CGFloat = 320

let RED = NSColor(calibratedRed: 0xB0 / 255, green: 0x3A / 255, blue: 0x2E / 255, alpha: 1)
let RED_LINE = NSColor(calibratedRed: 0x8E / 255, green: 0x2A / 255, blue: 0x21 / 255, alpha: 1)
let TITLE_COLOR = NSColor(calibratedRed: 0xFD / 255, green: 0xEB / 255, blue: 0xD0 / 255, alpha: 1)
let DATE_COLOR = NSColor(calibratedRed: 0xF0 / 255, green: 0xD5 / 255, blue: 0xC5 / 255, alpha: 1)

// ---------------------------------------------------------- 干支 / 生肖

let STEMS = Array("甲乙丙丁戊己庚辛壬癸")
let BRANCHES = Array("子丑寅卯辰巳午未申酉戌亥")
let ZODIAC = Array("鼠牛虎兔龙蛇马羊猴鸡狗猪")
let WEEK_CN = ["日", "一", "二", "三", "四", "五", "六"]  // Calendar.weekday: 1 = 周日
let CNY: [Int: (Int, Int)] = [
    2015: (2, 19), 2016: (2, 8), 2017: (1, 28), 2018: (2, 16),
    2019: (2, 5), 2020: (1, 25), 2021: (2, 12), 2022: (2, 1),
    2023: (1, 22), 2024: (2, 10), 2025: (1, 29), 2026: (2, 17),
    2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3),
    2031: (1, 23), 2032: (2, 11), 2033: (1, 31), 2034: (2, 19),
    2035: (2, 8),
]

func ganzhiDay(_ date: Date) -> String {
    let cal = Calendar(identifier: .gregorian)
    let base = cal.date(from: DateComponents(year: 1949, month: 10, day: 1))!  // 甲子日
    let days = cal.dateComponents([.day], from: base, to: date).day ?? 0
    return "\(STEMS[days % 10])\(BRANCHES[days % 12])"
}

func ganzhiYear(_ date: Date) -> (String, String) {
    let cal = Calendar.current
    var y = cal.component(.year, from: date)
    let m = cal.component(.month, from: date)
    let d = cal.component(.day, from: date)
    let (cm, cd) = CNY[y] ?? (2, 4)
    if m < cm || (m == cm && d < cd) { y -= 1 }
    let n = (y - 1984) % 60  // 1984 = 甲子年
    return ("\(STEMS[n % 10])\(BRANCHES[n % 12])", "\(ZODIAC[n % 12])")
}

func dateLine() -> String {
    let now = Date()
    let cal = Calendar.current
    let (gz, zc) = ganzhiYear(now)
    return String(format: "%d年%d月%d日 星期%@ · %@%@年 · %@日",
                  cal.component(.year, from: now), cal.component(.month, from: now),
                  cal.component(.day, from: now), WEEK_CN[cal.component(.weekday, from: now) - 1],
                  gz, zc, ganzhiDay(now))
}

// ---------------------------------------------------------- 配置 / 单实例 / 自启

func readConfig() -> [String: Any] {
    guard let data = FileManager.default.contents(atPath: CONFIG_PATH),
          let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    else { return [:] }
    return obj
}

func writeConfig(_ cfg: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: cfg, options: [.prettyPrinted]) {
        try? data.write(to: URL(fileURLWithPath: CONFIG_PATH))
    }
}

func guardSingleInstance() {
    if let s = try? String(contentsOfFile: PID_PATH, encoding: .utf8),
       let pid = Int32(s.trimmingCharacters(in: .whitespacesAndNewlines)),
       kill(pid, 0) == 0 {
        exit(0)  // 已在运行
    }
    try? "\(getpid())".write(toFile: PID_PATH, atomically: true, encoding: .utf8)
    atexit { try? FileManager.default.removeItem(atPath: PID_PATH) }
    signal(SIGTERM) { _ in exit(0) }
    signal(SIGINT) { _ in exit(0) }
}

func autostartOn() -> Bool {
    FileManager.default.fileExists(atPath: AGENT_PLIST)
}

func runTool(_ path: String, _ args: [String]) {
    let p = Process()
    p.launchPath = path
    p.arguments = args
    p.standardOutput = FileHandle.nullDevice
    p.standardError = FileHandle.nullDevice
    try? p.run()
}

func setAutostart(_ on: Bool) {
    if on {
        let execPath = Bundle.main.executablePath ?? ""
        let plist = """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>Label</key><string>\(APP_ID)</string>
          <key>ProgramArguments</key>
          <array>
            <string>\(execPath)</string>
          </array>
          <key>RunAtLoad</key><true/>
          <key>KeepAlive</key><false/>
          <key>ProcessType</key><string>Interactive</string>
        </dict>
        </plist>
        """
        try? FileManager.default.createDirectory(
            atPath: (AGENT_PLIST as NSString).deletingLastPathComponent,
            withIntermediateDirectories: true)
        try? plist.write(toFile: AGENT_PLIST, atomically: true, encoding: .utf8)
        runTool("/bin/launchctl", ["enable", "gui/\(getuid())/\(APP_ID)"])
        runTool("/bin/launchctl", ["bootstrap", "gui/\(getuid())", AGENT_PLIST])
    } else {
        try? FileManager.default.removeItem(atPath: AGENT_PLIST)
    }
}

// ---------------------------------------------------------- 标题栏（可拖动）

final class HeaderView: NSView {
    private var startMouse = NSPoint.zero
    private var startOrigin = NSPoint.zero

    override init(frame: NSRect) {
        super.init(frame: frame)

        let title = NSTextField(labelWithString: "🏮 每日运势")
        title.font = NSFont.systemFont(ofSize: 15, weight: .bold)
        title.textColor = TITLE_COLOR
        title.frame = NSRect(x: 14, y: frame.height - 30, width: 220, height: 22)
        addSubview(title)

        let date = NSTextField(labelWithString: dateLine())
        date.font = NSFont.systemFont(ofSize: 10)
        date.textColor = DATE_COLOR
        date.frame = NSRect(x: 14, y: 8, width: frame.width - 28, height: 14)
        date.lineBreakMode = .byTruncatingTail
        addSubview(date)

        let close = NSButton(title: "", target: nil, action: nil)
        close.isBordered = false
        close.attributedTitle = NSAttributedString(string: "✕", attributes: [
            .foregroundColor: DATE_COLOR,
            .font: NSFont.systemFont(ofSize: 13, weight: .bold),
        ])
        close.frame = NSRect(x: frame.width - 34, y: frame.height - 32, width: 26, height: 24)
        close.target = self
        close.action = #selector(closeClicked)
        addSubview(close)

        let mini = NSButton(title: "", target: nil, action: nil)
        mini.isBordered = false
        mini.attributedTitle = NSAttributedString(string: "−", attributes: [
            .foregroundColor: DATE_COLOR,
            .font: NSFont.systemFont(ofSize: 15, weight: .bold),
        ])
        mini.frame = NSRect(x: frame.width - 62, y: frame.height - 32, width: 26, height: 24)
        mini.target = self
        mini.action = #selector(minimizeClicked)
        addSubview(mini)
    }

    required init?(coder: NSCoder) { fatalError() }

    var onMinimize: (() -> Void)?

    @objc func minimizeClicked() {
        onMinimize?()
    }

    @objc func closeClicked() {
        NSApp.terminate(nil)
    }

    override func draw(_ dirtyRect: NSRect) {
        RED.setFill()
        dirtyRect.fill()
        RED_LINE.setFill()
        NSRect(x: 0, y: 0, width: bounds.width, height: 1).fill()
    }

    override func mouseDown(with event: NSEvent) {
        startMouse = NSEvent.mouseLocation
        startOrigin = window?.frame.origin ?? .zero
    }

    override func mouseDragged(with event: NSEvent) {
        guard let w = window else { return }
        let now = NSEvent.mouseLocation
        w.setFrameOrigin(NSPoint(x: startOrigin.x + now.x - startMouse.x,
                                 y: startOrigin.y + now.y - startMouse.y))
    }

    override func mouseUp(with event: NSEvent) {
        if let o = window?.frame.origin {
            var cfg = readConfig()
            cfg["nx"] = Int(o.x)
            cfg["ny"] = Int(o.y)
            writeConfig(cfg)
        }
    }
}

// ---------------------------------------------------------- 悬浮小球

let BALL: CGFloat = 64

final class BallView: NSView {
    var onExpand: (() -> Void)?
    var levelColor = NSColor(calibratedRed: 0x95 / 255, green: 0xA5 / 255, blue: 0xA6 / 255, alpha: 1)
    private var startMouse = NSPoint.zero
    private var startOrigin = NSPoint.zero
    private var moved = false

    override func draw(_ dirtyRect: NSRect) {
        let rect = bounds.insetBy(dx: 2.5, dy: 2.5)
        let path = NSBezierPath(ovalIn: rect)
        let top = NSColor(calibratedRed: 0xD2 / 255, green: 0x52 / 255, blue: 0x41 / 255, alpha: 1)
        let bottom = NSColor(calibratedRed: 0x8C / 255, green: 0x22 / 255, blue: 0x18 / 255, alpha: 1)
        NSGradient(colors: [top, bottom])?.draw(in: path, angle: -90)
        NSColor(calibratedRed: 0xE9 / 255, green: 0xC4 / 255, blue: 0x6A / 255, alpha: 1).setStroke()
        path.lineWidth = 3
        path.stroke()

        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont(name: "STKaitiSC-Bold", size: 26)
                ?? NSFont(name: "STKaiti", size: 26)
                ?? NSFont.systemFont(ofSize: 26, weight: .bold),
            .foregroundColor: NSColor(calibratedRed: 0xF6 / 255, green: 0xD6 / 255, blue: 0x70 / 255, alpha: 1),
        ]
        let s = NSAttributedString(string: "吉", attributes: attrs)
        let sz = s.size()
        s.draw(at: NSPoint(x: (bounds.width - sz.width) / 2,
                           y: (bounds.height - sz.height) / 2 - 1))

        // 今日签级小圆点
        let dot = NSBezierPath(ovalIn: NSRect(x: bounds.midX - 4, y: 7, width: 8, height: 8))
        levelColor.setFill()
        dot.fill()
    }

    override func mouseDown(with event: NSEvent) {
        startMouse = NSEvent.mouseLocation
        startOrigin = window?.frame.origin ?? .zero
        moved = false
    }

    override func mouseDragged(with event: NSEvent) {
        let now = NSEvent.mouseLocation
        let dx = now.x - startMouse.x, dy = now.y - startMouse.y
        if abs(dx) + abs(dy) > 4 { moved = true }
        window?.setFrameOrigin(NSPoint(x: startOrigin.x + dx, y: startOrigin.y + dy))
    }

    override func mouseUp(with event: NSEvent) {
        if moved {
            if let o = window?.frame.origin {
                var cfg = readConfig()
                cfg["nx"] = Int(o.x)
                cfg["ny"] = Int(o.y)
                writeConfig(cfg)
            }
        } else {
            onExpand?()  // 单击小球展开
        }
    }

    @objc func expandItem() { onExpand?() }
    @objc func quitItem() { NSApp.terminate(nil) }
    @objc func toggleAutostartItem(_ sender: NSMenuItem) { setAutostart(!autostartOn()) }

    override func rightMouseDown(with event: NSEvent) {
        let menu = NSMenu()
        let e1 = NSMenuItem(title: "展开运势面板", action: #selector(expandItem), keyEquivalent: "")
        e1.target = self
        menu.addItem(e1)
        let a1 = NSMenuItem(title: "开机自动启动", action: #selector(toggleAutostartItem(_:)), keyEquivalent: "")
        a1.target = self
        a1.state = autostartOn() ? .on : .off
        menu.addItem(a1)
        menu.addItem(.separator())
        let q1 = NSMenuItem(title: "关闭每日运势", action: #selector(quitItem), keyEquivalent: "")
        q1.target = self
        menu.addItem(q1)
        menu.popUp(positioning: e1, at: NSPoint(x: 0, y: bounds.height + 4), in: self)
    }
}

// ---------------------------------------------------------- JS 桥

final class Bridge: NSObject, WKScriptMessageHandler {
    weak var delegate: AppDelegate?

    func userContentController(_ ucc: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any],
              let action = body["action"] as? String else { return }
        switch action {
        case "quit":
            NSApp.terminate(nil)
        case "fit":
            if let h = (body["height"] as? NSNumber)?.doubleValue {
                delegate?.fitHeight(CGFloat(h))
            }
        case "setAutostart":
            setAutostart((body["on"] as? Bool) ?? false)
        case "level":
            if let lv = body["level"] as? String { delegate?.setLevel(lv) }
        case "expand":
            delegate?.setMinimized(false)
        default:
            break
        }
    }
}

// ---------------------------------------------------------- 主窗口

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var window: NSPanel!
    var webView: WKWebView!
    var header: HeaderView!
    var ballView: BallView?
    var contentH: CGFloat = 700
    var minimized = false
    var levelColor = NSColor(calibratedRed: 0x95 / 255, green: 0xA5 / 255, blue: 0xA6 / 255, alpha: 1)

    func applicationDidFinishLaunching(_ note: Notification) {
        let cfg = readConfig()
        let x = CGFloat((cfg["nx"] as? NSNumber)?.doubleValue ?? 120)
        let y = CGFloat((cfg["ny"] as? NSNumber)?.doubleValue ?? 220)

        let rect = NSRect(x: x, y: y, width: WIN_W, height: 700)
        let panel = NSPanel(contentRect: rect,
                            styleMask: [.borderless, .nonactivatingPanel],
                            backing: .buffered, defer: false)
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window = panel

        let content = panel.contentView!
        content.wantsLayer = true
        content.layer?.cornerRadius = 14
        content.layer?.masksToBounds = true

        let hdr = HeaderView(frame: NSRect(x: 0, y: rect.height - HEADER_H,
                                           width: WIN_W, height: HEADER_H))
        hdr.autoresizingMask = [.width, .minYMargin]
        hdr.onMinimize = { [weak self] in self?.setMinimized(true) }
        content.addSubview(hdr)
        header = hdr

        let conf = WKWebViewConfiguration()
        let bridge = Bridge()
        bridge.delegate = self
        conf.userContentController.add(bridge, name: "bridge")

        let wv = WKWebView(frame: NSRect(x: 0, y: 0, width: WIN_W,
                                         height: rect.height - HEADER_H),
                           configuration: conf)
        wv.autoresizingMask = [.width, .height]
        wv.navigationDelegate = self
        webView = wv
        content.addSubview(wv)

        if let url = Bundle.main.url(forResource: "index", withExtension: "html") {
            wv.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }

        // 上次退出时若是小球状态，直接以小球形态启动
        if (cfg["minimized"] as? NSNumber)?.boolValue == true {
            setMinimized(true, anchorTopRight: false)
        }

        panel.orderFrontRegardless()
    }

    func setLevel(_ lv: String) {
        switch lv {
        case "上上签": levelColor = NSColor(calibratedRed: 0xD4/255, green: 0xAF/255, blue: 0x37/255, alpha: 1)
        case "上吉": levelColor = NSColor(calibratedRed: 0xE6/255, green: 0x7E/255, blue: 0x22/255, alpha: 1)
        case "中吉": levelColor = NSColor(calibratedRed: 0x52/255, green: 0xBE/255, blue: 0x80/255, alpha: 1)
        case "小吉": levelColor = NSColor(calibratedRed: 0x5D/255, green: 0xAD/255, blue: 0xE2/255, alpha: 1)
        default: levelColor = NSColor(calibratedRed: 0x95/255, green: 0xA5/255, blue: 0xA6/255, alpha: 1)
        }
        if let b = ballView {
            b.levelColor = levelColor
            b.setNeedsDisplay(b.bounds)
        }
    }

    /// 收缩为小球 / 展开回面板。anchorTopRight：收缩时锚定右上角（缩小按钮的位置）。
    func setMinimized(_ m: Bool, anchorTopRight: Bool = true) {
        minimized = m
        guard let w = window else { return }
        let content = w.contentView!
        if m {
            var f = w.frame
            if anchorTopRight {
                f.origin = NSPoint(x: f.maxX - BALL, y: f.maxY - BALL)
            }
            f.size = NSSize(width: BALL, height: BALL)
            header.isHidden = true
            webView.isHidden = true
            let ball = BallView(frame: NSRect(x: 0, y: 0, width: BALL, height: BALL))
            ball.levelColor = levelColor
            ball.onExpand = { [weak self] in self?.setMinimized(false) }
            content.addSubview(ball)
            ballView = ball
            content.layer?.cornerRadius = BALL / 2
            w.setFrame(f, display: true)
        } else {
            ballView?.removeFromSuperview()
            ballView = nil
            header.isHidden = false
            webView.isHidden = false
            content.layer?.cornerRadius = 14
            var f = w.frame
            let h = contentH + HEADER_H
            f.origin = NSPoint(x: f.maxX - WIN_W, y: f.maxY - h)
            f.size = NSSize(width: WIN_W, height: h)
            w.setFrame(f, display: true)
            // 让页面重新汇报一次高度，防止展开后尺寸不对
            webView.evaluateJavaScript("window.fit && window.fit()", completionHandler: nil)
        }
        var cfg = readConfig()
        cfg["minimized"] = m
        cfg["nx"] = Int(w.frame.origin.x)
        cfg["ny"] = Int(w.frame.origin.y)
        writeConfig(cfg)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        // 把原生侧状态（如开机自启是否开启）注入页面
        webView.evaluateJavaScript(
            "window.applyNative && window.applyNative({autostart: \(autostartOn())})")
    }

    func fitHeight(_ h: CGFloat) {
        contentH = h
        guard !minimized, let w = window else { return }
        let screenH = NSScreen.main?.visibleFrame.height ?? 900
        let newH = min(max(h + HEADER_H, 240), screenH - 20)
        var f = w.frame
        f.origin.y = f.maxY - newH  // 顶边保持不动
        f.size.height = newH
        w.setFrame(f, display: true)
    }

    func applicationWillTerminate(_ note: Notification) {
        if let o = window?.frame.origin {
            var cfg = readConfig()
            cfg["nx"] = Int(o.x)
            cfg["ny"] = Int(o.y)
            writeConfig(cfg)
        }
    }
}

// ---------------------------------------------------------- 入口

guardSingleInstance()

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)  // 显示 Dock 图标（用户要求有图标）
app.run()
