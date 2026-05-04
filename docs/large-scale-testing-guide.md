# 大规模测试指南

## 概述

本指南说明如何进行大规模规则生成测试，包括：
1. 自动抓取漏洞案例
2. 批量生成规则
3. 批量评估规则

---

## 步骤 1：自动抓取漏洞案例

### 从 GitHub Advisory 抓取

```bash
cd yasa_engine/scripts

# 抓取 10 个 Python SQL 注入案例
node fetch_vuln_from_github.js python "SQL Injection" 10

# 抓取 5 个 Java 命令注入案例
node fetch_vuln_from_github.js java "Command Injection" 5

# 抓取 20 个 JavaScript SSRF 案例
node fetch_vuln_from_github.js javascript "SSRF" 20
```

### 提高速率限制（推荐）

GitHub API 有速率限制，建议设置 Personal Access Token：

1. 访问 https://github.com/settings/tokens
2. 生成新 token（只需 `public_repo` 权限）
3. 设置环境变量：
   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
   ```

### 脚本功能

- ✅ 自动搜索 GitHub Advisory Database
- ✅ 提取 commit diff（before/after 代码）
- ✅ 自动识别 source/sink 函数
- ✅ 生成标准化 JSON 格式
- ✅ 保存到 `datasets/vuln_cases/`

### 输出示例

```json
{
  "case_id": "python_sql_injection_GHSA-xxxx-yyyy-zzzz",
  "language": "python",
  "vulnerability_type": "SQL Injection",
  "source_code_before": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
  "source_code_after": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
  "source_function_hints": ["request.args"],
  "sink_function_hints": ["execute"],
  "notes": "SQL injection in user query (GHSA-xxxx-yyyy-zzzz)",
  "metadata": {
    "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
    "cve_id": "CVE-2023-12345",
    "severity": "high",
    "url": "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz"
  }
}
```

---

## 步骤 2：批量生成规则

### 基本用法

```bash
cd yasa_engine/scripts

# 为所有案例生成规则
node batch_generate_rules.js <your-api-key>

# 只为 Python 案例生成规则
node batch_generate_rules.js <your-api-key> --language python

# 限制数量（测试用）
node batch_generate_rules.js <your-api-key> --max 5

# 使用 OpenAI
node batch_generate_rules.js <your-api-key> --provider openai --model gpt-4o-mini
```

### 脚本功能

- ✅ 自动读取 `datasets/vuln_cases/` 下所有案例
- ✅ 逐个调用 `/api/generate-rule-from-case`
- ✅ 自动校验生成的规则
- ✅ 保存成功的规则到 `generated_rules/staging/`
- ✅ 生成详细报告到 `iteration_logs/`

### 输出示例

```
=== Batch Rule Generation ===

Provider: deepseek
Model: deepseek-chat
Language filter: python
Max count: unlimited

Loaded 15 cases

[1/15] Processing python_sqli_001...
  ✓ Success (validation: PASS)
  Waiting 2s...

[2/15] Processing python_cmd_injection_001...
  ✓ Success (validation: PASS)
  Waiting 2s...

...

=== Summary ===

Total cases: 15
Success: 14
Failed: 1

Validation:
  Valid rules: 13
  Invalid rules: 1

Report saved to: iteration_logs/batch_generation_1234567890.json
```

---

## 步骤 3：批量评估规则（可选）

如果你有测试集，可以批量评估生成的规则：

```bash
# TODO: 实现 batch_evaluate_rules.js
node batch_evaluate_rules.js --rules generated_rules/staging/ --tests datasets/test_cases/
```

---

## 完整工作流示例

### 场景：测试 50 个 Python 漏洞案例

```bash
# 1. 抓取案例
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
cd yasa_engine/scripts

node fetch_vuln_from_github.js python "SQL Injection" 20
node fetch_vuln_from_github.js python "Command Injection" 15
node fetch_vuln_from_github.js python "SSRF" 15

# 2. 检查抓取结果
ls ../../datasets/vuln_cases/ | wc -l

# 3. 批量生成规则
node batch_generate_rules.js sk-xxxxxxxx --language python

