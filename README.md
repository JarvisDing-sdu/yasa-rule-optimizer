# 马医生 Code Security Scanner

[语言：**中文** | [English](README.en.md)]

基于 YASA 静态分析引擎 + LLM 的代码安全扫描平台。支持多语言漏洞扫描、CVE 驱动的规则自动生成、个人规则库管理，以及 AI Agent 对话式交互。

## 核心功能

- **代码漏洞扫描** — YASA（污点追踪）+ Semgrep（模式匹配）双引擎，支持 Python / Java / Go / JavaScript / PHP / C
- **AI Agent 对话** — 支持工具调用的 Agent 循环，可搜索 GitHub Advisory、生成规则、扫描项目，全程对话式交互
- **CVE 驱动的规则生成** — 搜索 GitHub Advisory Database → 选中 CVE → LLM 4 阶段管道自动生成 YASA 检测规则，支持 23 种漏洞类型（SQL 注入、命令注入、路径遍历、反序列化、SSRF、XSS、XXE、SSTI 等），覆盖 CWE ID 精确匹配 + 关键词模糊匹配
- **个人规则库** — 每个用户拥有独立规则空间，可克隆官方规则、自行生成规则、启用/禁用单条规则
- **扫描时规则选择** — 用户可从官方 + 个人规则库中自由选择要使用的规则集
- **报告系统** — JSON / SARIF / TXT 多格式报告，支持收藏、导出 HTML、AI 二次研判

## 快速开始

### 1. 配置环境

```bash
cd ma_yisheng
cp .env.example .env
# 编辑 .env，填写 LLM_API_KEY、SMTP 等必要配置
nano .env
```

必需配置项：

| 配置               | 说明                              |
| ------------------ | --------------------------------- |
| `LLM_API_KEY`      | LLM API 密钥（DeepSeek / OpenAI） |
| `LLM_BASE_URL`     | LLM API 地址                      |
| `LLM_MODEL`        | 模型名称                          |
| `YASA_BUNDLE_PATH` | YASA 引擎包路径                   |
| `JWT_SECRET`       | JWT 签名密钥（随机字符串）        |
| `SMTP_HOST`        | SMTP 邮件服务器（发送验证码）     |
| `SMTP_USER`        | SMTP 邮箱账号                     |
| `SMTP_PASSWORD`    | SMTP 密码 / App Password          |

可选配置：

| 配置                 | 说明                                              |
| -------------------- | ------------------------------------------------- |
| `GITHUB_TOKEN`       | GitHub Personal Access Token（提升 API 速率限制） |
| `SEMGREP_RULES_PATH` | Semgrep 离线规则目录（留空则联网拉取）            |
| `SCAN_TIMEOUT`       | 扫描超时秒数（默认 300）                          |
| `DISABLE_SWAGGER`    | 设为 1 关闭 /docs（生产环境建议开启）             |

### 2. 安装依赖

```bash
# 使用项目自带的虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install -r server_requirements.txt
```

### 3. 启动服务

```bash
source .venv/bin/activate
python3 main.py --host 0.0.0.0 --port 8000
```

或使用启动脚本：

```bash
bash start_server.sh
```

服务默认监听 `http://0.0.0.0:8000`。启动后访问：

- 扫描主页：`http://localhost:8000/`
- 规则工坊：`http://localhost:8000/rule-workshop`
- API 文档：`http://localhost:8000/docs`（生产环境建议 `DISABLE_SWAGGER=1` 关闭）

> **注意**：`users.db` 首次启动或首次注册时自动创建，无需手动建库。

## 工作流程

### 流程一：代码扫描

```
登录 → 选择扫描路径（本地路径或上传 zip）→ 选择语言/引擎/规则集 → 开始扫描 → 查看报告
```

1. 在主页登录（邮箱验证码注册 / 密码登录）
2. 输入项目路径（如 `/home/user/my-project`）或上传 zip 包
3. 选择扫描引擎（YASA 深但慢 / Semgrep 快但浅）和语言
4. 可选：勾选个人规则集（规则工坊中创建的）
5. 等待扫描完成，查看漏洞报告
6. 可对单条漏洞做 AI 二次研判、生成修复建议、导出 HTML 报告

### 流程二：CVE 驱动的规则构建

```
规则工坊 → 搜索 CVE → 选择目标 CVE → 选择/创建规则集 → 自动生成规则 → 去主页扫描
```

