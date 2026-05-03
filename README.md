# yasa-rule-optimizer

A project focused on optimizing the rule generation logic of the YASA static analysis engine using Large Language Models (LLMs).

## 核心功能

✅ **LLM 辅助规则生成**：从漏洞案例自动生成静态分析规则  
✅ **规则校验**：JSON Schema + YASA 语义校验  
✅ **规则评估**：自动对比扫描结果与预期，计算 Precision/Recall/F1  
✅ **迭代优化**：基于误报/漏报分析，自动优化规则（最多 3 轮）  
✅ **多语言支持**：Python、Java、Go、JavaScript  

## 快速开始

### 1. 安装依赖

```bash
cd yasa_engine/yasa-api-agent
npm install
```

### 2. 启动后端服务

```bash
cd yasa_engine/yasa-api-agent
node app.js
```

服务将在 `http://localhost:3000` 启动。

### 3. 测试规则生成

```bash
cd yasa_engine/scripts
node test_generate_rule.js python_sqli_001 <your-api-key>
```

### 4. 测试迭代优化

```bash
node test_optimize_rule.js python_sqli_001 <your-api-key>
```

## 目录结构

- `apps/web/`: Web 前端界面
- `apps/client/`: 客户端应用
- `yasa_engine/`: YASA 引擎基础和运行时依赖
  - `yasa-api-agent/`: 后端 API 服务
  - `scripts/`: 规则生成、校验、评估脚本
  - `rules-mayisheng/`: 现有规则配置（不修改）
- `datasets/`: 实验数据集
  - `vuln_cases/`: 漏洞案例（输入）
  - `expected_results/`: 预期结果（用于评估）
  - `rule_examples/`: 规则示例（few-shot）
- `generated_rules/`: 生成的规则
  - `staging/`: 新生成的规则（待校验）
  - `candidate/`: 通过校验和评估的规则
  - `production/`: 正式启用的规则
- `iteration_logs/`: 迭代优化日志
- `prompts/`: LLM prompt 模板（Stage 1-4）
- `schemas/`: JSON Schema 定义
- `workflows/`: 实验工作流
- `docs/`: 项目和实验文档

## 核心 API

| 接口 | 功能 | 文档 |
|------|------|------|
| `POST /api/generate-rule-from-case` | 从漏洞案例生成规则 | [详见文档](docs/rule-generation-guide.md) |
| `POST /api/validate-rule` | 校验规则 | [详见文档](docs/rule-generation-guide.md) |
| `POST /api/evaluate-rule` | 评估规则 | [详见文档](docs/rule-generation-guide.md) |
| `POST /api/optimize-rule-iteratively` | 迭代优化规则 | [详见文档](docs/rule-generation-guide.md) |

## 工作流程

```
漏洞案例 → LLM-1 (描述) → LLM-2 (规则) → 校验 → 评估 → LLM-3 (FP/FN分析) → LLM-4 (优化prompt) → 再生成
```

详细说明见 [规则生成指南](docs/rule-generation-guide.md)。

## 论文实现

本项目实现了论文《Generation, Migration and Optimization of Cross-Language Static-Analysis Rules Based on Large Language Models》中的核心机制：

- ✅ Stage 1: 漏洞描述生成（LLM-1）
- ✅ Stage 2: 规则生成（LLM-2）
- ✅ Stage 3: FP/FN 分析（LLM-3）
- ✅ Stage 4: Prompt 优化（LLM-4）
- ✅ 迭代优化循环（3 轮）

**简化点**：使用同一个 LLM 实例，通过不同 prompt 实现 4 个阶段，降低成本和复杂度。

## 示例案例

项目已包含 3 个完整的漏洞案例：

- `python_sqli_001`: SQL 注入
- `python_cmd_injection_001`: 命令注入
- `python_ssrf_001`: SSRF

可直接用于测试和演示。

## 贡献指南

1. 新增漏洞案例：在 `datasets/vuln_cases/` 添加 JSON 文件
2. 新增规则示例：在 `datasets/rule_examples/` 添加示例
3. 优化 prompt：修改 `prompts/stage*.md`
4. 扩展语言支持：在 `app.js` 的 `LANG_CONFIG` 中添加配置

## License

MIT
