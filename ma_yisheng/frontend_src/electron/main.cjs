const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const net = require('net')
const path = require('path')
const fs = require('fs')

let API_PORT = process.env.MA_YISHENG_PORT || '8000'
let API_BASE = `http://127.0.0.1:${API_PORT}`
let backendProcess = null
let logFile = null
let backendExit = null

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

function cleanupBundledRuntimeLogs(backendBin) {
  if (!backendBin) return
  const bundledLogPath = path.join(path.dirname(backendBin), 'logs')
  try {
    if (!fs.existsSync(bundledLogPath)) return
    const stat = fs.lstatSync(bundledLogPath)
    if (stat.isDirectory() && !stat.isSymbolicLink()) {
      fs.rmSync(bundledLogPath, { recursive: true, force: true })
      log(`Removed bundled runtime logs: ${bundledLogPath}`)
    }
  } catch (error) {
    log(`Failed to remove bundled runtime logs: ${error.message}`)
  }
}

function canListen(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => {
      server.close(() => resolve(true))
    })
    server.listen(Number(port), '127.0.0.1')
  })
}

async function chooseApiPort() {
  const preferred = Number(process.env.MA_YISHENG_PORT || '8000')
  const candidates = [preferred]
  for (let port = 8001; port <= 8099; port += 1) {
    if (!candidates.includes(port)) {
      candidates.push(port)
    }
  }
  for (const port of candidates) {
    if (await canListen(port)) {
      API_PORT = String(port)
      API_BASE = `http://127.0.0.1:${API_PORT}`
      process.env.MA_YISHENG_PORT = API_PORT
      return API_PORT
    }
  }
  throw new Error('8000-8099 端口都被占用，无法启动本地后端')
}

function waitForBackend(timeoutMs = 90000) {
  const startedAt = Date.now()

  return new Promise((resolve, reject) => {
    const check = () => {
      if (backendExit) {
        const detail = `后端进程已退出：code=${backendExit.code ?? 'null'}, signal=${backendExit.signal ?? 'null'}`
        const suffix = logFile ? `\n日志：${logFile}` : ''
        reject(new Error(`${detail}${suffix}`))
        return
      }

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
        const suffix = logFile ? `\n日志：${logFile}` : ''
        reject(new Error(`后端启动超时${suffix}`))
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
  backendExit = null

  const env = {
    ...process.env,
    API_HOST: '127.0.0.1',
    API_PORT,
    APP_MODE: 'desktop',
    CONFIG_UI_ENABLED: '1',
    SERVER_URL: '',
    ALLOWED_ORIGINS: '',
    MA_YISHENG_DATA_DIR: path.join(app.getPath('userData'), 'runtime'),
  }
  fs.mkdirSync(env.MA_YISHENG_DATA_DIR, { recursive: true })
  const runtimeLogDir = path.join(env.MA_YISHENG_DATA_DIR, 'logs')
  fs.mkdirSync(runtimeLogDir, { recursive: true })
  env.LOG_DIR = runtimeLogDir
  env.YASA_LOG_DIR = runtimeLogDir
  env.MA_YISHENG_LOG_DIR = runtimeLogDir
  logFile = path.join(env.MA_YISHENG_DATA_DIR, 'backend.log')
  cleanupBundledRuntimeLogs(backendBin)
  log(`Starting backend, port=${API_PORT}, bin=${backendBin || ''}, dir=${backendDir || ''}, cwd=${env.MA_YISHENG_DATA_DIR}`)
  const out = fs.openSync(logFile, 'a')

  if (backendBin) {
    backendProcess = spawn(backendBin, ['--host', '127.0.0.1', '--port', API_PORT], {
      cwd: env.MA_YISHENG_DATA_DIR,
      env,
      stdio: ['ignore', out, out],
    })
  } else if (backendDir) {
    backendProcess = spawn('python3', ['main.py', '--host', '127.0.0.1', '--port', API_PORT], {
      cwd: env.MA_YISHENG_DATA_DIR,
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
    backendExit = { code, signal }
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
    await chooseApiPort()
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
