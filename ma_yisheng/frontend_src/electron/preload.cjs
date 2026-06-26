const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('maYisheng', {
  apiBase: `http://127.0.0.1:${process.env.MA_YISHENG_PORT || '8000'}`,
  log: (message) => ipcRenderer.send('renderer-log', String(message)),
  showPath: (targetPath) => ipcRenderer.invoke('show-path', String(targetPath)),
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
})
