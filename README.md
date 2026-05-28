# 马医生 Code Security Scanner

[语言：**中文** | [English](README.en.md)]

基于 YASA 静态分析引擎 + LLM 的代码安全扫描平台。
**核心创新：规则工坊 —— LLM 辅助的跨语言静态分析规则自动生成与迭代优化。**

## 规则工坊（Rule Workshop）★

规则工坊是本项目的学术创新点，实现了 **基于 LLM 的 4 阶段规则生成管道 + YASA 真实扫描评估 + 迭代优化闭环**。将论文中"LLM 辅助静态分析规则生成与优化"方法落地为完整工程系统。

### 核心管线

```
漏洞案例 / CVE 描述
  │
  ├─[Stage 1] LLM 分析     → 结构化漏洞描述（source/sink/触发条件/数据流）
  ├─[Stage 2] LLM 生成     → YASA 规则 JSON（checkerIds/sources/sinks/bridge）
  ├─[Stage 3] YASA 扫描评估 → 跑真实引擎、对比测试集 → TP/FP/FN/Precision/Recall/F1
  ├─[Stage 4] LLM 优化     → 根据评估数据精准调整 fsig/args/attribute/scope
  │
  └─ 迭代 Stage 3→4 直到 F1 ≥ 0.85 或 3 轮无改进
```

### 为什么 Stage 3 是关键

传统 LLM 方案只做"生成→自评"，LLM 不知道生成的规则在实际引擎上跑出来是什么效果。
规则工坊的 Stage 3 把生成的规则写入临时 JSON → 调 YASA 引擎（466MB 二进制）对测试用例做真实扫描 → 解析 SARIF 报告 → 与预期结果对比 → 算出精准的 TP/FP/FN。
**LLM 拿到的是"3 个正确检出、1 个误报在第 25 行 os.system()、0 个漏报"这种具体数据，而非泛泛的"规则可能有问题"。**

### 规则工坊使用流程

```
访问 /rule-workshop
  │
  ├─ 左侧面板：搜索 CVE
  │   └─ 按语言/漏洞类型/关键词搜索 GitHub Advisory
  │       CWE ID 精确匹配 + 23 种漏洞类型覆盖
  │
  ├─ 中间面板：生成规则
  │   ├─ 勾选目标 CVE → 查看详情（描述/影响版本/修复方案）
  │   ├─ 选择或新建规则集
  │   └─ 点击生成 → 后端自动：抓取CVE详情 → 4阶段管道 → 校验 → 入库
  │
  └─ 右侧面板：管理规则
      ├─ 规则集列表（官方 + 个人）
      ├─ 克隆官方规则 / 创建空规则集
      ├─ 查看单条规则详情（source/sink 定义）
      └─ 启用/禁用/删除单条规则
```

### 评估模式

| 模式 | Stage 3 | 适用场景 |
|------|---------|---------|
| 完整评估 | YASA 真实扫描 + 测试集对比 | 论文实验、规则质量验证 |
| 快速模式 | 仅 LLM 自评 | CVE 摄入、快速预览 |

配置测试集：在 `test-{lang}-cases/` 目录下放置源码 + `expected.json`，定义预期的漏洞类型和数量。无测试集时自动降级为快速模式。

### 效率设计

- 规则哈希缓存：同规则不重复扫描
- 测试用例单文件小样本：秒级扫描
- 迭代有明确停止条件（F1 达标 / 无改进）
- Stage 3 可选：`build_rule_pipeline_simple()` 跳过扫描

---

## 代码扫描

### 双引擎

| 引擎 | 方法 | 特点 |
|------|------|------|
| YASA | 污点追踪（Taint Analysis） | 深但慢，追踪 source→sink 完整数据流 |
| Semgrep | 模式匹配（Pattern Matching） | 快但浅，正则+AST 模式 |

### 支持语言

Python / Java / Go / JavaScript / TypeScript / PHP / C

### 扫描流程

```
登录 → 输入项目路径（或上传 zip）→ 选择引擎/语言/规则模式
   → 可选：勾选个人规则集 → 扫描 → 查看结构化漏洞报告
   → AI 二次研判 / 生成修复建议 / 导出 HTML
```

---

## AI Agent 对话

```
聊天框描述需求 → Agent 调用工具 → 返回结果
```

- 「查 Python SSRF 最新 CVE」→ GitHub Advisory 搜索
- 「根据 CVE-2024-xxx 生成规则」→ 4 阶段管道
- 「扫描 /home/user/project」→ 调用扫描引擎
- 「这份报告有哪些高危漏洞」→ 报告分析

