# 规则生成系统实现总结

## 已完成的工作

### 1. 核心基础设施 ✅

- **目录结构**
  - `generated_rules/staging/` - 新生成规则暂存区
  - `generated_rules/candidate/` - 通过评估的候选规则
  - `generated_rules/production/` - 正式生产规则
  - `iteration_logs/` - 迭代优化日志
  - `yasa_engine/scripts/` - 核心脚本目录

- **Schema 定义**
  - `schemas/generated-rule.schema.json` - 生成规则的 JSON Schema
  - 包含完整的 sources/sinks/metadata 定义
  - 支持校验和元数据追踪

### 2. 核心模块 ✅

#### 规则校验器 (`validate_rule.js`)
- JSON Schema 结构校验
- YASA 语义规则校验（sources/sinks 类型、必填字段）
- 规则 ID 唯一性检查
- 支持命令行独立运行

#### LLM 调用管道 (`rule_generation_pipeline.js`)
- Stage 1: 漏洞描述生成（LLM-1）
- Stage 2: 规则生成（LLM-2）
- Stage 3: FP/FN 分析（LLM-3）
- Stage 4: Prompt 优化（LLM-4）
- 单轮生成和迭代优化两种模式

#### 评估对比器 (`compare_findings.js`)
- 扫描结果与预期结果对比
- TP/FP/FN 分类
- Precision/Recall/F1 计算
- 支持解析 YASA 扫描产物

### 3. API 接口 ✅

已在 `app.js` 中集成 4 个新接口：

1. **POST /api/generate-rule-from-case**
   - 从漏洞案例生成规则（Stage 1 + 2）
   - 自动校验并保存到 staging
   - 返回描述、规则、校验结果

2. **POST /api/validate-rule**
   - 独立校验规则
   - 返回详细的错误和警告

3. **POST /api/evaluate-rule**
   - 用测试集评估规则
   - 返回 TP/FP/FN 和指标

4. **POST /api/optimize-rule-iteratively**
   - 迭代优化规则（最多 3 轮）
   - 自动执行 Stage 1→2→3→4→2 循环
   - 保存最佳规则到 candidate
   - 记录完整迭代日志

### 4. 测试数据 ✅

#### 漏洞案例（3 个）
- `python_sqli_001.json` - SQL 注入
- `python_cmd_injection_001.json` - 命令注入
- `python_ssrf_001.json` - SSRF

每个案例包含：
- before/after 代码
- source/sink hints
- 漏洞类型和语言

#### 预期结果
- 对应每个案例的 expected findings
- 用于评估对比

#### 规则示例
- `python_example.json` - 用于 few-shot prompting

### 5. 测试脚本 ✅

- `test_generate_rule.js` - 快速测试单轮生成
- `test_optimize_rule.js` - 快速测试迭代优化
- 支持命令行参数（case_id + api_key）

### 6. 文档 ✅

- `docs/rule-generation-guide.md` - 完整使用指南
- `generated_rules/README.md` - 规则生命周期说明
- `README.md` - 项目总览（已更新）
- `install_dependencies.sh` - 依赖安装脚本

## 技术亮点

### 1. 简化的 4-LLM 架构
- 使用同一个 LLM 实例，通过不同 prompt 实现 4 个阶段
- 降低成本：只需一个 API Key
- 降低复杂度：复用 `callLLM` 函数

### 2. 完整的规则生命周期管理
```
生成 → 校验 → staging → 评估 → candidate → 审核 → production
```

### 3. 可扩展的评估框架
- 支持自定义测试集
- 支持多种匹配策略
- 易于扩展到其他语言

### 4. 迭代优化闭环
```
规则 → 扫描 → 对比 → FP/FN分析 → Prompt优化 → 再生成
```

## 与论文的对应关系

