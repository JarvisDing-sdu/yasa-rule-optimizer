const express = require('express');
const { spawn } = require('child_process');
const fs = require('fs');
const fsPromises = require('fs').promises;
const path = require('path');
const axios = require('axios');
require('dotenv').config();

const app = express();
app.use(express.json({ limit: '2mb' }));
const WEB_PUBLIC_DIR = path.resolve(__dirname, '../../apps/web/public');
const WEB_INDEX_PATH = path.join(WEB_PUBLIC_DIR, 'index.html');
app.use(express.static(WEB_PUBLIC_DIR));

// 多语言配置
const LANG_CONFIG = {
  python: { analyzer: 'PythonAnalyzer', sdk: './uast4py' },
  go: { analyzer: 'GoAnalyzer', sdk: './uast4go' },
  java: { analyzer: 'JavaAnalyzer', sdk: './uast4java' },
  js: { analyzer: 'JavaScriptAnalyzer', sdk: './uast4js', engineLanguage: 'javascript' },
  php: { analyzer: 'PhpAnalyzer', sdk: '', engineLanguage: 'php' },
  c: { analyzer: 'CAnalyzer', sdk: '', engineLanguage: 'c' },
};

const DEFAULT_CHECKERS = {
  python: [
    'taint_flow_python_input',
    'taint_flow_python_input_inner',
    'taint_flow_python_django_input',
  ],
  go: ['taint_flow_go_input'],
  java: ['taint_flow_java_input', 'taint_flow_java_input_inner', 'taint_flow_spring_input'],
  js: ['taint_flow_js_input', 'taint_flow_egg_input', 'taint_flow_express_input'],
  php: ['taint_flow_php_input'],
  c: ['taint_flow_c_input'],
};

// 规则配置目录（按语言 + minimal/full 选择）
const RULES_MAYISHENG_DIR = path.resolve(__dirname, '../rules-mayisheng');

function getRuleConfigPath(lang, ruleMode) {
  const l = String(lang || 'python').toLowerCase();
  const mode = String(ruleMode || 'full').toLowerCase() === 'minimal' ? 'minimal' : 'full';
  const name = `rule_config_${l}_${mode}.json`;
  const candidate = path.join(RULES_MAYISHENG_DIR, name);
  if (fs.existsSync(candidate)) return candidate;
  throw new Error(`Rule config not found: ${name} (looked in rules-mayisheng/)`);
}

function getLangConfig(lang) {
  const key = String(lang || '').toLowerCase();
  return LANG_CONFIG[key] || null;
}

function inferLanguageFromTargetPath(targetPath) {
  const lower = String(targetPath || '').toLowerCase();
  if (lower.endsWith('.py')) return 'python';
  if (lower.endsWith('.go')) return 'go';
  if (lower.endsWith('.java')) return 'java';
  if (lower.endsWith('.js') || lower.endsWith('.ts') || lower.endsWith('.mjs') || lower.endsWith('.cjs')) return 'js';
  if (lower.endsWith('.php')) return 'php';
  if (lower.endsWith('.c') || lower.endsWith('.h')) return 'c';
  if (lower.includes('django') || lower.includes('flask') || lower.includes('langchain')) {
    return 'python';
  }
  return 'python';
}

function getTempCodeExtension(language) {
  const extMap = {
    python: 'py',
    java: 'java',
    go: 'go',
    js: 'js',
    javascript: 'js',
    php: 'php',
    c: 'c',
  };
  return extMap[String(language || '').toLowerCase()] || 'js';
}

function normalizeCheckerIds(lang, checkers) {
  if (typeof checkers === 'string' && checkers.trim()) return checkers.trim();
  if (Array.isArray(checkers) && checkers.length > 0) return checkers.join(',');
  const defaults = DEFAULT_CHECKERS[String(lang || '').toLowerCase()] || [];
  return defaults.join(',');
}

function safeJsonParse(text) {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (e) {
    return { ok: false, error: e };
  }
}

