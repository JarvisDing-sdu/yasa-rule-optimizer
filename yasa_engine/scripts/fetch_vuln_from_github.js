#!/usr/bin/env node

/**
 * 从 GitHub Security Advisory Database 抓取漏洞案例
 * 
 * 功能：
 * 1. 通过 GitHub API 搜索漏洞
 * 2. 提取 before/after 代码（从 commit diff）
 * 3. 识别 source/sink 函数
 * 4. 生成标准化的漏洞案例 JSON
 * 
 * 用法：
 *   node fetch_vuln_from_github.js <language> <vuln_type> <count>
 * 
 * 示例：
 *   node fetch_vuln_from_github.js python "SQL Injection" 10
 *   node fetch_vuln_from_github.js java "Command Injection" 5
 */

const axios = require('axios');
const fs = require('fs');
const path = require('path');

// GitHub API 配置
const GITHUB_API_BASE = 'https://api.github.com';
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || ''; // 可选，但有 token 可以提高速率限制

/**
 * 搜索 GitHub Advisory
 */
async function searchAdvisories(language, vulnType, count = 10) {
  const headers = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };
  
  if (GITHUB_TOKEN) {
    headers['Authorization'] = `Bearer ${GITHUB_TOKEN}`;
  }

  try {
    // 使用 GitHub Advisory Database API
    const response = await axios.get(`${GITHUB_API_BASE}/advisories`, {
      headers,
      params: {
        ecosystem: getEcosystem(language),
        severity: 'high,critical',
        per_page: count * 2, // 多抓一些，因为不是所有都有 patch
      },
    });

    console.log(`Found ${response.data.length} advisories`);
    return response.data;
  } catch (err) {
    console.error('Failed to fetch advisories:', err.message);
    if (err.response?.status === 403) {
      console.error('Rate limit exceeded. Please set GITHUB_TOKEN environment variable.');
    }
    return [];
  }
}

/**
 * 获取 Advisory 的详细信息（包括 patch 链接）
 */
async function getAdvisoryDetails(ghsaId) {
  const headers = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };
  
  if (GITHUB_TOKEN) {
    headers['Authorization'] = `Bearer ${GITHUB_TOKEN}`;
  }

  try {
    const response = await axios.get(`${GITHUB_API_BASE}/advisories/${ghsaId}`, {
      headers,
    });
    return response.data;
  } catch (err) {
    console.error(`Failed to fetch details for ${ghsaId}:`, err.message);
    return null;
  }
}

/**
 * 从 commit URL 提取 diff
 */
async function fetchCommitDiff(commitUrl) {
  try {
    // 将 GitHub commit URL 转换为 API URL
    const match = commitUrl.match(/github\.com\/([^\/]+)\/([^\/]+)\/commit\/([a-f0-9]+)/);
    if (!match) return null;

    const [, owner, repo, sha] = match;
    
    const headers = {
      'Accept': 'application/vnd.github.diff',
      'X-GitHub-Api-Version': '2022-11-28',
    };
    
    if (GITHUB_TOKEN) {
      headers['Authorization'] = `Bearer ${GITHUB_TOKEN}`;
    }

    const response = await axios.get(
      `${GITHUB_API_BASE}/repos/${owner}/${repo}/commits/${sha}`,
      { headers }
    );

    return response.data;
  } catch (err) {
    console.error(`Failed to fetch commit diff:`, err.message);
    return null;
  }
}

/**
 * 解析 diff，提取 before/after 代码
 */
function parseDiff(diffText, language) {
  if (!diffText) return null;

  const lines = diffText.split('\n');
  let beforeCode = [];
  let afterCode = [];
  let inDiff = false;

  for (const line of lines) {
    // 检测文件类型
    if (line.startsWith('diff --git')) {
      const ext = getFileExtension(language);
      inDiff = line.includes(`.${ext}`);
      continue;
    }

    if (!inDiff) continue;

    // 提取删除的行（before）
    if (line.startsWith('-') && !line.startsWith('---')) {
      beforeCode.push(line.substring(1));
    }
    // 提取添加的行（after）
    else if (line.startsWith('+') && !line.startsWith('+++')) {
      afterCode.push(line.substring(1));
    }
    // 保留上下文行
    else if (line.startsWith(' ')) {
      beforeCode.push(line.substring(1));
      afterCode.push(line.substring(1));
    }
  }

  return {
    before: beforeCode.join('\n').trim(),
    after: afterCode.join('\n').trim(),
  };
}

/**
 * 从代码中识别可能的 source/sink 函数
 */