# 4. 查看报告
cat ../../iteration_logs/batch_generation_*.json | jq '.summary'

# 5. 检查生成的规则
ls ../../generated_rules/staging/ | wc -l
```

---

## 成本估算

### 单条规则生成成本

- Stage 1 (描述生成): ~500 tokens
- Stage 2 (规则生成): ~1000 tokens
- **总计**: ~1500 tokens/规则

### DeepSeek 定价（参考）

- 输入: ¥0.001/1K tokens
- 输出: ¥0.002/1K tokens
- **单条规则成本**: ~¥0.003（约 $0.0004）

### 批量成本

| 案例数 | 总 tokens | 成本（DeepSeek） | 成本（GPT-4o-mini） |
|--------|-----------|------------------|---------------------|
| 10     | 15K       | ¥0.03            | $0.015              |
| 50     | 75K       | ¥0.15            | $0.075              |
| 100    | 150K      | ¥0.30            | $0.15               |
| 1000   | 1.5M      | ¥3.00            | $1.50               |

**结论**：测试 1000 个案例成本约 ¥3-10 元，非常经济。

---

## 注意事项

### 1. 速率限制

- **GitHub API**: 未认证 60 次/小时，认证后 5000 次/小时
- **LLM API**: DeepSeek 通常无严格限制，OpenAI 有 TPM/RPM 限制
- **建议**: 批量生成时每个请求间隔 2-3 秒

### 2. 数据质量

- 并非所有 GitHub Advisory 都有完整的 patch
- 自动识别的 source/sink 可能不准确
- **建议**: 人工抽查 10-20% 的案例

### 3. 规则校验

- 生成的规则可能不符合 YASA 语义
- **建议**: 只使用 `validation.valid === true` 的规则

### 4. 存储空间

- 1000 个案例 + 规则约占 50-100 MB
- 迭代日志会累积
- **建议**: 定期清理 `iteration_logs/`

---

## 高级用法

### 并行生成（提高速度）

```bash
# 将案例分成 4 批，并行处理
node batch_generate_rules.js sk-xxx --language python --max 25 &
node batch_generate_rules.js sk-xxx --language java --max 25 &
node batch_generate_rules.js sk-xxx --language javascript --max 25 &
node batch_generate_rules.js sk-xxx --language go --max 25 &
wait
```

### 自定义抓取源

除了 GitHub Advisory，还可以从以下来源抓取：

1. **NVD (National Vulnerability Database)**
   - API: https://nvd.nist.gov/developers/vulnerabilities
   - 需要注册 API Key

2. **CVE Details**
   - 网站: https://www.cvedetails.com/
   - 需要爬虫（注意 robots.txt）

3. **Snyk Vulnerability Database**
   - API: https://snyk.io/vuln/
   - 需要 Snyk 账号

4. **手工标注的数据集**
   - Juliet Test Suite (NIST)
   - OWASP Benchmark
   - 直接下载使用

---

## 故障排查

### 问题 1: GitHub API 403 错误

**原因**: 速率限制  
**解决**: 设置 `GITHUB_TOKEN` 环境变量

### 问题 2: 抓取的案例没有代码

**原因**: Advisory 没有关联 commit  
**解决**: 正常现象，脚本会自动跳过

### 问题 3: 生成的规则校验失败

**原因**: LLM 输出格式不符合 YASA 语义  
**解决**: 
- 调整 `prompts/stage2_rule_generation.md`
- 增加规则示例（few-shot）
- 使用更强的模型（如 GPT-4）

### 问题 4: 批量生成中断

**原因**: 网络超时或 API 错误  
**解决**: 
- 脚本会记录已处理的案例
- 手动删除已生成的规则，重新运行
- 或使用 `--max` 分批处理

---

## 总结

通过这套脚本，你可以：

✅ **自动抓取** 数百个真实漏洞案例  
✅ **批量生成** 规则（成本极低）  
✅ **自动校验** 规则质量  
✅ **详细报告** 成功率和错误信息  

适合大规模实验和论文数据收集。