1. 访问 `/rule-workshop` 进入规则工坊
2. 左侧面板：选择语言和漏洞类型（支持 23 种），搜索 GitHub Advisory（自动分页拉取 500 条，CWE ID 精确匹配）
3. 勾选感兴趣的 CVE（支持多选）
4. 中间面板：查看 CVE 详情，选择或新建目标规则集
5. 点击「从选中 CVE 生成规则」→ 后端自动抓取 CVE 详情 → LLM 4 阶段管道生成规则 → 入库
6. 右侧面板可查看/管理规则集（启用/禁用/删除单条规则）
7. 回到主页扫描时，就能在规则集选择器中看到刚创建的规则

### 流程三：AI Agent 对话式操作

```
在聊天框描述需求 → Agent 判断并调用工具 → 返回结果 → 确认并执行
```

典型对话示例：

- 「帮我查一下 Python SSRF 的最新 CVE」→ Agent 自动调用 GitHub Advisory 搜索
- 「根据这几条 CVE 生成规则」→ Agent 调用规则构建管道，保存到个人规则库
- 「扫描 /home/user/my-project」→ Agent 调用扫描引擎，返回漏洞报告
- 「这份报告里有哪些高危漏洞？」→ Agent 读取报告，总结关键发现

Agent 会主动确认模糊描述（如「你指的是 Python 的 SQL 注入还是命令注入？」），不会凭猜测操作。

## 项目结构

```
ma_yisheng/
├── main.py                     # FastAPI 应用入口
├── config.py                   # 配置管理
├── auth.py                     # 用户认证（JWT + 邮箱验证码）
├── database.py                 # SQLite 数据库初始化
├── scanner.py                  # YASA / Semgrep 扫描核心
├── sarif_parser.py             # SARIF 报告解析 + 去重
├── llm.py                      # LLM 调用封装
├── report.py                   # 报告管理（JSON/TXT/HTML）
├── agent.py                    # Agent tool calling 循环
├── agent_tools.py              # Agent 工具定义
├── cve_intel.py                # CVE 情报（NVD/EPSS/KEV/OSV）
├── rule_generation_api.py      # 规则生成 API
├── email_service.py            # 邮件发送服务
├── git_tools.py                # Git 操作工具
├── chat.py                     # 旧版对话模块
├── scan.py                     # 旧版扫描模块
├── scan_service.py             # 扫描后台任务调度
├── app/                        # FastAPI 应用模块
│   ├── database.py             # SQLAlchemy 数据库配置
│   ├── deps.py                 # 共享依赖（DB、认证、任务存储）
│   ├── middleware/              # 中间件
│   │   ├── rate_limit.py       # 限流中间件
│   │   └── security.py         # 安全头中间件
│   ├── models/                 # SQLAlchemy 模型
│   │   ├── user.py             # 用户模型
│   │   ├── user_rule.py        # 规则集/规则模型
│   │   ├── conversation.py     # 对话记忆模型
│   │   └── scan_task.py        # 扫描任务模型
│   ├── routers/                # API 路由
│   │   ├── auth.py             # /api/auth/* 认证接口
│   │   ├── scan.py             # /api/scan/* 扫描接口
│   │   ├── report.py           # /api/reports/* 报告接口
│   │   ├── chat.py             # /api/chat/* 对话/Agent 接口
│   │   ├── rule_sets.py        # /api/rule-sets/* 规则集 CRUD
│   │   ├── cve.py              # /api/cve/* CVE 搜索/摄入
│   │   ├── health.py           # /api/health/* 健康检查
│   │   └── conversation.py     # 对话记忆管理
│   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── auth.py
│   │   ├── scan.py
│   │   └── rule_set.py
│   └── services/               # 业务逻辑
│       ├── scan_service.py     # 扫描后台任务
│       ├── rule_service.py     # 规则管理/CVE搜索/规则合并
│       └── memory.py           # 对话记忆管理
├── rules/                      # 官方规则库（JSON）
│   ├── rule_config_python_full.json
│   ├── rule_config_python_minimal.json
│   ├── rule_config_php_full.json
│   ├── rule_config_php_minimal.json
│   ├── rule_config_c_full.json
│   ├── rule_config_c_minimal.json
│   ├── rule_config_java_full.json
│   ├── rule_config_java_minimal.json
│   ├── rule_config_go_full.json
│   ├── rule_config_go_minimal.json
│   ├── rule_config_js_full.json
│   └── rule_config_js_minimal.json
├── static/                     # 静态文件
│   └── rule-workshop.html      # 规则工坊页面
├── frontend_src/               # 前端 React 源码（Vite）
├── frontend_dist/              # 前端构建产物
│   ├── index.html              # React SPA 主页
│   └── rule-workshop.html      # 规则工坊
├── uploads/                    # 上传文件临时目录
├── yasa_engine/                # YASA 引擎 SDK
├── .env                        # 环境配置（不入库）
├── .env.example                # 环境配置模板
├── server_requirements.txt     # Python 依赖
└── start_server.sh             # 启动脚本
```

