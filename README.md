# 马医生 Code Security Scanner

[语言：**中文** | [English](README.en.md)]

基于 YASA 静态分析引擎 + LLM 的代码安全扫描平台。  
**核心创新：规则工坊 —— LLM 辅助的跨语言静态分析规则自动生成与迭代优化。**

---

## 用户使用方式

### 方式一：桌面客户端（推荐普通用户）

下载对应系统的安装包，双击安装，打开即用，**无需安装 Python 或配置后端**。

| 系统 | 安装包 | 说明 |
|------|--------|------|
| macOS | `Ma Yisheng.dmg` | 双击挂载，拖入 Applications |
| Windows | `Ma Yisheng Setup.exe` | 双击安装 |
| Linux | `Ma Yisheng.AppImage` | 赋予执行权限后双击运行 |

从 [GitHub Releases](https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases) 页面下载最新版本。

**首次启动流程：**

1. 打开应用，会自动进入「环境配置」页
2. 填写必要配置（LLM API Key、YASA 引擎路径等）
3. 保存后进入登录页，注册账号
4. 开始使用

> 客户端内置后端，启动时自动拉起，无需用户手动操作。每台设备的账号数据独立存储，不与网页版共享。

---

### 方式二：网页版（服务器部署 / 开发者）

后端部署到服务器后，用户通过浏览器访问，多人共享同一个账号数据库。

**启动步骤：**

```bash
cd ma_yisheng
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r server_requirements.txt
cp .env.example .env
nano .env                          # 填写必要配置
bash start_server.sh
```

浏览器访问 `http://localhost:8000`，注册账号后即可使用。

**必填配置（.env）：**

| 配置项 | 说明 |
|--------|------|
| `LLM_API_KEY` | LLM 接口密钥 |
| `LLM_MODEL` | 模型名称 |
| `YASA_BUNDLE_PATH` | YASA 引擎目录（约 466MB，从 Release 下载） |
| `JWT_SECRET` | 随机字符串，生产环境必须修改 |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | 邮件（用于注册验证码） |

---

## 功能概览

### 代码扫描

1. 登录后，输入本地代码路径或上传 ZIP 包
2. 选择扫描引擎（YASA 深度 / Semgrep 快速）和语言
3. 等待扫描完成，查看结构化漏洞报告
4. 可使用 AI 对单条漏洞进行二次研判、生成修复建议、导出 HTML 报告

| 引擎 | 方法 | 特点 |
|------|------|------|
| YASA | 污点追踪 | 深但慢，适合安全审计 |
| Semgrep | 模式匹配 | 快但浅，适合日常检查 |

支持语言：Python / Java / Go / JavaScript / TypeScript / PHP / C

### 规则工坊（核心创新）★

基于 LLM 的 4 阶段规则生成管道，从 CVE 描述自动生成并优化 YASA 扫描规则。

```
CVE 描述 → [LLM 分析] → [LLM 生成规则] → [YASA 真实扫描评估] → [LLM 优化] → 迭代至 F1 ≥ 0.85
```

访问 `/rule-workshop` 使用。

### AI Agent 对话

```
聊天框描述需求 → Agent 调用工具 → 返回结果
```

示例：「查 Python SSRF 最新 CVE」、「扫描 /home/user/project」、「这份报告有哪些高危漏洞」

---

## 开发者：打包客户端

> 打包需要先用 PyInstaller 将 Python 后端编译为单文件可执行程序，再用 electron-builder 打包桌面安装包。

### 第一步：打包 Python 后端

```bash
cd ma_yisheng
pip install pyinstaller
pyinstaller --onefile --name ma-yisheng-backend \
  --add-data rules:rules \
  --add-data static:static \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  main.py
# 产物：ma_yisheng/dist/ma-yisheng-backend（或 .exe）
```

### 第二步：打包桌面安装包

```bash
cd ma_yisheng/frontend_src
npm install

# macOS（需在 Mac 上运行）
npm run dist:dmg

# Windows（需在 Windows 上运行）
npm run dist:win

# Linux（需在 Linux 上运行）
npm run dist:linux
```

