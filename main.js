const { app, BrowserWindow, ipcMain, Notification } = require("electron");
const path = require("path");
const fs = require("fs");

const USER_DATA = path.join(app.getPath("home"), ".pomodoro-electron");
app.setPath("userData", USER_DATA);
const CONFIG_PATH = path.join(USER_DATA, "config.json");

let mainWindow;

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
  } catch {
    return {};
  }
}

function saveConfig(data) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2), "utf-8");
}

function createWindow() {
  const config = loadConfig();

  mainWindow = new BrowserWindow({
    width: 400,
    height: 620,
    resizable: false,
    frame: false,
    transparent: false,
    backgroundColor: "#1e1e1e",
    alwaysOnTop: config.alwaysOnTop || false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  app.quit();
});

// ── IPC handlers ────────────────────────────────────────────────

ipcMain.handle("load-config", () => loadConfig());

ipcMain.handle("save-config", (_event, data) => {
  saveConfig(data);
  if (mainWindow) {
    mainWindow.setAlwaysOnTop(data.alwaysOnTop || false);
  }
});

ipcMain.handle("notify", (_event, { title, body }) => {
  if (Notification.isSupported()) {
    new Notification({ title, body, silent: false }).show();
  }
});

ipcMain.handle("minimize", () => mainWindow?.minimize());
ipcMain.handle("close", () => mainWindow?.close());