---

## 快速开始

### 1. 获取引擎

引擎二进制约 466MB，从 [GitHub Release](https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases) 获取，放到独立目录。

### 2. 配置

```bash
cd ma_yisheng
cp .env.example .env
nano .env
```

必需：`LLM_API_KEY`、`LLM_MODEL`、`YASA_BUNDLE_PATH`、`JWT_SECRET`、SMTP 配置。

可选：`GITHUB_TOKEN`（提升 API 限流）、`SEMGREP_RULES_PATH`（离线规则）、`SCAN_TIMEOUT`。

### 3. 安装与启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r server_requirements.txt
bash start_server.sh     # → http://localhost:8000
```

- 扫描主页：`http://localhost:8000/`
- **规则工坊**：`http://localhost:8000/rule-workshop`
- API 文档：`http://localhost:8000/docs`

---

## 项目结构

```
ma_yisheng/                        # 所有运行代码
├── main.py                        # FastAPI 入口
├── config.py                      # 配置管理
├── scanner.py                     # 双引擎扫描核心
├── sarif_parser.py                # SARIF 解析 + 去重
├── llm.py                         # LLM 调用（4-stage 管道函数）
├── rule_evaluator.py              # ★ 规则评估器（YASA扫描→对比预期→F1）
├── rule_generation_api.py         # 规则生成独立端点
├── agent.py / agent_tools.py      # Agent + 工具定义
├── report.py                      # 报告管理
├── auth.py / email_service.py     # 认证 + 邮件
│
├── app/
│   ├── routers/                   # API 路由
│   │   ├── auth.py, scan.py, report.py, chat.py
│   │   ├── cve.py                 # CVE 搜索/摄入
│   │   └── rule_sets.py           # 规则集 CRUD
│   ├── services/
│   │   ├── rule_service.py        # ★ 规则管道 + 迭代优化
│   │   └── scan_service.py        # 后台扫描调度
│   ├── models/                    # SQLAlchemy 模型
│   └── middleware/                # rate_limit / security
│
├── rules/                         # 官方规则库（6 语言 × full/minimal）
├── test-python-cases/             # 测试用例 + expected.json
├── frontend_src/                  # React 前端（Vite）
├── .env.example
├── server_requirements.txt
└── start_server.sh
```

---

## API 概览

### 规则工坊

| 接口 | 说明 |
|------|------|
| `GET /api/cve/search` | 搜索 GitHub Advisory（CWE/关键词/语言） |
| `GET /api/cve/detail/{ghsa_id}` | CVE 详情 |
| `POST /api/cve/ingest` | 批量摄入 CVE → 4 阶段管道 → 入库 |
| `POST /api/cve/generate-rules` | 从漏洞描述直接生成规则 |
| `GET /api/rule-sets` | 列出规则集 |
| `POST /api/rule-sets` | 创建规则集 |
| `POST /api/rule-sets/{id}/clone-official` | 克隆官方规则 |
| `PUT /api/rule-sets/{id}/rules/{db_id}/toggle` | 启用/禁用 |

### 扫描

| 接口 | 说明 |
|------|------|
| `POST /api/scan` | 扫描路径 |
| `POST /api/scan/upload` | 上传 zip 扫描 |
| `GET /api/scan/{task_id}` | 查询进度 |
| `GET /api/tasks` | 历史列表 |

### 报告

| 接口 | 说明 |
|------|------|
| `GET /api/reports` | 报告列表 |
| `GET /api/reports/{path}/findings` | 结构化的漏洞列表 |
| `POST /api/reports/{path}/findings/review` | AI 二次研判 |
| `GET /api/reports/{path}/export` | 导出 HTML |

### Agent

| 接口 | 说明 |
|------|------|
| `POST /api/chat/agent` | Agent 对话 |
| `POST /api/chat/agent/stream` | Agent 流式 |
| `POST /api/chat/upload` | 上传文件分析 |

### 认证

| 接口 | 说明 |
|------|------|
| `POST /api/auth/send-code` | 发送验证码 |
| `POST /api/auth/register` | 注册 |
| `POST /api/auth/login` | 登录 |

---

## 部署注意事项

1. **引擎**：466MB 二进制，从 GitHub Release 获取；包含 C/PHP checker 支持
2. **测试集**：规则工坊 Stage 3 评估需要 `test-*-cases/expected.json`，无则自动降级
3. **GitHub Token**：未认证限流 60/h，认证后 5000/h
4. **SMTP**：Gmail 需 App Password
5. **JWT_SECRET**：生产环境务必修改

## License

MIT