产物输出到 `ma_yisheng/frontend_src/release/` 目录，上传到 GitHub Releases 供用户下载。

> **注意：** 每个平台只能在对应系统上打包。推荐使用 GitHub Actions 自动化三平台打包。

---

## 项目结构

```
ma_yisheng/
├── main.py                        # FastAPI 入口
├── config.py                      # 配置管理（含多平台数据目录）
├── scanner.py                     # 双引擎扫描核心
├── sarif_parser.py                # SARIF 解析 + 去重
├── llm.py                         # LLM 调用（4-stage 管道）
├── rule_evaluator.py              # ★ 规则评估器（YASA扫描→对比预期→F1）
├── rule_generation_api.py         # 规则生成端点
├── agent.py / agent_tools.py      # Agent + 工具定义
├── report.py                      # 报告管理
├── auth.py / email_service.py     # 认证 + 邮件
│
├── app/
│   ├── routers/                   # API 路由
│   │   ├── auth.py, scan.py, report.py, chat.py
│   │   ├── cve.py                 # CVE 搜索/摄入
│   │   ├── rule_sets.py           # 规则集 CRUD
│   │   └── config.py              # 配置读写（供客户端设置页使用）
│   ├── services/
│   │   ├── rule_service.py        # ★ 规则管道 + 迭代优化
│   │   └── scan_service.py        # 后台扫描调度
│   ├── models/                    # SQLAlchemy 模型
│   └── middleware/                # rate_limit / security
│
├── frontend_src/                  # React + Electron 前端
│   ├── electron/
│   │   ├── main.cjs               # Electron 主进程（自动拉起后端）
│   │   └── preload.cjs            # 渲染进程桥接
│   └── src/
│       ├── pages/
│       │   ├── SetupPage.tsx      # 首次配置引导页
│       │   ├── SettingsPage.tsx   # 设置页（含清除登录锁定）
│       │   └── ...
│       └── components/
│           └── ConfigGate.tsx     # 配置完整性检查
│
├── rules/                         # 官方规则库（6 语言 × full/minimal）
├── test-python-cases/             # 测试用例 + expected.json
├── server_requirements.txt
└── start_server.sh
```

---

## 客户端数据目录

客户端数据不写入安装目录，存储在用户目录下：

| 系统 | 数据目录 |
|------|---------|
| macOS | `~/Library/Application Support/MaYisheng/` |
| Windows | `%APPDATA%\MaYisheng\` |
| Linux | `~/.local/share/ma-yisheng/` |

包含：`.env`（配置）、`users.db`（账号）、`yasa-reports/`（扫描报告）

---

## API 概览

### 扫描
| 接口 | 说明 |
|------|------|
| `POST /api/scan` | 扫描本地路径 |
| `POST /api/scan/upload` | 上传 ZIP 扫描 |
| `GET /api/scan/{task_id}` | 查询进度 |
| `GET /api/tasks` | 历史列表 |

### 报告
| 接口 | 说明 |
|------|------|
| `GET /api/reports` | 报告列表 |
| `GET /api/reports/{path}/findings` | 结构化漏洞列表 |
| `POST /api/reports/{path}/findings/review` | AI 二次研判 |
| `GET /api/reports/{path}/export` | 导出 HTML |

### 规则工坊
| 接口 | 说明 |
|------|------|
| `GET /api/cve/search` | 搜索 GitHub Advisory |
| `POST /api/cve/ingest` | 批量摄入 CVE → 生成规则 |
| `GET /api/rule-sets` | 规则集列表 |
| `POST /api/rule-sets` | 创建规则集 |
| `PUT /api/rule-sets/{id}/rules/{db_id}/toggle` | 启用/禁用规则 |

### 认证
| 接口 | 说明 |
|------|------|
| `POST /api/auth/send-code` | 发送验证码 |
| `POST /api/auth/register` | 注册 |
| `POST /api/auth/login` | 登录 |

API 文档：`http://localhost:8000/docs`

---

## License

MIT