| 论文环节 | 实现模块 | 状态 |
|---------|---------|------|
| LLM-1: 漏洞描述生成 | `stage1_generateDescription` | ✅ |
| LLM-2: 规则生成 | `stage2_generateRule` | ✅ |
| LLM-3: FP/FN 分析 | `stage3_analyzeFpFn` | ✅ |
| LLM-4: Prompt 优化 | `stage4_refinePrompt` | ✅ |
| 规则校验 | `RuleValidator` | ✅ |
| 评估对比 | `FindingsComparator` | ✅ |
| 迭代循环 | `optimizeRuleIteratively` | ✅ |

## 下一步工作建议

### 短期（1-2 周）
1. **安装依赖并测试**
   ```bash
   ./install_dependencies.sh
   cd yasa_engine/yasa-api-agent && node app.js
   cd ../scripts && node test_generate_rule.js python_sqli_001 <api-key>
   ```

2. **补充更多测试案例**
   - 从 GitHub Advisory 或 CVE 数据库抓取
   - 至少准备 10-20 个案例用于评估

3. **调优 Prompt**
   - 根据实际生成效果调整 `prompts/stage*.md`
   - 可能需要多次迭代

### 中期（2-4 周）
4. **前端集成**
   - 在 `apps/web/public/index.html` 中添加"规则生成"面板
   - 可视化展示迭代过程和评估结果

5. **批量生成脚本**
   - 支持从 CSV/JSON 批量读取案例
   - 并行生成多条规则

6. **规则合并工具**
   - 将 candidate 规则合并到正式配置
   - 自动去重和冲突检测

### 长期（1-2 月）
7. **CVE 爬虫**
   - 自动从 GitHub Advisory 抓取漏洞案例
   - 提取 before/after diff

8. **跨语言规则迁移**
   - Python 规则 → Java 规则
   - 利用 LLM 做语义转换

9. **性能基准测试**
   - 测试生成规则的扫描性能
   - 与手写规则对比

## 注意事项

### 1. API Key 管理
- 不要提交 API Key 到 Git
- 使用 `.env` 文件或环境变量
- 前端输入后立即清空

### 2. 规则质量控制
- 生成的规则必须经过人工审核
- staging → candidate → production 三级审核
- 记录每条规则的来源和评估指标

### 3. 成本控制
- 每轮迭代会调用多次 LLM（约 4-6 次）
- 3 轮优化 ≈ 12-18 次调用
- 建议先用小规模测试集验证

### 4. 评估准确性
- 测试集质量直接影响优化效果
- 需要包含正样本和负样本
- 建议人工标注预期结果

## 文件清单

### 新增文件
```
schemas/generated-rule.schema.json
generated_rules/README.md
generated_rules/staging/
generated_rules/candidate/
generated_rules/production/
iteration_logs/
yasa_engine/scripts/validate_rule.js
yasa_engine/scripts/rule_generation_pipeline.js
yasa_engine/scripts/compare_findings.js
yasa_engine/scripts/test_generate_rule.js
yasa_engine/scripts/test_optimize_rule.js
datasets/vuln_cases/python_sqli_001.json
datasets/vuln_cases/python_cmd_injection_001.json
datasets/vuln_cases/python_ssrf_001.json
datasets/expected_results/python_sqli_001.expected.json
datasets/expected_results/python_cmd_injection_001.expected.json
datasets/rule_examples/python_example.json
docs/rule-generation-guide.md
install_dependencies.sh
```

### 修改文件
```
yasa_engine/yasa-api-agent/app.js (新增 4 个接口)
README.md (更新项目说明)
```

## 总结

本次实现完成了论文中核心的"LLM 辅助规则生成与迭代优化"机制，并针对邓老师的建议做了简化（使用同一个 LLM 实例）。系统已具备：

✅ 完整的 4 阶段生成流程  
✅ 规则校验和评估能力  
✅ 迭代优化闭环  
✅ 可直接测试的示例案例  
✅ 详细的使用文档  

可以立即开始测试和验证效果。
