const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const path = require('path')
const fs = require('fs')

const API_PORT = process.env.MA_YISHENG_PORT || '8000'
const API_BASE = `http://127.0.0.1:${API_PORT}`
let backendProcess = null
let logFile = null

function log(message) {
  if (!logFile) return
  fs.appendFileSync(logFile, `[${new Date().toISOString()}] ${message}\n`)
}

function resolveBackendDir() {
  const candidates = [
    path.join(process.resourcesPath || '', 'backend'),
    path.join(__dirname, '..', '..'),
  ]

  return candidates.find((dir) => dir && require('fs').existsSync(path.join(dir, 'main.py')))
}

function resolveBackendExecutable() {
  const candidates = [
    path.join(process.resourcesPath || '', 'backend-bin', 'ma-yisheng-backend'),
    path.join(__dirname, '..', '..', 'dist', 'ma-yisheng-backend'),
  ]

  return candidates.find((file) => file && fs.existsSync(file))
}

function waitForBackend(timeoutMs = 30000) {
  const startedAt = Date.now()

  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(`${API_BASE}/api/health`, (res) => {
        res.resume()
        if (res.statusCode && res.statusCode < 500) {
          resolve()
          return
        }
        retry()
      })
      req.on('error', retry)
      req.setTimeout(1000, () => {
        req.destroy()
        retry()
      })
    }

    const retry = () => {
      if (Date.now() - startedAt > timeoutMs) {
        reject(new Error('后端启动超时'))
        return
      }
      setTimeout(check, 500)
    }

    check()
  })
}

function startBackend() {
  const backendBin = resolveBackendExecutable()
  const backendDir = resolveBackendDir()

  const env = {
    ...process.env,
    API_HOST: '127.0.0.1',
    API_PORT,
    SERVER_URL: '',
    ALLOWED_ORIGINS: '',
    MA_YISHENG_DATA_DIR: path.join(app.getPath('userData'), 'runtime'),
  }
  fs.mkdirSync(env.MA_YISHENG_DATA_DIR, { recursive: true })
  logFile = path.join(env.MA_YISHENG_DATA_DIR, 'backend.log')
  log(`Starting backend, bin=${backendBin || ''}, dir=${backendDir || ''}`)
  const out = fs.openSync(logFile, 'a')

  if (backendBin) {
    backendProcess = spawn(backendBin, ['--host', '127.0.0.1', '--port', API_PORT], {
      cwd: path.dirname(backendBin),
      env,
      stdio: ['ignore', out, out],
    })
  } else if (backendDir) {
    backendProcess = spawn('python3', ['main.py', '--host', '127.0.0.1', '--port', API_PORT], {
      cwd: backendDir,
      env,
      stdio: ['ignore', out, out],
    })
  } else {
    throw new Error('找不到后端可执行文件或 main.py')
  }

  backendProcess.on('error', (error) => {
    log(`Backend spawn error: ${error.message}`)
  })

  backendProcess.on('exit', (code, signal) => {
    log(`Backend exited: code=${code}, signal=${signal}`)
    backendProcess = null
  })
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 680,
    title: 'Ma Yisheng',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    log(`Renderer console level=${level} ${sourceId}:${line} ${message}`)
  })
  win.webContents.on('render-process-gone', (_event, details) => {
    log(`Renderer process gone: ${JSON.stringify(details)}`)
  })
  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    log(`Renderer failed load ${errorCode} ${errorDescription} ${validatedURL}`)
  })

  win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
}

app.whenReady().then(async () => {
  ipcMain.on('renderer-log', (_event, message) => {
    log(`Renderer ${message}`)
  })

  ipcMain.handle('show-path', async (_event, targetPath) => {
    if (!targetPath || typeof targetPath !== 'string') {
      return { ok: false, error: '路径为空' }
    }
    const normalizedPath = path.normalize(targetPath)
    if (!fs.existsSync(normalizedPath)) {
      return { ok: false, error: '路径不存在' }
    }
    shell.showItemInFolder(normalizedPath)
    return { ok: true }
  })

  ipcMain.handle('select-directory', async () => {
    const result = await dialog.showOpenDialog({
      title: '选择要扫描的项目目录',
      properties: ['openDirectory'],
    })
    if (result.canceled || result.filePaths.length === 0) {
      return { ok: false }
    }
    return { ok: true, path: result.filePaths[0] }
  })

  try {
    startBackend()
    await waitForBackend()
    createWindow()
  } catch (error) {
    dialog.showErrorBox('后端启动失败', error instanceof Error ? error.message : String(error))
    app.quit()
    return
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
})