function identifySourceSinkHints(code, language, vulnType) {
  const hints = {
    sources: [],
    sinks: [],
  };

  // 常见的 source 模式
  const sourcePatterns = {
    python: ['request.args', 'request.form', 'request.json', 'sys.argv', 'input('],
    java: ['request.getParameter', 'request.getHeader', 'System.getenv'],
    javascript: ['req.query', 'req.body', 'req.params', 'process.argv'],
  };

  // 常见的 sink 模式（按漏洞类型）
  const sinkPatterns = {
    'SQL Injection': {
      python: ['execute(', 'executemany(', 'raw('],
      java: ['executeQuery(', 'executeUpdate(', 'createQuery('],
      javascript: ['query(', 'execute('],
    },
    'Command Injection': {
      python: ['os.system(', 'os.popen(', 'subprocess.'],
      java: ['Runtime.exec(', 'ProcessBuilder('],
      javascript: ['exec(', 'spawn(', 'execSync('],
    },
    'SSRF': {
      python: ['requests.get(', 'requests.post(', 'urlopen('],
      java: ['HttpClient', 'URL(', 'openConnection('],
      javascript: ['fetch(', 'axios.get(', 'http.request('],
    },
  };

  // 提取 sources
  const sourcePatternsForLang = sourcePatterns[language] || [];
  for (const pattern of sourcePatternsForLang) {
    if (code.includes(pattern)) {
      hints.sources.push(pattern.replace('(', '').trim());
    }
  }

  // 提取 sinks
  const sinkPatternsForVuln = sinkPatterns[vulnType]?.[language] || [];
  for (const pattern of sinkPatternsForVuln) {
    if (code.includes(pattern)) {
      hints.sinks.push(pattern.replace('(', '').trim());
    }
  }

  return hints;
}

/**
 * 生成漏洞案例 JSON
 */
function generateVulnCase(advisory, diff, language, vulnType) {
  const hints = identifySourceSinkHints(diff.before, language, vulnType);
  
  const caseId = `${language}_${vulnType.toLowerCase().replace(/\s+/g, '_')}_${advisory.ghsa_id}`;
  
  return {
    case_id: caseId,
    language: language,
    vulnerability_type: vulnType,
    source_code_before: diff.before,
    source_code_after: diff.after,
    source_function_hints: hints.sources,
    sink_function_hints: hints.sinks,
    notes: `${advisory.summary} (${advisory.ghsa_id})`,
    metadata: {
      ghsa_id: advisory.ghsa_id,
      cve_id: advisory.cve_id,
      severity: advisory.severity,
      published_at: advisory.published_at,
      url: advisory.html_url,
    },
  };
}

/**
 * 辅助函数
 */
function getEcosystem(language) {
  const map = {
    python: 'pip',
    java: 'maven',
    javascript: 'npm',
    go: 'go',
  };
  return map[language.toLowerCase()] || 'pip';
}

function getFileExtension(language) {
  const map = {
    python: 'py',
    java: 'java',
    javascript: 'js',
    go: 'go',
  };
  return map[language.toLowerCase()] || 'py';
}

/**
 * 主函数
 */
async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: node fetch_vuln_from_github.js <language> <vuln_type> [count]');
    console.error('Example: node fetch_vuln_from_github.js python "SQL Injection" 10');
    process.exit(1);
  }

  const language = args[0].toLowerCase();
  const vulnType = args[1];
  const count = parseInt(args[2] || '10');

  console.log(`\n=== Fetching ${count} ${vulnType} cases for ${language} ===\n`);

  // 1. 搜索 advisories
  const advisories = await searchAdvisories(language, vulnType, count);
  
  if (advisories.length === 0) {
    console.log('No advisories found. Try different search terms or set GITHUB_TOKEN.');
    return;
  }

  // 2. 处理每个 advisory
  const outputDir = path.resolve(__dirname, '../../datasets/vuln_cases');
  fs.mkdirSync(outputDir, { recursive: true });

  let successCount = 0;

  for (const advisory of advisories.slice(0, count)) {
    console.log(`\nProcessing ${advisory.ghsa_id}...`);
    
    // 获取详细信息
    const details = await getAdvisoryDetails(advisory.ghsa_id);
    if (!details || !details.references || details.references.length === 0) {
      console.log('  No patch references found, skipping.');
      continue;
    }

    // 查找 commit URL
    const commitRef = details.references.find(ref => 
      ref.url.includes('/commit/') || ref.url.includes('/pull/')
    );
    
    if (!commitRef) {
      console.log('  No commit URL found, skipping.');
      continue;
    }

    console.log(`  Fetching diff from ${commitRef.url}...`);
    
    // 获取 diff
    const diffText = await fetchCommitDiff(commitRef.url);
    if (!diffText) {
      console.log('  Failed to fetch diff, skipping.');
      continue;
    }

    // 解析 diff
    const diff = parseDiff(diffText, language);
    if (!diff || !diff.before || !diff.after) {
      console.log('  No valid diff found, skipping.');
      continue;
    }

    // 生成案例
    const vulnCase = generateVulnCase(advisory, diff, language, vulnType);
    
    // 保存到文件
    const outputPath = path.join(outputDir, `${vulnCase.case_id}.json`);
    fs.writeFileSync(outputPath, JSON.stringify(vulnCase, null, 2), 'utf8');
    
    console.log(`  ✓ Saved to ${outputPath}`);
    successCount++;

    // 避免触发速率限制
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  console.log(`\n=== Summary ===`);
  console.log(`Total processed: ${advisories.length}`);
  console.log(`Successfully extracted: ${successCount}`);
  console.log(`Output directory: ${outputDir}`);
  console.log('');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
