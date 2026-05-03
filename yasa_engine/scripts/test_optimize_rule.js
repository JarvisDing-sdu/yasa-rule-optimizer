#!/usr/bin/env node

/**
 * 快速测试脚本：迭代优化规则
 * 
 * 用法：
 *   node test_optimize_rule.js <case_id> <api_key>
 * 
 * 示例：
 *   node test_optimize_rule.js python_sqli_001 sk-xxx
 */

const fs = require('fs');
const path = require('path');
const axios = require('axios');

const API_BASE = process.env.API_BASE || 'http://localhost:3000';

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: node test_optimize_rule.js <case_id> <api_key>');
    console.error('Example: node test_optimize_rule.js python_sqli_001 sk-xxx');
    process.exit(1);
  }

  const caseId = args[0];
  const apiKey = args[1];

  // 加载漏洞案例
  const casePath = path.resolve(__dirname, `../../datasets/vuln_cases/${caseId}.json`);
  if (!fs.existsSync(casePath)) {
    console.error(`Case file not found: ${casePath}`);
    process.exit(1);
  }

  const vulnCase = JSON.parse(fs.readFileSync(casePath, 'utf8'));

  // 构造测试案例（简化版：使用 before 代码作为测试）
  const testCases = [
    {
      case_id: `${caseId}_test`,
      code: vulnCase.source_code_before,
      language: vulnCase.language,
      expected_findings: [
        {
          vulnerability_type: vulnCase.vulnerability_type,
          should_report: true,
        }
      ]
    }
  ];

  console.log(`\n=== Testing Iterative Optimization ===`);
  console.log(`Case ID: ${vulnCase.case_id}`);
  console.log(`Language: ${vulnCase.language}`);
  console.log(`Vulnerability Type: ${vulnCase.vulnerability_type}`);
  console.log(`Max Rounds: 3`);
  console.log('');

  try {
    console.log('Calling /api/optimize-rule-iteratively...');
    console.log('(This may take several minutes...)');
    console.log('');

    const response = await axios.post(`${API_BASE}/api/optimize-rule-iteratively`, {
      vulnCase,
      testCases,
      provider: 'deepseek',
      model: 'deepseek-chat',
      apiKey,
      maxRounds: 3,
    }, {
      timeout: 600000, // 10 分钟
    });

    const result = response.data;

    console.log('\n=== Result ===\n');
    console.log(`Success: ${result.success}`);
    console.log(`Best F1 Score: ${result.bestF1.toFixed(4)}`);
    console.log(`Saved Path: ${result.savedPath || 'N/A'}`);
    console.log(`Log Path: ${result.logPath}`);
    console.log('');

    console.log('Iteration Summary:');
    result.iterationLog.forEach((log, i) => {
      const metrics = log.evaluation.metrics;
      console.log(`  Round ${log.round}: Precision=${metrics.precision.toFixed(2)}, Recall=${metrics.recall.toFixed(2)}, F1=${metrics.f1.toFixed(2)}`);
    });
    console.log('');

    console.log('Best Rule:');
    console.log(JSON.stringify(result.bestRule, null, 2));
    console.log('');

  } catch (err) {
    console.error('\n=== Error ===\n');
    if (err.response) {
      console.error(`Status: ${err.response.status}`);
      console.error(`Error: ${err.response.data.error}`);
      console.error(`Details: ${err.response.data.details}`);
    } else {
      console.error(err.message);
    }
    process.exit(1);
  }
}

main();
