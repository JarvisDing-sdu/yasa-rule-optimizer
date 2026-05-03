# LLM-Assisted Rule Generation System

## 概述

本系统实现了基于大语言模型的静态分析规则生成、校验、评估和迭代优化流程。

## 核心流程

### 单轮生成（Stage 1 + Stage 2）

```
漏洞案例 → LLM-1 (描述生成) → LLM-2 (规则生成) → 校验 → staging/
```

### 迭代优化（Stage 1 → 2 → 3 → 4 → 2 ...）

```
漏洞案例 → 描述 → 规则 → 评估 → FP/FN分析 → prompt优化 → 再生成 → ...
```

## API 接口

### 1. 生成规则（单轮）

**POST** `/api/generate-rule-from-case`

请求体：
```json
{
  "vulnCase": {
    "case_id": "python_sqli_001",
    "language": "python",
    "vulnerability_type": "SQLInjection",
    "source_code_before": "...",
    "source_code_after": "...",
    "source_function_hints": ["request.args.get"],
    "sink_function_hints": ["cursor.execute"]
  },
  "provider": "deepseek",
  "model": "deepseek-chat",
  "apiKey": "sk-xxx"
}
```

响应：
```json
{
  "success": true,
  "description": { ... },
  "rule": { ... },
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  },
  "savedPath": "/path/to/generated_rules/staging/rule_xxx.json"
}
```

### 2. 校验规则

**POST** `/api/validate-rule`

请求体：
```json
{
  "rule": { ... }
}
```

### 3. 评估规则

**POST** `/api/evaluate-rule`

请求体：
```json
{
  "rule": { ... },
  "testCases": [
    {
      "case_id": "test_001",
      "code": "...",
      "language": "python",
      "expected_findings": [
        { "vulnerability_type": "SQLInjection", "should_report": true }
      ]
    }
  ]
}
```

响应：
```json
{
  "success": true,
  "evaluation": {
    "tp": [...],
    "fp": [...],
    "fn": [...],
    "metrics": {
      "precision": 0.95,
      "recall": 0.90,
      "f1": 0.92
    }
  }
}
```

### 4. 迭代优化

**POST** `/api/optimize-rule-iteratively`

请求体：
```json
{
  "vulnCase": { ... },
  "testCases": [ ... ],
  "provider": "deepseek",
  "model": "deepseek-chat",
  "apiKey": "sk-xxx",
  "maxRounds": 3
}
```

响应：
```json
{
  "success": true,
  "bestRule": { ... },
  "bestF1": 0.92,
  "iterationLog": [
    {
      "round": 1,
      "rule": { ... },
      "evaluation": { ... }
    },
    ...
  ],
  "savedPath": "/path/to/generated_rules/candidate/rule_xxx.json",
  "logPath": "/path/to/iteration_logs/xxx.json"
}
```

## 命令行工具

### 校验规则

```bash
cd yasa_engine/scripts
node validate_rule.js ../../generated_rules/staging/rule_xxx.json
```

### 对比评估结果

```bash
node compare_findings.js test_cases.json scan_results.json
```

## 目录结构

```
yasa-rule-optimizer/
├── datasets/
│   ├── vuln_cases/          # 漏洞案例（输入）
│   ├── expected_results/    # 预期结果（用于评估）
│   └── rule_examples/       # 规则示例（few-shot）
├── generated_rules/
│   ├── staging/             # 新生成的规则（待校验）
│   ├── candidate/           # 通过校验和评估的规则
│   └── production/          # 正式启用的规则
├── iteration_logs/          # 迭代优化日志
├── prompts/                 # LLM prompt 模板
├── schemas/                 # JSON Schema 定义
└── yasa_engine/
    ├── scripts/
    │   ├── validate_rule.js           # 规则校验器
    │   ├── compare_findings.js        # 评估对比器
    │   └── rule_generation_pipeline.js # LLM 调用管道
    └── yasa-api-agent/
        └── app.js                     # 后端 API 服务
```

## 工作流程示例

### 场景 1：快速生成单条规则

1. 准备漏洞案例 JSON（参考 `datasets/vuln_cases/python_sqli_001.json`）
2. 调用 `/api/generate-rule-from-case`
3. 检查返回的 `validation` 字段
4. 如果 `valid: true`，规则已保存到 `staging/`
5. 人工审核后可移动到 `production/`

### 场景 2：批量生成并优化

1. 准备多个漏洞案例
2. 准备测试集（包含预期结果）
3. 对每个案例调用 `/api/optimize-rule-iteratively`
4. 系统自动执行 3 轮优化
5. 最佳规则保存到 `candidate/`
6. 查看 `iteration_logs/` 了解优化过程

### 场景 3：手动调试规则

1. 编写规则 JSON
2. 调用 `/api/validate-rule` 检查语法
3. 调用 `/api/evaluate-rule` 测试效果
4. 根据 FP/FN 手动调整规则
5. 重复 2-4 直到满意

## 注意事项

1. **API Key 安全**：不要在代码中硬编码 API Key，使用环境变量或前端输入
2. **规则唯一性**：每条规则的 `metadata.ruleId` 必须唯一
3. **语义校验**：生成的规则必须符合 YASA 语义（TaintSource、FuncCallTaintSink 等）
4. **评估准确性**：测试集质量直接影响优化效果，建议至少 10 个案例
5. **迭代轮数**：默认 3 轮，可根据实际情况调整（更多轮次 = 更高成本）

## 扩展方向

- [ ] 支持从 CVE 数据库自动抓取漏洞案例
- [ ] 前端可视化界面（规则编辑器、评估报告）
- [ ] 规则版本管理和回滚
- [ ] 多语言规则迁移（Python → Java）
- [ ] 规则性能基准测试
