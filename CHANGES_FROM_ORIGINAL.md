# Changes From Original Version

本文档记录当前版本相对最初版本的主要改动，重点说明功能差异、涉及文件和运行方式变化。

## 1. 应用形态

### 最初版本

- 主要是 Web 前端 + 后端服务。
- 前端需要通过浏览器访问。
- 用户需要自己启动后端，前端不会自动拉起服务。
- 打包前端只能得到静态 Web 资源，不是可直接打开的桌面 App。

### 当前版本

- 增加 Electron 桌面壳。
- 打开 `Ma Yisheng.app` 后会自动启动内置后端。
- 前端通过本地 `127.0.0.1:8000` 调用后端。
- 后端以 PyInstaller 单文件形式打包进 App。
- 运行数据不写进 `.app` 内部，而写入用户目录：

```text
~/Library/Application Support/app/runtime
```

主要新增/修改文件：

- `ma_yisheng/frontend_src/electron/main.cjs`
- `ma_yisheng/frontend_src/electron/preload.cjs`
- `ma_yisheng/frontend_src/package.json`
- `ma_yisheng/frontend_src/vite.config.ts`
- `ma_yisheng/ma-yisheng-backend.spec`

当前 App 输出位置：

```text
ma_yisheng/frontend_src/release/mac-arm64/Ma Yisheng.app
```

## 2. 本地运行数据目录

### 最初版本

- `.env`、`users.db`、报告目录等倾向于写在项目目录。
- 打包成 App 后，写入 App 内部或源码目录会不稳定，也不符合桌面应用习惯。

### 当前版本

- 增加统一运行数据目录：

```text
~/Library/Application Support/app/runtime
```

- `.env` 路径：

```text
~/Library/Application Support/app/runtime/.env
```

- 用户数据库：

```text
~/Library/Application Support/app/runtime/users.db
```

- 报告目录：

```text
~/Library/Application Support/app/runtime/yasa-reports
```

主要修改文件：

- `ma_yisheng/config.py`
- `ma_yisheng/auth.py`
- `ma_yisheng/database.py`
- `ma_yisheng/app/database.py`

## 3. 首次配置和环境配置页

### 最初版本

- 启动后直接进入登录/主界面。
- 如果 `.env` 没配好，登录、发邮件、扫描可能直接失败。
- 用户需要手动编辑 `.env`。

### 当前版本

- 增加配置检查入口。
- 如果缺少必要配置，会先进入配置页。
- 可以在界面中配置：
  - YASA 引擎目录
  - YASA 可执行文件名
  - UAST 文件名
  - LLM Provider / Base URL / API Key / Model
  - Semgrep 离线规则目录
  - GitHub Token
  - 扫描超时
  - SMTP 邮件配置
- 保存后写入 runtime `.env`。

主要新增/修改文件：

- `ma_yisheng/app/routers/config.py`
- `ma_yisheng/frontend_src/src/api/config.ts`
- `ma_yisheng/frontend_src/src/components/ConfigGate.tsx`
- `ma_yisheng/frontend_src/src/pages/SetupPage.tsx`
- `ma_yisheng/frontend_src/src/pages/SettingsPage.tsx`
- `ma_yisheng/frontend_src/src/App.tsx`

## 4. 邮件服务配置

### 最初版本

- SMTP 配置能力较弱。
- 邮件发送默认走 STARTTLS。
- 使用 465 端口时容易出现连接被关闭，例如：

```text
Connection unexpectedly closed
```

### 当前版本

- 增加 `SMTP_SECURITY` 配置：
  - `auto`
  - `ssl`
  - `starttls`
  - `none`
- `auto` 模式下：
  - `465` 自动走 SSL
  - 其他端口默认 STARTTLS
- 配置页增加“测试邮件”按钮。

主要修改文件：

- `ma_yisheng/email_service.py`
- `ma_yisheng/config.py`
- `ma_yisheng/app/routers/auth.py`
- `ma_yisheng/app/routers/config.py`
- `ma_yisheng/frontend_src/src/pages/SettingsPage.tsx`

## 5. 登录锁定处理

### 最初版本

- 登录失败次数过多后会被锁定。
- 没有界面按钮清理本地锁定状态。

### 当前版本

- 环境配置页增加“清除登录锁定”按钮。
- 后端新增接口清理本机 `login_attempts` 记录。

主要新增/修改文件：

- `ma_yisheng/app/routers/config.py`
- `ma_yisheng/frontend_src/src/api/config.ts`
- `ma_yisheng/frontend_src/src/pages/SettingsPage.tsx`

## 6. 路由和白屏问题

### 最初版本

- 使用 `BrowserRouter`。
- 打包成 file-based Electron App 后，刷新或进入子路径容易出现空白页或 404。
- 规则工坊跳转到后端路径后，404 时不容易返回。

### 当前版本

- 前端改为 `HashRouter`。
- Vite `base` 改为 `./`，适配 Electron `loadFile()`。
- 增加全局错误边界和 renderer 日志上报。
- 规则工坊纳入 App 路由，不再直接替换当前窗口到后端 URL。

主要新增/修改文件：

- `ma_yisheng/frontend_src/src/App.tsx`
- `ma_yisheng/frontend_src/vite.config.ts`
- `ma_yisheng/frontend_src/src/components/ErrorBoundary.tsx`
- `ma_yisheng/frontend_src/src/main.tsx`
- `ma_yisheng/frontend_src/src/pages/RuleWorkshopPage.tsx`
- `ma_yisheng/frontend_src/src/components/layout/AppLayout.tsx`

## 7. 报告展示和报告定位

### 最初版本

