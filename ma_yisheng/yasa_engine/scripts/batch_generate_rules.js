#!/usr/bin/env node

/**
 * 批量生成规则脚本
 * 
 * 功能：
 * 1. 读取 datasets/vuln_cases/ 下的所有案例
 * 2. 对每个案例调用 /api/generate-rule-from-case
 * 3. 记录成功/失败统计
 * 4. 生成批量报告
 * 
 * 用法：
 *   node batch_generate_rules.js <api_key> [--language python] [--max 10]
 * 
 * 示例：
 *   node batch_generate_rules.js sk-xxx
 *   node batch_generate_rules.js sk-xxx --language python --max 5
 */

const fs = require('fs');
const path = require('path');
const axios = require('axios');

const API_BASE = process.env.API_BASE || 'http://localhost:3000';

/**
 * 解析命令行参数
 */
function parseArgs() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.error('Usage: node batch_generate_rules.js <api_key> [--language python] [--max 10]');
    console.error('Example: node batch_generate_rules.js sk-xxx --language python --max 5');
    process.exit(1);
  }

  const config = {
    apiKey: args[0],
    language: null,
    maxCount: null,
    provider: 'deepseek',
    model: 'deepseek-chat',
  };

  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--language' && args[i + 1]) {
      config.language = args[i + 1];
      i++;
    } else if (args[i] === '--max' && args[i + 1]) {
      config.maxCount = parseInt(args[i + 1]);
      i++;
    } else if (args[i] === '--provider' && args[i + 1]) {
      config.provider = args[i + 1];
      i++;
    } else if (args[i] === '--model' && args[i + 1]) {
      config.model = args[i + 1];
      i++;
    }
  }

  return config;
}

/**
 * 加载所有漏洞案例
 */
function loadVulnCases(language = null) {
  const casesDir = path.resolve(__dirname, '../../datasets/vuln_cases');
  
  if (!fs.existsSync(casesDir)) {
    console.error(`Cases directory not found: ${casesDir}`);
    return [];
  }

  const files = fs.readdirSync(casesDir).filter(f => f.endsWith('.json'));
  const cases = [];

  for (const file of files) {
    try {
      const content = JSON.parse(fs.readFileSync(path.join(casesDir, file), 'utf8'));
      
      // 过滤语言
      if (language && content.language !== language) {
        continue;
      }

      cases.push(content);
    } catch (e) {
      console.warn(`Failed to load ${file}:`, e.message);
    }
  }

  return cases;
}

/**
 * 生成单条规则
 */
async function generateRule(vulnCase, config) {
  try {
    const response = await axios.post(`${API_BASE}/api/generate-rule-from-case`, {
      vulnCase,
      provider: config.provider,
      model: config.model,
      apiKey: config.apiKey,
    }, {
      timeout: 120000, // 2 分钟
    });

    return {
      success: true,
      caseId: vulnCase.case_id,
      rule: response.data.rule,
      validation: response.data.validation,
      savedPath: response.data.savedPath,
    };
  } catch (err) {
    return {
      success: false,
      caseId: vulnCase.case_id,
      error: err.response?.data?.details || err.message,
    };
  }
}

/**
 * 主函数
 */
async function main() {
  const config = parseArgs();

  console.log('\n=== Batch Rule Generation ===\n');
  console.log(`Provider: ${config.provider}`);
  console.log(`Model: ${config.model}`);
  console.log(`Language filter: ${config.language || 'all'}`);
  console.log(`Max count: ${config.maxCount || 'unlimited'}`);
  console.log('');

  // 1. 加载案例
  let cases = loadVulnCases(config.language);
  
  if (cases.length === 0) {
    console.error('No cases found. Please add cases to datasets/vuln_cases/');
    process.exit(1);
  }

  if (config.maxCount) {
    cases = cases.slice(0, config.maxCount);
  }

  console.log(`Loaded ${cases.length} cases\n`);

  // 2. 批量生成
  const results = [];
  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < cases.length; i++) {
    const vulnCase = cases[i];
    console.log(`[${i + 1}/${cases.length}] Processing ${vulnCase.case_id}...`);

    const result = await generateRule(vulnCase, config);
    results.push(result);

    if (result.success) {
      successCount++;
      console.log(`  ✓ Success (validation: ${result.validation.valid ? 'PASS' : 'FAIL'})`);
      if (!result.validation.valid) {
        console.log(`    Errors: ${result.validation.errors.length}`);
      }
    } else {
      failCount++;
      console.log(`  ✗ Failed: ${result.error}`);
    }

    // 避免速率限制
    if (i < cases.length - 1) {
      console.log('  Waiting 2s...\n');
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }

  // 3. 生成报告
  console.log('\n=== Summary ===\n');
  console.log(`Total cases: ${cases.length}`);
  console.log(`Success: ${successCount}`);
  console.log(`Failed: ${failCount}`);
  console.log('');

  // 统计校验结果
  const validRules = results.filter(r => r.success && r.validation.valid).length;
  const invalidRules = results.filter(r => r.success && !r.validation.valid).length;

  console.log('Validation:');
  console.log(`  Valid rules: ${validRules}`);
  console.log(`  Invalid rules: ${invalidRules}`);
  console.log('');

  // 保存详细报告
  const reportDir = path.resolve(__dirname, '../../iteration_logs');
  fs.mkdirSync(reportDir, { recursive: true });
  
  const reportPath = path.join(reportDir, `batch_generation_${Date.now()}.json`);
  fs.writeFileSync(reportPath, JSON.stringify({
    timestamp: new Date().toISOString(),
    config,
    summary: {
      total: cases.length,
      success: successCount,
      failed: failCount,
      valid: validRules,
      invalid: invalidRules,
    },
    results,
  }, null, 2), 'utf8');

  console.log(`Report saved to: ${reportPath}`);
  console.log('');

  // 列出失败的案例
  if (failCount > 0) {
    console.log('Failed cases:');
    results.filter(r => !r.success).forEach(r => {
      console.log(`  - ${r.caseId}: ${r.error}`);
    });
    console.log('');
  }

  // 列出校验失败的案例
  if (invalidRules > 0) {
    console.log('Invalid rules:');
    results.filter(r => r.success && !r.validation.valid).forEach(r => {
      console.log(`  - ${r.caseId}: ${r.validation.errors.length} errors`);
    });
    console.log('');
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
