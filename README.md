# 马医生 · Code Security Scanner

<p>
  <a href="http://47.94.95.178">网页版</a> ·
  <a href="https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases">下载客户端</a> ·
  <a href="README.en.md">English</a>
</p>

基于 YASA 静态分析引擎与 LLM 的代码安全扫描平台，支持 Web 端与桌面客户端双端使用。

---

## 核心功能

- **双引擎扫描** — YASA 污点追踪 + Semgrep 模式匹配，支持 Python / Java / Go / JavaScript / TypeScript / PHP / C 七种语言
- **AI 安全助手** — 自然语言交互，可搜索 CVE、克隆仓库、执行扫描、分析报告，支持深度思考模式
- **规则工坊** — 从 CVE 描述自动生成 YASA 检测规则，LLM 生成 + 真实引擎评估 + 迭代优化闭环
- **报告 AI 增强** — 漏洞真伪研判、一键生成修复代码、可利用性评估与攻击路径分析

---

## 快速开始

**网页版**：直接访问 [http://47.94.95.178](http://47.94.95.178)，注册账号即可使用，无需安装任何软件。

**桌面客户端**：

1. 从 [Releases](https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases) 页面下载对应系统的安装包（`.exe` / `.dmg` / `.AppImage`）
2. 从同一页面单独下载 YASA 引擎包（约 466MB），解压到本地任意目录
3. 安装并打开客户端，首次启动按引导填写 YASA 引擎路径和 LLM API Key
4. 注册账号，开始使用

> 桌面客户端内置后端，打开即自动启动，无需额外配置服务器。账号与报告数据存储在本机，与网页版相互独立。

---

## 使用说明

### 代码扫描

进入**扫描控制台**，选择输入方式：

- **上传 ZIP 包**：将代码压缩后上传（最大 50MB）
- **本地路径**：在客户端中点击「选择文件夹」，直接选择本机代码目录

配置扫描参数后提交，后台异步执行，实时显示进度。

| 选项 | 说明 |
|------|------|
| 引擎：YASA | 污点追踪，深度追踪数据流从输入到危险调用的完整路径，适合安全审计 |
| 引擎：Semgrep | AST 模式匹配，速度快，适合日常快速检查 |
| 规则模式：minimal | 精简核心规则，速度快 |
| 规则模式：full | 完整规则集，检出率更高 |
| 个人规则集 | 可叠加在规则工坊中生成的自定义规则 |

扫描完成后，报告按严重程度（Critical / High / Medium / Low）分类展示，每条漏洞含完整污点路径、触发文件和行号、代码片段预览。

### 报告 AI 增强

在报告详情页，可对每条漏洞使用以下 AI 功能：

| 功能 | 说明 |
|------|------|
| **AI 研判** | 判断是否为真实漏洞还是误报，给出结论与理由 |
| **修复建议** | 生成修复说明、修复代码示例和攻击场景描述 |
| **可利用性评估** | 分析攻击路径、前置条件、利用难度和影响范围 |
| **导出报告** | 将完整报告导出为 HTML 文件 |

### AI 安全助手

在**对话页**通过自然语言提问，AI 助手会自动选择工具完成任务。支持上传代码文件（`.py .java .go .js .ts .c .php .zip` 等）直接分析。

**可以做什么：**

```
「帮我扫描 /home/user/myproject，用 YASA 引擎」
「克隆 github.com/xxx/yyy 然后做安全分析」
「查一下最新的 Python SQL 注入 CVE」
「这个包的 1.2.3 版本有没有已知漏洞」
「上次扫描的报告哪条漏洞最危险」
「根据这个漏洞描述帮我生成一条检测规则」
```

**能力范围：**
- 对本地路径或克隆仓库执行漏洞扫描，查看和管理历史报告
- 搜索 GitHub Advisory、NVD、OSV 漏洞数据库，查询 CISA KEV 已知被利用漏洞，获取 EPSS 利用概率
- 克隆 GitHub/GitLab 仓库，查看提交历史、commit diff，追踪漏洞引入和修复点
- 根据漏洞描述生成 YASA 检测规则，根据用户反馈迭代优化
- Bing 联网搜索、GitHub 代码和仓库搜索

支持**深度思考模式**（点击 🧠 切换），对话历史自动保存，可从侧边栏随时继续历史对话。

### 规则工坊

进入 `/rule-workshop` 页面，从 CVE 自动生成可用于扫描的 YASA 检测规则。

**生成流程：**

1. 在左侧面板按语言、漏洞类型或关键词搜索 GitHub Advisory（覆盖 SQL 注入、命令注入、SSRF、路径穿越、XSS、反序列化等 23 种类型）
2. 勾选目标 CVE，选择目标规则集，点击「生成」
3. 后端自动执行四阶段管道：LLM 分析漏洞特征 → 生成 YASA 规则 JSON → YASA 引擎对测试集做真实扫描评估（TP/FP/FN/F1）→ LLM 根据评估数据精准优化
4. 迭代直到 F1 ≥ 0.85 或 3 轮无改进，结果入库

**规则管理：**在右侧面板查看官方规则集和个人规则集，支持克隆官方规则、启用/禁用/删除单条规则。生成的规则可在扫描时作为「个人规则集」叠加使用。

> 与只做"生成→LLM自评"的方案不同，规则工坊的 Stage 3 将规则投入真实 YASA 引擎扫描，LLM 拿到的是具体的误报行号、漏报数量等数据，而非泛泛的"规则可能有问题"。

---

## 自部署

<details>
<summary>点击展开部署步骤</summary>

### 获取 YASA 引擎

从 [GitHub Releases](https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases) 下载 YASA 引擎包（约 466MB），解压到独立目录。

### 配置环境变量

```bash
cd ma_yisheng
cp .env.example .env
```

编辑 `.env`，填写以下配置：

| 配置项 | 必需 | 说明 |
|--------|------|------|
| `LLM_API_KEY` | ✓ | LLM 接口密钥 |
| `LLM_MODEL` | ✓ | 模型名称 |
| `YASA_BUNDLE_PATH` | ✓ | YASA 引擎目录路径 |
| `JWT_SECRET` | ✓ | 随机字符串，生产环境务必修改 |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | ✓ | 邮件服务（用于注册验证码） |
| `GITHUB_TOKEN` | — | 提升 GitHub API 限流（5000/h vs 60/h） |
| `SEMGREP_RULES_PATH` | — | 离线 Semgrep 规则目录 |

### 启动服务

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r server_requirements.txt
bash start_server.sh
```

服务启动后访问 `http://localhost:8000`，API 文档见 `http://localhost:8000/docs`。

</details>

---

## License

MIT
