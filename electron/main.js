const { app, BrowserWindow, ipcMain, screen } = require("electron");
const path = require("path");

let win = null;
let savedBounds = null;
const HEADER_H = 58;

function createWindow() {
  win = new BrowserWindow({
    width: 320,
    height: 700,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  win.setAlwaysOnTop(true, "floating");
  win.loadFile("index.html", { search: "win=1" });
  win.on("closed", () => { win = null; });
}

ipcMain.on("bridge", (event, msg) => {
  if (!win) return;
  switch (msg.action) {
    case "quit":
      app.quit();
      break;
    case "fit": {
      const workArea = screen.getPrimaryDisplay().workAreaSize;
      const h = Math.min(Math.max(msg.height + HEADER_H, 200), workArea.height - 20);
      const b = win.getBounds();
      // 顶边保持不动
      win.setBounds({ x: b.x, y: b.y + b.height - h, width: 320, height: h });
      break;
    }
    case "setAutostart":
      app.setLoginItemSettings({ openAtLogin: !!msg.on });
      break;
    case "minimize": {
      savedBounds = win.getBounds();
      win.setBounds({
        x: savedBounds.x + savedBounds.width - 64,
        y: savedBounds.y,
        width: 64,
        height: 64
      });
      // 等窗口 resize 完成后再切小球模式
      setTimeout(() => {
        win.webContents.executeJavaScript(
          'document.body.classList.add("minimized")'
        );
      }, 100);
      break;
    }
    case "openURL": {
      const { shell } = require("electron");
      if (msg.url) shell.openExternal(msg.url);
      break;
    }
    case "autoUpdate": {
      if (msg.url && msg.version) downloadAndPromptUpdate(msg.url, msg.version);
      break;
    }
    case "expand": {
      const b = savedBounds || { x: 100, y: 100, width: 320, height: 700 };
      // 先恢复窗口大小
      win.setBounds({ x: b.x, y: b.y, width: 320, height: b.height });
      // 延迟确保窗口已 resize，再移除 minimized 类
      setTimeout(() => {
        win.webContents.executeJavaScript(
          'document.body.classList.remove("minimized"); ' +
          'if (typeof fit === "function") fit();'
        );
      }, 150);
      break;
    }
  }
});

// 下载新版本并提示用户退出更新
function downloadAndPromptUpdate(url, version) {
  const https = require("https");
  const fs = require("fs");
  const path = require("path");
  const os = require("os");
  
  const zipPath = path.join(os.tmpdir(), "fortune-new.zip");
  const file = fs.createWriteStream(zipPath);
  
  https.get(url, (response) => {
    response.pipe(file);
    file.on("finish", () => {
      file.close();
      // 显示提示
      const { dialog } = require("electron");
      dialog.showMessageBox(win, {
        type: "info",
        title: "更新完成",
        message: `新版本 v${version} 已下载完成`,
        detail: "点击「退出并更新」将自动替换并重启 APP",
        buttons: ["退出并更新", "稍后"],
        defaultId: 0
      }).then((result) => {
        if (result.response === 0) {
          performUpdate(zipPath);
        }
      });
    });
  }).on("error", (err) => {
    dialog.showMessageBox(win, {
      type: "error",
      title: "下载失败",
      message: "请检查网络后重试"
    });
  });
}

// 执行更新：退出 APP，启动批处理脚本替换并重启
function performUpdate(zipPath) {
  const { app } = require("electron");
  const path = require("path");
  const os = require("os");
  const fs = require("fs");
  
  const appDir = path.dirname(process.execPath);
  const scriptPath = path.join(os.tmpdir(), "fortune-update.bat");
  const batContent = `@echo off
timeout /t 2 /nobreak >nul
taskkill /F /IM 每日运势.exe >nul 2>&1
powershell -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${appDir}' -Force"
start "" "${path.join(appDir, "每日运势.exe")}"
`;
  fs.writeFileSync(scriptPath, batContent, "utf8");
  
  // 启动批处理并退出
  require("child_process").spawn("cmd.exe", ["/c", scriptPath], { detached: true });
  app.quit();
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
