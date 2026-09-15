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
        win.webContents.send("app-event", "minimized", true);
      }, 100);
      break;
    }
    case "expand": {
      const b = savedBounds || { x: 100, y: 100, width: 320, height: 700 };
      win.setBounds({ x: b.x, y: b.y, width: 320, height: b.height });
      setTimeout(() => {
        win.webContents.send("app-event", "minimized", false);
      }, 100);
      break;
    }
  }
});

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
