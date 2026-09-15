#!/bin/zsh
# 编译并打包「每日运势.app」到 build/ 目录
set -e
cd "$(dirname "$0")"

APP="build/每日运势.app"

echo "== 生成图标 =="
python3 build_icon.py >/dev/null

echo "== 编译 Swift 原生程序 =="
rm -rf build
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -target arm64-apple-macosx13.0 \
  -framework Cocoa -framework WebKit \
  -o "$APP/Contents/MacOS/fortune" main.swift

echo "== 组装 APP 包 =="
cp index.html "$APP/Contents/Resources/index.html"
cp icon.icns "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<'PL'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>每日运势</string>
  <key>CFBundleDisplayName</key><string>每日运势</string>
  <key>CFBundleIdentifier</key><string>com.zcode.fortune-assistant</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>fortune</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PL
plutil -lint "$APP/Contents/Info.plist" >/dev/null

echo "== 签名（ad-hoc）=="
touch "$APP"
codesign --force --deep --sign - "$APP" 2>/dev/null || true

echo "== 完成: $APP =="