## API 概览

所有 API 默认前缀 `/api`，需携带 JWT Token（`Authorization: Bearer <token>`）。

### 认证

| 接口                            | 说明           |
| ------------------------------- | -------------- |
| `POST /api/auth/send-code`      | 发送邮箱验证码 |
| `POST /api/auth/register`       | 验证码注册     |
| `POST /api/auth/login`          | 密码登录       |
| `POST /api/auth/reset-password` | 重置密码       |

### 扫描

| 接口                                      | 说明             |
| ----------------------------------------- | ---------------- |
| `POST /api/scan`                          | 扫描本地路径     |
| `POST /api/scan/upload`                   | 上传 zip 扫描    |
| `GET /api/scan/{task_id}`                 | 查询扫描进度     |
| `GET /api/tasks`                          | 历史任务列表     |
| `POST /api/scan/{task_id}/chain-analysis` | 跨文件漏洞链分析 |

### 报告

| 接口                                       | 说明           |
| ------------------------------------------ | -------------- |
| `GET /api/reports`                         | 报告列表       |
| `GET /api/reports/{path}/content`          | 报告内容       |
| `GET /api/reports/{path}/findings`         | 结构化漏洞列表 |
| `POST /api/reports/{path}/findings/review` | AI 二次研判    |
| `POST /api/reports/{path}/findings/fix`    | 修复建议       |
| `GET /api/reports/{path}/export`           | 导出 HTML      |
| `POST /api/reports/{path}/chat`            | 报告对话       |
| `GET /api/reports/{path}/chat/stream`      | 报告流式对话   |

### 规则集

| 接口                                           | 说明                |
| ---------------------------------------------- | ------------------- |
| `GET /api/rule-sets`                           | 列出官方+个人规则集 |
| `POST /api/rule-sets`                          | 创建规则集          |
| `GET /api/rule-sets/{id}`                      | 规则集详情+规则列表 |
| `DELETE /api/rule-sets/{id}`                   | 删除规则集          |
| `POST /api/rule-sets/{id}/clone-official`      | 克隆官方规则        |
| `PUT /api/rule-sets/{id}/rules/{db_id}/toggle` | 启用/禁用规则       |
| `DELETE /api/rule-sets/{id}/rules/{db_id}`     | 删除规则            |

### CVE

| 接口                            | 说明                                                         |
| ------------------------------- | ------------------------------------------------------------ |
| `GET /api/cve/search`           | 搜索 GitHub Advisory（支持 vuln_type/keyword/language/count） |
| `GET /api/cve/detail/{ghsa_id}` | CVE 详情                                                     |
| `POST /api/cve/ingest`          | 批量摄入 CVE 生成规则                                        |
| `POST /api/cve/generate-rules`  | 从漏洞描述直接生成规则                                       |

### Agent

| 接口                          | 说明                    |
| ----------------------------- | ----------------------- |
| `POST /api/chat/agent`        | Agent 对话（JSON 响应） |
| `POST /api/chat/agent/stream` | Agent 对话（SSE 流式）  |
| `POST /api/chat`              | 普通 LLM 对话           |
| `POST /api/chat/upload`       | 上传文件供 Agent 分析   |

### 健康检查

| 接口                        | 说明                             |
| --------------------------- | -------------------------------- |
| `GET /api/health`           | 服务健康状态（含数据库连接检查） |
| `GET /api/health/readiness` | 就绪检查                         |

## 部署注意事项

1. **YASA 引擎**：确保 `YASA_BUNDLE_PATH` 指向正确的引擎目录，引擎二进制需有执行权限
2. **邮件服务**：SMTP 配置必须正确，否则用户无法注册（Gmail 需使用 App Password）
3. **GitHub Token**：建议配置 `GITHUB_TOKEN`，未认证 API 限流为 60 次/小时，认证后 5000 次/小时
4. **JWT_SECRET**：生产环境务必修改为强随机字符串
5. **Swagger 文档**：生产环境建议 `DISABLE_SWAGGER=1` 关闭 `/docs`
6. **数据库**：`users.db` 自动创建，无需手动初始化；数据库文件不入版本控制
7. **前端**：前端构建产物在 `frontend_dist/`，由 FastAPI 直接 serve；源码在 `frrontend_src/` 使用 Vite 构建

## License

MIT