- 扫描完成后报告位置不明显。
- 任务列表只在部分成功场景下显示“查看报告”。
- 多语言扫描只显示第一份报告。
- 报告目录在 App runtime 下，用户不容易找到。

### 当前版本

- 任务列表支持展示多份报告。
- 成功报告和失败诊断报告区分显示：
  - `查看报告`
  - `查看诊断`
- 报告列表显示报告目录路径。
- 报告列表和详情页增加“目录/打开目录”能力，可以在 Finder 中定位。
- 报告详情页显示报告目录。
- 如果没有结构化 findings，但有原始输出，会展示原始输出。

主要新增/修改文件：

- `ma_yisheng/frontend_src/src/components/scan/TaskList.tsx`
- `ma_yisheng/frontend_src/src/pages/ReportsPage.tsx`
- `ma_yisheng/frontend_src/src/pages/ReportDetailPage.tsx`
- `ma_yisheng/frontend_src/electron/main.cjs`
- `ma_yisheng/frontend_src/electron/preload.cjs`
- `ma_yisheng/frontend_src/src/types/global.d.ts`
- `ma_yisheng/app/routers/report.py`

## 8. 本地路径扫描

### 最初版本

- 前端已有路径扫描接口，但 UI 默认偏向上传 ZIP。
- 在桌面 App 场景中，用户需要手动复制目录路径。

### 当前版本

- 扫描表单默认打开“本地路径”模式。
- 增加“选择文件夹”按钮。
- Electron 主进程使用系统目录选择器返回本地路径。
- 选择目录后直接走现有 `/api/scan` 路径扫描接口。
- 上传 ZIP 功能仍保留。

主要修改文件：

- `ma_yisheng/frontend_src/src/components/scan/ScanForm.tsx`
- `ma_yisheng/frontend_src/electron/main.cjs`
- `ma_yisheng/frontend_src/electron/preload.cjs`
- `ma_yisheng/frontend_src/src/types/global.d.ts`

## 9. PHP/C/Python 扫描失败诊断

### 最初版本

- YASA 子进程失败时，后端只在 `ok=true` 时保存报告。
- 如果 YASA 异常退出，前端只显示“无报告”或空错误。
- Electron 环境变量可能影响外部 Node/pkg 类扫描器，使其只输出类似：

```text
Node.js v18.5.0
```

### 当前版本

- 启动 YASA/Semgrep 前清理 Electron/Node 相关环境变量：
  - `ELECTRON_RUN_AS_NODE`
  - `ELECTRON_NO_ATTACH_CONSOLE`
  - `ELECTRON_ENABLE_LOGGING`
  - `NODE_OPTIONS`
  - `NODE_PATH`
  - npm lifecycle 相关变量
- YASA 非 0 退出时返回明确错误：

```text
YASA 退出码 <code>
```

- 只要有 `report_dir`，即使扫描失败也写入报告文件，作为诊断报告。

主要修改文件：

- `ma_yisheng/scanner.py`
- `ma_yisheng/app/services/scan_service.py`
- `ma_yisheng/scan_service.py`
- `ma_yisheng/frontend_src/src/components/scan/TaskList.tsx`
- `ma_yisheng/frontend_src/src/pages/ReportDetailPage.tsx`

## 10. 前端资源和 SVG 报错体验

### 最初版本

- 页面里有复杂 SVG 资源。
- 某些 SVG path 片段会被用户误认为运行错误。

### 当前版本

- 删除部分默认 Vite/React 资源。
- 替换 favicon。
- 减少复杂 SVG 内容暴露。

主要修改/删除文件：

- `ma_yisheng/frontend_src/public/favicon.svg`
- `ma_yisheng/frontend_src/public/icons.svg`
- `ma_yisheng/frontend_src/src/assets/react.svg`
- `ma_yisheng/frontend_src/src/assets/vite.svg`
- `ma_yisheng/frontend_src/index.html`

## 11. 构建命令

### 前端构建

```bash
cd ma_yisheng/frontend_src
npm run build
```

### 后端单文件构建

```bash
cd ma_yisheng
/usr/bin/env PYINSTALLER_CONFIG_DIR=/Users/infinite/yasa-rule-optimizer/ma_yisheng/.pyinstaller-cache \
  .venv/bin/pyinstaller \
  --clean \
  --runtime-tmpdir /tmp \
  --workpath build \
  --distpath dist \
  --name ma-yisheng-backend \
  --onefile \
  --add-data rules:rules \
  --add-data static:static \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  main.py
```

### macOS App 构建

```bash
cd ma_yisheng/frontend_src
npm run dist
```

输出：

```text
ma_yisheng/frontend_src/release/mac-arm64/Ma Yisheng.app
```

## 12. 生成产物和不应重点审查的文件

本次工作产生了一些构建产物和系统缓存，不属于核心源码逻辑：

- `ma_yisheng/build/`
- `ma_yisheng/dist/`
- `ma_yisheng/frontend_src/release/`
- `ma_yisheng/.pyinstaller-cache/`
- `ma_yisheng/app/services/__pycache__/`
- `.DS_Store`
- `ma_yisheng/.DS_Store`

如果后续提交代码，建议把构建产物、系统文件和缓存排除在提交之外。

## 13. 当前使用方式

1. 完全退出旧 App。
2. 打开：

```text
ma_yisheng/frontend_src/release/mac-arm64/Ma Yisheng.app
```

3. 首次启动先填写环境配置。
4. 扫描 GitHub 项目：
   - 先 `git clone` 到本地。
   - 在 App 扫描页选择“本地路径”。
   - 点击“选择文件夹”选择仓库目录。
   - 选择语言和引擎后开始扫描。

