# 马医生 Code Security Scanner

[语言：**中文** | [English](README.en.md)]

基于 YASA 静态分析引擎 + LLM 的代码安全扫描平台。  
**核心创新：规则工坊 —— LLM 辅助的跨语言静态分析规则自动生成与迭代优化。**

## 快速使用

**网页版（推荐）：** 访问 [http://47.94.95.178](http://47.94.95.178)，注册账号即可，无需安装。

**桌面客户端：**
1. 从 [GitHub Releases](https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases) 下载安装包（`.exe` / `.dmg` / `.AppImage`）及 YASA 引擎（约 466MB）
2. 安装客户端，首次启动在配置页填写 YASA 引擎路径和 LLM API Key
3. 注册账号，开始使用（客户端账号与网页版独立）

---

## 功能一览

### 一、代码扫描

支持对本地代码路径或上传 ZIP 包进行安全漏洞扫描。

**支持语言：** Python / Java / Go / JavaScript / TypeScript / PHP / C

**双引擎：**

| 引擎 | 原理 | 特点 | 推荐场景 |
|------|------|------|---------|
| YASA | 污点追踪（Taint Analysis） | 深度追踪 source→sink 完整数据流，检出率高 | 安全审计、正式扫描 |
| Semgrep | 模式匹配（Pattern Matching） | 基于 AST 规则匹配，速度快 | 日常快速检查 |

**扫描规则模式：**

| 模式 | 说明 |
|------|------|
| minimal | 精简核心规则，速度快，适合日常 |
| full | 完整规则集，检出率更高，适合全面审计 |

**使用流程：**

1. 登录后进入扫描页
2. 选择输入方式：填写本地代码路径 或 上传 ZIP 包（最大 50MB）
3. 选择扫描引擎、语言（支持 auto 自动检测）、规则模式
4. 可选勾选个人规则集（在规则工坊中创建的自定义规则）
5. 点击扫描，后台异步执行，前端实时显示进度
6. 扫描完成后查看结构化漏洞报告

**报告内容包括：**
- 漏洞列表（按严重程度分类：Critical / High / Medium / Low）
- 每条漏洞的完整污点路径（source → 传播链 → sink）、触发文件和行号
- 代码片段预览
- 跨文件漏洞链分析（LLM 对整个项目的多条 findings 进行关联分析）

**报告 AI 辅助功能：**

| 功能 | 说明 |
|------|------|
| AI 二次研判 | 对单条漏洞判断是否为真实漏洞（而非误报），给出结论和理由 |
| 生成修复建议 | 输出修复说明、修复代码和攻击场景描述 |
| 可利用性评估 | 评估攻击路径、前置条件、PoC 提示、利用难度和影响范围 |
| 导出 HTML 报告 | 将完整报告导出为 HTML 文件 |

---

### 二、AI Agent 对话

通过自然语言与 AI Agent 交互，Agent 可自动调用工具完成复杂任务。

**支持的工具能力（20 个工具）：**

**扫描与报告：**
- 对本地项目路径执行漏洞扫描，支持指定语言、引擎、规则模式
- 查看最近扫描报告内容（最多 6000 字符）
- 列出历史扫描报告，支持按项目名过滤
- 将扫描报告标记为收藏永久保留

**CVE 情报查询：**
- 从 GitHub Advisory Database 按语言、漏洞类型、关键词搜索 CVE，覆盖 23 种漏洞类型（SQL 注入、命令注入、SSRF、路径穿越、XSS、反序列化、XXE、模板注入等）
- 查询 NVD 数据库（覆盖非开源软件漏洞）
- 检查 CVE 是否被 CISA KEV（已知被利用漏洞目录）收录
- 查询 OSV 数据库（检查指定包名和版本是否存在漏洞，支持 PyPI / npm / Maven / Go）
- 对多个 CVE 按 CVSS × EPSS × KEV 综合评分排序风险优先级
- 获取单个 CVE 完整情报：NVD 详情 + CVSS + EPSS 利用概率 + 综合风险评分

**规则生成：**
- 根据用户描述的漏洞特征生成 YASA 规则，支持传入代码片段辅助精确识别函数签名
- 根据 CVE ID 自动生成规则（查 Advisory → 提取特征 → 生成 → 入库）
- 批量从多个 GHSA ID 生成规则
- 根据用户反馈（如"误报太多"）迭代优化已生成的规则

**网络搜索：**
- Bing 网络搜索
- GitHub 仓库/代码/议题搜索（支持 `lang:python` 等语法）

**Git 操作：**
- 克隆 GitHub/GitLab 仓库到服务器临时目录后直接扫描
- 查看提交历史、commit diff、两版本代码对比（用于追踪漏洞引入和修复点）
- 列出仓库目录结构

**对话示例：**

```
「查 Python 最新的 SSRF 漏洞 CVE」
「帮我扫描 /home/user/myproject，用 YASA 引擎」
「克隆 github.com/xxx/yyy 然后扫描」
「这份报告的漏洞哪条最危险」
「根据 CVE-2024-1234 给我生成一条检测规则」
「上次的报告误报太多，帮我优化规则」
```

支持流式输出（SSE），对话记忆持久化，可通过 `conversation_id` 继续已有对话。  
支持上传代码文件（`.py .java .go .js .ts .c .php .zip`，最大 10MB）直接让 Agent 分析。

---

### 三、规则工坊（Rule Workshop）★

规则工坊是本项目的核心创新，实现了 **基于 LLM 的 4 阶段规则生成管道 + YASA 真实扫描评估 + 迭代优化闭环**。

#### 核心管线

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

#### 为什么 Stage 3 是关键

传统 LLM 方案只做"生成→自评"，无法知道规则在实际引擎上的表现。  
规则工坊的 Stage 3 把生成的规则写入临时 JSON → 调 YASA 引擎对测试用例做真实扫描 → 解析 SARIF 报告 → 与预期结果对比 → 算出精准的 TP/FP/FN。  
**LLM 拿到的是"3 个正确检出、1 个误报在第 25 行 os.system()、0 个漏报"这种具体数据，而非泛泛的"规则可能有问题"。**

#### 使用流程

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

#### 评估模式

| 模式 | Stage 3 | 适用场景 |
|------|---------|---------|
| 完整评估 | YASA 真实扫描 + 测试集对比 | 论文实验、规则质量验证 |
| 快速模式 | 仅 LLM 自评 | CVE 摄入、快速预览 |

配置测试集：在 `test-{lang}-cases/` 目录下放置源码 + `expected.json`，定义预期的漏洞类型和数量。无测试集时自动降级为快速模式。

---

## 项目结构

```
ma_yisheng/
├── main.py                        # FastAPI 入口
├── config.py                      # 配置管理（含多平台数据目录）
├── scanner.py                     # 双引擎扫描核心
├── sarif_parser.py                # SARIF 解析 + 去重
├── llm.py                         # LLM 调用（4-stage 管道函数）
├── rule_evaluator.py              # ★ 规则评估器（YASA扫描→对比预期→F1）
├── rule_generation_api.py         # 规则生成独立端点
├── agent.py / agent_tools.py      # Agent + 20个工具定义
├── report.py                      # 报告管理
├── auth.py / email_service.py     # 认证 + 邮件
│
├── app/
│   ├── routers/
│   │   ├── scan.py                # 扫描接口
│   │   ├── report.py              # 报告接口（含AI研判/修复/导出）
│   │   ├── chat.py                # Agent对话接口（含SSE流式）
│   │   ├── cve.py                 # CVE搜索/摄入/规则生成
│   │   ├── rule_sets.py           # 规则集 CRUD
│   │   └── config.py              # 配置读写（客户端设置页）
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
│   └── src/pages/
│       ├── SetupPage.tsx          # 首次配置引导页
│       └── SettingsPage.tsx       # 设置页
│
├── rules/                         # 官方规则库（6 语言 × full/minimal）
├── test-python-cases/             # 测试用例 + expected.json
├── server_requirements.txt
└── start_server.sh
```

---

## 自部署（开发者）

### 1. 获取引擎

YASA 引擎二进制约 466MB，从 [GitHub Release](https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases) 获取，放到独立目录。

### 2. 配置

```bash
cd ma_yisheng
cp .env.example .env
nano .env
```

| 配置项 | 是否必需 | 说明 |
|--------|---------|------|
| `LLM_API_KEY` | 必需 | LLM 接口密钥 |
| `LLM_MODEL` | 必需 | 模型名称 |
| `YASA_BUNDLE_PATH` | 必需 | YASA 引擎目录 |
| `JWT_SECRET` | 必需 | 随机字符串，生产环境必须修改 |
| `SMTP_HOST/USER/PASSWORD` | 必需 | 邮件（注册验证码） |
| `GITHUB_TOKEN` | 可选 | 提升 API 限流（5000/h vs 60/h） |
| `SEMGREP_RULES_PATH` | 可选 | 离线 Semgrep 规则目录 |

### 3. 启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r server_requirements.txt
bash start_server.sh
```

---

## License

MIT
