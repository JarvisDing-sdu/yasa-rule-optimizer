#!/usr/bin/env node

/**
 * 快速测试脚本：生成一条规则并校验
 * 
 * 用法：
 *   node test_generate_rule.js <case_id> <api_key>
 * 
 * 示例：
 *   node test_generate_rule.js python_sqli_001 sk-xxx
 */

const fs = require('fs');
const path = require('path');
const axios = require('axios');

const API_BASE = process.env.API_BASE || 'http://localhost:3000';

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: node test_generate_rule.js <case_id> <api_key>');
    console.error('Example: node test_generate_rule.js python_sqli_001 sk-xxx');
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
  console.log(`\n=== Testing Rule Generation ===`);
  console.log(`Case ID: ${vulnCase.case_id}`);
  console.log(`Language: ${vulnCase.language}`);
  console.log(`Vulnerability Type: ${vulnCase.vulnerability_type}`);
  console.log('');

  try {
    console.log('Calling /api/generate-rule-from-case...');
    const response = await axios.post(`${API_BASE}/api/generate-rule-from-case`, {
      vulnCase,
      provider: 'deepseek',
      model: 'deepseek-chat',
      apiKey,
    }, {
      timeout: 120000,
    });

    const result = response.data;

    console.log('\n=== Result ===\n');
    console.log(`Success: ${result.success}`);
    console.log(`Validation Valid: ${result.validation.valid}`);
    console.log(`Saved Path: ${result.savedPath || 'N/A'}`);
    console.log('');

    if (result.validation.errors.length > 0) {
      console.log('Validation Errors:');
      result.validation.errors.forEach((err, i) => {
        console.log(`  ${i + 1}. [${err.type}] ${err.field || ''}: ${err.message}`);
      });
      console.log('');
    }

    if (result.validation.warnings.length > 0) {
      console.log('Validation Warnings:');
      result.validation.warnings.forEach((warn, i) => {
        console.log(`  ${i + 1}. [${warn.type}] ${warn.field || ''}: ${warn.message}`);
      });
      console.log('');
    }

    console.log('Generated Rule:');
    console.log(JSON.stringify(result.rule, null, 2));
    console.log('');

    console.log('Description:');
    console.log(JSON.stringify(result.description, null, 2));
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
