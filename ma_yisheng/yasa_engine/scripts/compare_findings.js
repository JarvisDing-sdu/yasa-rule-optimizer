const fs = require('fs');
const path = require('path');

/**
 * 规则评估对比器
 * 
 * 功能：
 * 1. 对比扫描结果与预期结果
 * 2. 分类：TP（真阳性）、FP（误报）、FN（漏报）、TN（真阴性）
 * 3. 计算指标：Precision、Recall、F1
 */

class FindingsComparator {
  /**
   * 对比单个测试案例的扫描结果
   * 
   * @param {Object} testCase - 测试案例
   * @param {string} testCase.case_id
   * @param {string} testCase.code - 待扫描代码
   * @param {Array} testCase.expected_findings - 预期发现的漏洞
   * @param {Array} actualFindings - 实际扫描结果（从 YASA 引擎输出解析）
   * @returns {Object} 对比结果
   */
  compareCase(testCase, actualFindings) {
    const expected = testCase.expected_findings || [];
    const actual = actualFindings || [];

    const tp = []; // 真阳性：预期有且实际检出
    const fp = []; // 误报：预期无但实际检出
    const fn = []; // 漏报：预期有但实际未检出
    
    // 简化版匹配逻辑：按漏洞类型匹配
    // 实际项目中可能需要更精细的匹配（如行号、函数名等）
    
    const expectedTypes = new Set(expected.map(e => e.vulnerability_type));
    const actualTypes = new Set(actual.map(a => a.vulnerability_type || a.attribute));

    // 计算 TP 和 FN
    for (const exp of expected) {
      const expType = exp.vulnerability_type;
      const matched = actual.find(a => 
        (a.vulnerability_type === expType || a.attribute?.includes(expType))
      );
      
      if (matched) {
        tp.push({
          case_id: testCase.case_id,
          expected: exp,
          actual: matched,
          match_type: 'TP',
        });
      } else {
        fn.push({
          case_id: testCase.case_id,
          expected: exp,
          actual: null,
          match_type: 'FN',
          reason: `Expected ${expType} but not detected`,
        });
      }
    }

    // 计算 FP
    for (const act of actual) {
      const actType = act.vulnerability_type || act.attribute;
      const matched = expected.find(e => 
        e.vulnerability_type === actType || actType?.includes(e.vulnerability_type)
      );
      
      if (!matched) {
        fp.push({
          case_id: testCase.case_id,
          expected: null,
          actual: act,
          match_type: 'FP',
          reason: `Unexpected detection: ${actType}`,
        });
      }
    }

    return { tp, fp, fn };
  }

  /**
   * 对比多个测试案例
   * 
   * @param {Array<Object>} testCases - 测试案例列表
   * @param {Array<Object>} scanResults - 扫描结果列表（与 testCases 一一对应）
   * @returns {Object} 汇总结果
   */
  compareAll(testCases, scanResults) {
    const allTp = [];
    const allFp = [];
    const allFn = [];

    testCases.forEach((testCase, idx) => {
      const actualFindings = scanResults[idx] || [];
      const result = this.compareCase(testCase, actualFindings);
      
      allTp.push(...result.tp);
      allFp.push(...result.fp);
      allFn.push(...result.fn);
    });

    const metrics = this.calculateMetrics(allTp.length, allFp.length, allFn.length);

    return {
      tp: allTp,
      fp: allFp,
      fn: allFn,
      metrics,
      summary: {
        total_cases: testCases.length,
        tp_count: allTp.length,
        fp_count: allFp.length,
        fn_count: allFn.length,
        ...metrics,
      },
    };
  }

  /**
   * 计算评估指标
   */
  calculateMetrics(tpCount, fpCount, fnCount) {
    const precision = tpCount + fpCount > 0 ? tpCount / (tpCount + fpCount) : 0;
    const recall = tpCount + fnCount > 0 ? tpCount / (tpCount + fnCount) : 0;
    const f1 = precision + recall > 0 ? (2 * precision * recall) / (precision + recall) : 0;

    return {
      precision: parseFloat(precision.toFixed(4)),
      recall: parseFloat(recall.toFixed(4)),
      f1: parseFloat(f1.toFixed(4)),
    };
  }