function getProviderConfig(provider, model, apiKeyOverride) {
  const key = String(provider || 'deepseek').toLowerCase();
  if (key === 'deepseek') {
    return {
      provider: 'deepseek',
      url: 'https://api.deepseek.com/chat/completions',
      apiKey: apiKeyOverride || process.env.DEEPSEEK_API_KEY,
      model: model || process.env.DEEPSEEK_MODEL || 'deepseek-chat',
    };
  }
  if (key === 'openai') {
    return {
      provider: 'openai',
      url: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1/chat/completions',
      apiKey: apiKeyOverride || process.env.OPENAI_API_KEY,
      model: model || process.env.OPENAI_MODEL || 'gpt-4o-mini',
    };
  }
  if (key === 'ollama') {
    return {
      provider: 'ollama',
      url: (process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434') + '/v1/chat/completions',
      apiKey: apiKeyOverride || process.env.OLLAMA_API_KEY || 'ollama',
      model: model || process.env.OLLAMA_MODEL || 'qwen2.5-coder:latest',
    };
  }
  return null;
}

async function callLLM({
  provider,
  model,
  apiKey,
  messages,
  temperature = 0.2,
}) {
  const cfg = getProviderConfig(provider, model, apiKey);
  if (!cfg) throw new Error(`Unsupported AI provider: ${provider}`);
  if (!cfg.apiKey) throw new Error(`Missing API key for provider: ${cfg.provider}`);

  const response = await axios.post(
    cfg.url,
    {
      model: cfg.model,
      messages,
      stream: false,
      temperature,
    },
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${cfg.apiKey}`,
      },
      timeout: 90000,
    }
  );

  const content = response?.data?.choices?.[0]?.message?.content?.trim();
  if (!content) throw new Error('Empty response from AI provider');
  return content;
}

async function loadReportArtifacts(reportDir) {
  const artifacts = {
    reportDir,
    diagnostics: [],
    findingsCount: 0,
    engineOutputPreview: '',
  };

  try {
    const diagPath = path.join(reportDir, 'yasa-diagnostics-log.txt');
    const text = await fsPromises.readFile(diagPath, 'utf8');
    artifacts.diagnostics = text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => safeJsonParse(line))
      .filter((x) => x.ok)
      .map((x) => x.value);
  } catch {
    // ignore
  }

  try {
    const outputPath = path.join(reportDir, 'engine-output.log');
    const output = await fsPromises.readFile(outputPath, 'utf8');
    const m = output.match(/# Total-findings\s*:\s*(\d+)/);
    artifacts.findingsCount = m ? Number(m[1]) : 0;
    artifacts.engineOutputPreview = output.slice(-8000);
  } catch {
    // ignore
  }

  return artifacts;
}

// 工具函数：调用 YASA 引擎
function runYasaScan({ lang, targetPath, checkers, reportId, ruleConfigPath }) {
  return new Promise((resolve, reject) => {
    const langConfig = getLangConfig(lang);
    if (!langConfig) {
      return reject(new Error(`Unsupported language: ${lang}`));
    }

    const yasaBinaryPath = path.resolve(__dirname, '../yasa-engine-linux-x64');
    const rulesPath = ruleConfigPath;
    const reportDir = path.resolve(__dirname, '../report', reportId);
    const projectRoot = path.dirname(yasaBinaryPath);
    const sourcePath = path.isAbsolute(targetPath)
      ? targetPath
      : path.resolve(projectRoot, targetPath);

    fs.mkdirSync(reportDir, { recursive: true });
    const engineOutputPath = path.join(reportDir, 'engine-output.log');
    const outputStream = fs.createWriteStream(engineOutputPath, { flags: 'a' });
    let stdoutBuffer = '';
    let stderrBuffer = '';

    const chmod = spawn('chmod', ['+x', yasaBinaryPath]);
    chmod.on('error', (err) => {
      console.error('chmod error:', err);
    });
    chmod.stderr.on('data', (data) => {
      console.error('[chmod stderr]', data.toString());
    });

    chmod.on('close', (code) => {
      if (code !== 0) {
        console.warn(`chmod exited with code ${code}, trying to run anyway...`);
      }

      const engineLang = langConfig.engineLanguage || lang;
      const args = [
        '--language',
        engineLang,
        '--analyzer',
        langConfig.analyzer,
        '--ruleConfigFile',
        rulesPath,
        '--checkerIds',
        checkers,
        '--entrypointMode',
        'BOTH',
        '--report',
        reportDir,
        sourcePath,
      ];
      if (langConfig.sdk) {
        args.splice(4, 0, '--uastSDKPath', langConfig.sdk);
      }

      console.log('Running YASA engine with args:', args.join(' '));

      const child = spawn(yasaBinaryPath, args, {
        cwd: path.dirname(yasaBinaryPath),
      });

      // 存储进程到全局 map，以便后续取消
      activeScanProcesses.set(reportId, { child, startTime: Date.now() });

      child.stdout.on('data', (data) => {
        const text = data.toString();
        stdoutBuffer += text;
        outputStream.write(text);
        process.stdout.write(`[yasa stdout] ${text}`);
      });

      child.stderr.on('data', (data) => {
        const text = data.toString();
        stderrBuffer += text;
        outputStream.write(text);
        process.stderr.write(`[yasa stderr] ${text}`);
      });

      child.on('error', (err) => {
        console.error('Failed to start YASA engine:', err);
        activeScanProcesses.delete(reportId);
        reject(err);
      });

      child.on('close', (exitCode) => {
        outputStream.end();
        activeScanProcesses.delete(reportId);
        const m = stdoutBuffer.match(/# Total-findings\s*:\s*(\d+)/);
        const findingsCount = m ? Number(m[1]) : 0;
        if (exitCode === 0) {
          resolve({ code: exitCode, reportDir, engineOutputPath, findingsCount, stderrText: stderrBuffer });
        } else {
          let errorMsg = `YASA 引擎执行失败 (exit code ${exitCode})`;
          
          // 根据错误信息给出更具体的提示
          if (stderrBuffer.includes('no such file or directory') || stderrBuffer.includes('cannot find')) {
            errorMsg += '\n\n原因：目标路径不存在或无法访问。请检查 Target Path 是否正确。';
          } else if (stderrBuffer.includes('permission denied')) {
            errorMsg += '\n\n原因：权限不足，无法访问目标路径。请检查文件权限。';
          } else if (stderrBuffer.includes('rule') || stderrBuffer.includes('config')) {
            errorMsg += '\n\n原因：规则配置文件错误或不存在。请检查规则模式和语言选择。';
          } else if (stderrBuffer.includes('analyzer') || stderrBuffer.includes('Analyzer')) {
            errorMsg += '\n\n原因：分析器不支持或配置错误。请检查语言选择。';
          } else if (stderrBuffer.includes('SDK') || stderrBuffer.includes('uast')) {
            errorMsg += '\n\n原因：UAST SDK 不存在或不兼容。请确保对应语言的 SDK 已安装。';
          } else if (stderrBuffer.length > 0) {
            errorMsg += `\n\n详细错误：${stderrBuffer.slice(0, 500)}`;
          }
          
          const error = new Error(errorMsg);
          error.code = exitCode;
          error.stderr = stderrBuffer;
          error.details = errorMsg;
          reject(error);
        }
      });
    });
  });
}

// 扫描核心接口
app.post('/api/scan', async (req, res) => {
  try {
    const {
      lang,
      targetPath,
      checkers,
      ruleMode,
    } = req.body || {};

    if (!targetPath) {
      return res.status(400).json({
        error: 'Missing required field: targetPath',
      });
    }

    const finalLang = (lang || inferLanguageFromTargetPath(targetPath)).toLowerCase();
    const finalCheckers = normalizeCheckerIds(finalLang, checkers);
    if (!finalCheckers) {
      return res.status(400).json({
        error: `No default checkerIds configured for language: ${finalLang}`,
      });
    }

    let ruleConfigPath;
    try {
      ruleConfigPath = getRuleConfigPath(finalLang, ruleMode);
    } catch (e) {
      return res.status(400).json({ error: e.message });
    }

    const reportId = Date.now().toString();

    const scanResult = await runYasaScan({
      lang: finalLang,
      targetPath,
      checkers: finalCheckers,
      reportId,
      ruleConfigPath,
    });

    res.json({
      success: true,
      reportId,
      language: finalLang,
      ruleMode: ruleMode || 'full',
      ruleConfigPath,
      checkerIds: finalCheckers.split(','),
      reportDir: scanResult.reportDir,
      findingsCount: scanResult.findingsCount || 0,
    });
  } catch (err) {
    console.error('Scan failed:', err);
    res.status(500).json({
      error: 'Scan failed',
      details: err.message || String(err),
    });
  }
});

app.get('/api/providers', (req, res) => {
  res.json({
    providers: [
      {
        id: 'deepseek',
        label: 'DeepSeek',
        defaultModel: process.env.DEEPSEEK_MODEL || 'deepseek-chat',
        needsApiKey: true,
      },
      {
        id: 'openai',
        label: 'OpenAI-compatible',
        defaultModel: process.env.OPENAI_MODEL || 'gpt-4o-mini',
        needsApiKey: true,
      },
    ],
  });
});

app.post('/api/analyze-report', async (req, res) => {
  try {
    const { reportId, reportDir, provider, model, apiKey, targetPath, language } =
      req.body || {};
    
    // 验证 API Key 必填
    if (!apiKey || !apiKey.trim()) {
      return res.status(400).json({ 
        error: 'API Key 必填',
        details: '请提供有效的 API Key 来调用 AI 分析服务'
      });
    }

    const resolvedReportDir =
      reportDir ||
      (reportId ? path.resolve(__dirname, '../report', String(reportId)) : null);
    if (!resolvedReportDir) {
      return res.status(400).json({ error: 'reportId or reportDir is required' });
    }

    const artifacts = await loadReportArtifacts(resolvedReportDir);
    const analysisText = await callLLM({
      provider: provider || 'deepseek',
      model,
      apiKey,
      temperature: 0.2,
      messages: [
        {
          role: 'system',
          content:
            '你是资深应用安全分析师。请根据扫描产物生成简洁、专业的漏洞分析报告，必须包含：漏洞类型、漏洞原理、调用链路摘要、修复建议。若证据不足请明确写出不确定点。',
        },
        {
          role: 'user',
          content: [
            `targetPath: ${targetPath || 'unknown'}`,
            `language: ${language || 'unknown'}`,
            `reportDir: ${resolvedReportDir}`,
            `findingsCount: ${artifacts.findingsCount}`,
            '',
            'diagnostics(JSON):',
            JSON.stringify(artifacts.diagnostics, null, 2),
            '',
            'engineOutput(last part):',
            artifacts.engineOutputPreview || '(empty)',
          ].join('\n'),
        },
      ],
    });

    res.json({
      success: true,
      reportDir: resolvedReportDir,
      findingsCount: artifacts.findingsCount,
      analysis: analysisText,
    });
  } catch (err) {
    res.status(500).json({
      error: 'Analyze report failed',
      details: err.message || String(err),
    });
  }
});

app.post('/api/chat', async (req, res) => {
  try {
    const { provider, model, apiKey, messages, context } = req.body || {};
    if (!Array.isArray(messages) || messages.length === 0) {
      return res.status(400).json({ error: 'messages is required' });
    }

    const aiMessages = [
      {
        role: 'system',
        content:
          '你是漏洞分析助手。回答时优先结合上下文中的扫描信息，输出清晰的风险说明与修复建议。',
      },
    ];
    if (context) {
      aiMessages.push({
        role: 'system',
        content: `context:\n${JSON.stringify(context, null, 2)}`,
      });
    }
    aiMessages.push(...messages);

    const reply = await callLLM({
      provider: provider || 'deepseek',
      model,
      apiKey,
      messages: aiMessages,
      temperature: 0.3,
    });

    res.json({ success: true, reply });
  } catch (err) {
    res.status(500).json({
      error: 'Chat failed',
      details: err.message || String(err),
    });
  }
});

app.post('/api/export-report', async (req, res) => {
  try {
    const { outputPath, format, reportMeta, analysis } = req.body || {};
    if (!outputPath) {
      return res.status(400).json({ error: 'outputPath is required' });
    }

    const target = path.isAbsolute(outputPath)
      ? outputPath
      : path.resolve(process.cwd(), outputPath);
    await fsPromises.mkdir(path.dirname(target), { recursive: true });

    const reportContent =
      String(format || 'markdown').toLowerCase() === 'json'
        ? JSON.stringify(
            {
              generatedAt: new Date().toISOString(),
              reportMeta: reportMeta || {},
              analysis: analysis || '',
            },
            null,
            2
          )
        : [
            '# Vulnerability Analysis Report',
            '',
            `- Generated At: ${new Date().toISOString()}`,
            `- Report ID: ${reportMeta?.reportId || 'unknown'}`,
            `- Language: ${reportMeta?.language || 'unknown'}`,
            `- Target Path: ${reportMeta?.targetPath || 'unknown'}`,
            `- Findings Count: ${reportMeta?.findingsCount ?? 'unknown'}`,
            '',
            '## AI Analysis',
            '',
            analysis || '(empty)',
            '',
          ].join('\n');

    await fsPromises.writeFile(target, reportContent, 'utf8');
    res.json({ success: true, outputPath: target });
  } catch (err) {
    res.status(500).json({
      error: 'Export report failed',
      details: err.message || String(err),
    });
  }
});

app.get('/', (req, res) => {
  res.sendFile(WEB_INDEX_PATH);
});

// 全局扫描进程管理
const activeScanProcesses = new Map();

// 工具函数：递归删除目录
async function removeDir(dirPath) {
  try {
    const entries = await fsPromises.readdir(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name);
      if (entry.isDirectory()) {
        await removeDir(fullPath);
      } else {
        await fsPromises.unlink(fullPath);
      }
    }
    await fsPromises.rmdir(dirPath);
  } catch (e) {
    console.warn(`Failed to remove dir ${dirPath}:`, e.message);
  }
}

// 取消扫描接口
app.post('/api/cancel-scan', async (req, res) => {
  try {
    const { reportId } = req.body || {};
    if (!reportId) {
      return res.status(400).json({ error: 'reportId is required' });
    }

    const scanProcess = activeScanProcesses.get(reportId);
    if (!scanProcess) {
      return res.status(404).json({ error: 'Scan process not found or already completed' });
    }

    // 杀死进程
    if (scanProcess.child && !scanProcess.child.killed) {
      scanProcess.child.kill('SIGTERM');
      console.log(`Killed scan process for reportId: ${reportId}`);
    }

    // 删除报告目录
    const reportDir = path.resolve(__dirname, '../report', reportId);
    await removeDir(reportDir);
    console.log(`Cleaned up report directory: ${reportDir}`);

    // 从活跃进程表中移除
    activeScanProcesses.delete(reportId);

    res.json({ success: true, message: 'Scan cancelled and cache cleaned' });
  } catch (err) {
    console.error('Cancel scan failed:', err);
    res.status(500).json({
      error: 'Cancel scan failed',
      details: err.message || String(err),
    });
  }
});

// ==================== 规则生成相关接口 ====================

const { RuleValidator } = require('../scripts/validate_rule.js');
const { RuleGenerationPipeline } = require('../scripts/rule_generation_pipeline.js');
const { FindingsComparator } = require('../scripts/compare_findings.js');

const ruleValidator = new RuleValidator();
const ruleGenerationPipeline = new RuleGenerationPipeline(callLLM);
const findingsComparator = new FindingsComparator();

// 加载现有规则 ID（用于唯一性检查）
ruleValidator.loadExistingRules('../rules-mayisheng');
ruleValidator.loadExistingRules('../../generated_rules/staging');
ruleValidator.loadExistingRules('../../generated_rules/candidate');
ruleValidator.loadExistingRules('../../generated_rules/production');

/**
 * POST /api/generate-rule-from-case
 * 
 * 从漏洞案例生成规则（Stage 1 + Stage 2）
 * 
 * 请求体：
 * {
 *   "vulnCase": { case_id, language, vulnerability_type, source_code_before, source_code_after, ... },
 *   "provider": "deepseek",
 *   "model": "deepseek-chat",
 *   "apiKey": "sk-xxx"
 * }
 */
app.post('/api/generate-rule-from-case', async (req, res) => {
  try {
    const { vulnCase, provider, model, apiKey } = req.body || {};

    if (!vulnCase || !vulnCase.case_id) {
      return res.status(400).json({ error: 'vulnCase with case_id is required' });
    }

    if (!apiKey || !apiKey.trim()) {
      return res.status(400).json({ error: 'API Key is required' });
    }

    // 加载规则示例（few-shot）
    const ruleExamplesPath = path.resolve(__dirname, '../../datasets/rule_examples');
    let ruleExamples = [];
    if (fs.existsSync(ruleExamplesPath)) {
      const files = fs.readdirSync(ruleExamplesPath).filter(f => f.endsWith('.json') && f !== 'README.json');
      if (files.length > 0) {
        ruleExamples = JSON.parse(fs.readFileSync(path.join(ruleExamplesPath, files[0]), 'utf8'));
      }
    }

    // 如果没有示例，从现有规则中提取一个
    if (ruleExamples.length === 0) {
      const lang = vulnCase.language || 'python';
      const ruleConfigPath = getRuleConfigPath(lang, 'full');
      const fullRules = JSON.parse(fs.readFileSync(ruleConfigPath, 'utf8'));
      ruleExamples = fullRules.slice(0, 1); // 取第一条作为示例
    }

    // 生成规则
    const result = await ruleGenerationPipeline.generateRuleFromCase(
      vulnCase,
      ruleExamples,
      provider || 'deepseek',
      model,
      apiKey
    );

    // 校验规则
    const validation = ruleValidator.validateRule(result.rule);

    // 如果校验通过，保存到 staging
    let savedPath = null;
    if (validation.valid) {
      const stagingDir = path.resolve(__dirname, '../../generated_rules/staging');
      fs.mkdirSync(stagingDir, { recursive: true });
      savedPath = path.join(stagingDir, `${result.rule.metadata.ruleId}.json`);
      fs.writeFileSync(savedPath, JSON.stringify(result.rule, null, 2), 'utf8');
      result.rule.metadata.validationStatus = 'valid';
    } else {
      result.rule.metadata.validationStatus = 'invalid';
    }

    res.json({
      success: true,
      description: result.description,
      rule: result.rule,
      validation,
      savedPath,
    });
  } catch (err) {
    console.error('Generate rule from case failed:', err);
    res.status(500).json({
      error: 'Generate rule from case failed',
      details: err.message || String(err),
    });
  }
});

/**
 * POST /api/validate-rule
 * 
 * 校验规则（独立接口）
 * 
 * 请求体：
 * {
 *   "rule": { ... }
 * }
 */
app.post('/api/validate-rule', async (req, res) => {
  try {
    const { rule } = req.body || {};

    if (!rule) {
      return res.status(400).json({ error: 'rule is required' });
    }

    const validation = ruleValidator.validateRule(rule);

    res.json({
      success: true,
      validation,
    });
  } catch (err) {
    console.error('Validate rule failed:', err);
    res.status(500).json({
      error: 'Validate rule failed',
      details: err.message || String(err),
    });
  }
});

/**
 * POST /api/evaluate-rule
 * 
 * 评估规则（用测试集扫描并对比）
 * 
 * 请求体：
 * {
 *   "rule": { ... },
 *   "testCases": [ { case_id, code, language, expected_findings: [...] }, ... ]
 * }
 */
app.post('/api/evaluate-rule', async (req, res) => {
  try {
    const { rule, testCases } = req.body || {};

    if (!rule) {
      return res.status(400).json({ error: 'rule is required' });
    }

    if (!testCases || !Array.isArray(testCases) || testCases.length === 0) {
      return res.status(400).json({ error: 'testCases array is required' });
    }

    // 1. 将规则临时写入文件
    const tempRuleDir = path.resolve(__dirname, '../report/temp_rules');
    fs.mkdirSync(tempRuleDir, { recursive: true });
    const tempRuleId = `temp_${Date.now()}`;
    const tempRulePath = path.join(tempRuleDir, `${tempRuleId}.json`);
    fs.writeFileSync(tempRulePath, JSON.stringify([rule], null, 2), 'utf8');

    // 2. 对每个测试案例执行扫描
    const scanResults = [];
    for (const testCase of testCases) {
      // 将测试代码写入临时文件
      const tempCodeDir = path.resolve(__dirname, '../report/temp_code');
      fs.mkdirSync(tempCodeDir, { recursive: true });
      const ext = getTempCodeExtension(testCase.language);
      const tempCodePath = path.join(tempCodeDir, `${testCase.case_id}.${ext}`);
      fs.writeFileSync(tempCodePath, testCase.code || '', 'utf8');

      // 执行扫描
      const reportId = `eval_${testCase.case_id}_${Date.now()}`;
      try {
        const scanResult = await runYasaScan({
          lang: testCase.language,
          targetPath: tempCodePath,
          checkers: normalizeCheckerIds(testCase.language, rule.checkerIds),
          reportId,
          ruleConfigPath: tempRulePath,
        });

        // 解析扫描结果
        const findings = findingsComparator.parseYasaReport(scanResult.reportDir);
        scanResults.push(findings);
      } catch (err) {
        console.error(`Scan failed for case ${testCase.case_id}:`, err.message);
        scanResults.push([]); // 扫描失败视为无发现
      }
    }

    // 3. 对比结果
    const comparison = findingsComparator.compareAll(testCases, scanResults);

    // 4. 清理临时文件
    try {
      fs.unlinkSync(tempRulePath);
    } catch (e) {
      // ignore
    }

    res.json({
      success: true,
      evaluation: comparison,
    });
  } catch (err) {
    console.error('Evaluate rule failed:', err);
    res.status(500).json({
      error: 'Evaluate rule failed',
      details: err.message || String(err),
    });
  }
});

/**
 * POST /api/optimize-rule-iteratively
 * 
 * 迭代优化规则（Stage 1 → 2 → 3 → 4 → 2 ...）
 * 
 * 请求体：
 * {
 *   "vulnCase": { ... },
 *   "testCases": [ ... ],
 *   "provider": "deepseek",
 *   "model": "deepseek-chat",
 *   "apiKey": "sk-xxx",
 *   "maxRounds": 3
 * }
 */
app.post('/api/optimize-rule-iteratively', async (req, res) => {
  try {
    const { vulnCase, testCases, provider, model, apiKey, maxRounds } = req.body || {};

    if (!vulnCase || !vulnCase.case_id) {
      return res.status(400).json({ error: 'vulnCase with case_id is required' });
    }

    if (!testCases || !Array.isArray(testCases) || testCases.length === 0) {
      return res.status(400).json({ error: 'testCases array is required' });
    }

    if (!apiKey || !apiKey.trim()) {
      return res.status(400).json({ error: 'API Key is required' });
    }

    // 加载规则示例
    const ruleExamplesPath = path.resolve(__dirname, '../../datasets/rule_examples');
    let ruleExamples = [];
    if (fs.existsSync(ruleExamplesPath)) {
      const files = fs.readdirSync(ruleExamplesPath).filter(f => f.endsWith('.json') && f !== 'README.json');
      if (files.length > 0) {
        ruleExamples = JSON.parse(fs.readFileSync(path.join(ruleExamplesPath, files[0]), 'utf8'));
      }
    }

    if (ruleExamples.length === 0) {
      const lang = vulnCase.language || 'python';
      const ruleConfigPath = getRuleConfigPath(lang, 'full');
      const fullRules = JSON.parse(fs.readFileSync(ruleConfigPath, 'utf8'));
      ruleExamples = fullRules.slice(0, 1);
    }

    // 定义评估函数（传给 pipeline）
    const evaluateFunc = async (rule, testCases) => {
      // 复用 /api/evaluate-rule 的逻辑
      const tempRuleDir = path.resolve(__dirname, '../report/temp_rules');
      fs.mkdirSync(tempRuleDir, { recursive: true });
      const tempRuleId = `temp_${Date.now()}`;
      const tempRulePath = path.join(tempRuleDir, `${tempRuleId}.json`);
      fs.writeFileSync(tempRulePath, JSON.stringify([rule], null, 2), 'utf8');

      const scanResults = [];
      for (const testCase of testCases) {
        const tempCodeDir = path.resolve(__dirname, '../report/temp_code');
        fs.mkdirSync(tempCodeDir, { recursive: true });
        const ext = getTempCodeExtension(testCase.language);
        const tempCodePath = path.join(tempCodeDir, `${testCase.case_id}.${ext}`);
        fs.writeFileSync(tempCodePath, testCase.code || '', 'utf8');

        const reportId = `eval_${testCase.case_id}_${Date.now()}`;
        try {
          const scanResult = await runYasaScan({
            lang: testCase.language,
            targetPath: tempCodePath,
            checkers: normalizeCheckerIds(testCase.language, rule.checkerIds),
            reportId,
            ruleConfigPath: tempRulePath,
          });

          const findings = findingsComparator.parseYasaReport(scanResult.reportDir);
          scanResults.push(findings);
        } catch (err) {
          console.error(`Scan failed for case ${testCase.case_id}:`, err.message);
          scanResults.push([]);
        }
      }

      const comparison = findingsComparator.compareAll(testCases, scanResults);

      try {
        fs.unlinkSync(tempRulePath);
      } catch (e) {
        // ignore
      }

      return comparison;
    };

    // 执行迭代优化
    const result = await ruleGenerationPipeline.optimizeRuleIteratively(
      vulnCase,
      ruleExamples,
      testCases,
      evaluateFunc,
      provider || 'deepseek',
      model,
      apiKey,
      maxRounds || 3
    );

    // 保存最佳规则到 candidate
    let savedPath = null;
    if (result.bestRule) {
      const validation = ruleValidator.validateRule(result.bestRule);
      if (validation.valid && result.bestF1 >= 0.7) {
        const candidateDir = path.resolve(__dirname, '../../generated_rules/candidate');
        fs.mkdirSync(candidateDir, { recursive: true });
        savedPath = path.join(candidateDir, `${result.bestRule.metadata.ruleId}.json`);
        fs.writeFileSync(savedPath, JSON.stringify(result.bestRule, null, 2), 'utf8');
      }
    }

    // 保存迭代日志
    const logDir = path.resolve(__dirname, '../../iteration_logs');
    fs.mkdirSync(logDir, { recursive: true });
    const logPath = path.join(logDir, `${vulnCase.case_id}_${Date.now()}.json`);
    fs.writeFileSync(logPath, JSON.stringify(result.iterationLog, null, 2), 'utf8');

    res.json({
      success: true,
      bestRule: result.bestRule,
      bestF1: result.bestF1,
      iterationLog: result.iterationLog,
      savedPath,
      logPath,
    });
  } catch (err) {
    console.error('Optimize rule iteratively failed:', err);
    res.status(500).json({
      error: 'Optimize rule iteratively failed',
      details: err.message || String(err),
    });
  }
});

// ==================== 原有代码 ====================

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`YASA API agent listening on port ${PORT}`);
});

module.exports = app;
