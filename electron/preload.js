const { contextBridge, ipcRenderer } = require("electron");

// 让 index.html 里的 webkit.messageHandlers.bridge.postMessage 直接可用
contextBridge.exposeInMainWorld("webkit", {
  messageHandlers: {
    bridge: {
      postMessage: (msg) => ipcRenderer.send("bridge", msg)
    }
  }
});

// 直接操作 DOM，不依赖 window.onMinimized（避免 contextIsolation 问题）
ipcRenderer.on("app-event", (event, name, val) => {
  if (name === "minimized") {
    // 用 webFrame 直接执行 JS，绕过 contextIsolation
    const { webFrame } = require("electron");
    webFrame.executeJavaScript(`
      if (document.body) {
        document.body.classList.${val ? "add" : "remove"}("minimized");
      }
    `);
  }
});