  /**
   * 从 YASA 扫描产物中解析 findings
   * 
   * @param {string} reportDir - 报告目录
   * @returns {Array} findings 列表
   */
  parseYasaReport(reportDir) {
    const findings = [];
    
    try {
      // 读取 diagnostics log
      const diagPath = path.join(reportDir, 'yasa-diagnostics-log.txt');
      if (fs.existsSync(diagPath)) {
        const lines = fs.readFileSync(diagPath, 'utf8').split('\n');
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const diag = JSON.parse(line);
            if (diag.severity === 'error' || diag.severity === 'warning') {
              findings.push({
                vulnerability_type: diag.code || diag.message,
                attribute: diag.code,
                location: diag.location,
                message: diag.message,
              });
            }
          } catch (e) {
            // 忽略非 JSON 行
          }
        }
      }

      // 读取 engine output（备用）
      const outputPath = path.join(reportDir, 'engine-output.log');
      if (fs.existsSync(outputPath) && findings.length === 0) {
        const output = fs.readFileSync(outputPath, 'utf8');
        // 简单解析：查找 "Total-findings" 行
        const match = output.match(/# Total-findings\s*:\s*(\d+)/);
        if (match && parseInt(match[1]) > 0) {
          // 如果有 findings 但 diagnostics 为空，说明格式可能不同
          // 这里可以根据实际 YASA 输出格式进一步解析
          findings.push({
            vulnerability_type: 'Unknown',
            attribute: 'UnknownVulnerability',
            message: 'Detected by YASA but details not parsed',
          });
        }
      }
    } catch (e) {
      console.error(`Failed to parse YASA report from ${reportDir}:`, e.message);
    }

    return findings;
  }
}

/**
 * CLI 入口（用于独立测试）
 */
function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: node compare_findings.js <test_cases.json> <scan_results.json>');
    process.exit(1);
  }

  const testCasesFile = args[0];
  const scanResultsFile = args[1];

  if (!fs.existsSync(testCasesFile)) {
    console.error(`File not found: ${testCasesFile}`);
    process.exit(1);
  }
  if (!fs.existsSync(scanResultsFile)) {
    console.error(`File not found: ${scanResultsFile}`);
    process.exit(1);
  }

  const testCases = JSON.parse(fs.readFileSync(testCasesFile, 'utf8'));
  const scanResults = JSON.parse(fs.readFileSync(scanResultsFile, 'utf8'));

  const comparator = new FindingsComparator();
  const result = comparator.compareAll(testCases, scanResults);

  console.log('\n=== Evaluation Result ===\n');
  console.log('Summary:');
  console.log(`  Total Cases: ${result.summary.total_cases}`);
  console.log(`  TP (True Positive): ${result.summary.tp_count}`);
  console.log(`  FP (False Positive): ${result.summary.fp_count}`);
  console.log(`  FN (False Negative): ${result.summary.fn_count}`);
  console.log('');
  console.log('Metrics:');
  console.log(`  Precision: ${result.metrics.precision.toFixed(4)}`);
  console.log(`  Recall: ${result.metrics.recall.toFixed(4)}`);
  console.log(`  F1 Score: ${result.metrics.f1.toFixed(4)}`);
  console.log('');

  if (result.fp.length > 0) {
    console.log('False Positives:');
    result.fp.forEach((fp, i) => {
      console.log(`  ${i + 1}. ${fp.case_id}: ${fp.reason}`);
    });
    console.log('');
  }

  if (result.fn.length > 0) {
    console.log('False Negatives:');
    result.fn.forEach((fn, i) => {
      console.log(`  ${i + 1}. ${fn.case_id}: ${fn.reason}`);
    });
    console.log('');
  }
}

if (require.main === module) {
  main();
}

module.exports = { FindingsComparator };
