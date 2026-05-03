const fs = require('fs');
const path = require('path');

/**
 * LLM 规则生成管道
 * 
 * 实现论文中的 4 阶段流程：
 * - Stage 1 (LLM-1): 漏洞案例 → 结构化描述
 * - Stage 2 (LLM-2): 描述 + 规则示例 → 候选规则
 * - Stage 3 (LLM-3): FP/FN 分析 → 改进建议
 * - Stage 4 (LLM-4): 原始 prompt + 改进建议 → 优化后的 prompt
 */

class RuleGenerationPipeline {
  constructor(callLLMFunc) {
    this.callLLM = callLLMFunc;
    this.promptsDir = path.resolve(__dirname, '../../prompts');
    this.loadPromptTemplates();
  }

  /**
   * 加载 prompt 模板
   */
  loadPromptTemplates() {
    this.prompts = {
      stage1: fs.readFileSync(path.join(this.promptsDir, 'stage1_vulnerability_description.md'), 'utf8'),
      stage2: fs.readFileSync(path.join(this.promptsDir, 'stage2_rule_generation.md'), 'utf8'),
      stage3: fs.readFileSync(path.join(this.promptsDir, 'stage3_fp_fn_analysis.md'), 'utf8'),
      stage4: fs.readFileSync(path.join(this.promptsDir, 'stage4_prompt_refinement.md'), 'utf8'),
    };
  }

  /**
   * Stage 1: 生成结构化漏洞描述
   * 
   * @param {Object} vulnCase - 漏洞案例
   * @param {string} vulnCase.case_id
   * @param {string} vulnCase.language
   * @param {string} vulnCase.vulnerability_type
   * @param {string} vulnCase.source_code_before
   * @param {string} vulnCase.source_code_after
   * @param {Array<string>} vulnCase.source_function_hints
   * @param {Array<string>} vulnCase.sink_function_hints
   * @returns {Promise<Object>} 结构化描述 JSON
   */
  async stage1_generateDescription(vulnCase, provider, model, apiKey) {
    const userPrompt = [
      `Case ID: ${vulnCase.case_id}`,
      `Language: ${vulnCase.language}`,
      `Vulnerability Type: ${vulnCase.vulnerability_type}`,
      '',
      '=== Source Code Before Fix ===',
      vulnCase.source_code_before || '(empty)',
      '',
      '=== Source Code After Fix ===',
      vulnCase.source_code_after || '(empty)',
      '',
      '=== Source Function Hints ===',
      JSON.stringify(vulnCase.source_function_hints || [], null, 2),
      '',
      '=== Sink Function Hints ===',
      JSON.stringify(vulnCase.sink_function_hints || [], null, 2),
      '',
      'Please generate a structured vulnerability description following the output format specified in the system prompt.',
    ].join('\n');

    const response = await this.callLLM({
      provider,
      model,
      apiKey,
      messages: [
        { role: 'system', content: this.prompts.stage1 },
        { role: 'user', content: userPrompt },
      ],
      temperature: 0.2,
    });

    return this.parseJSON(response, 'stage1');
  }

  /**
   * Stage 2: 生成候选规则
   * 
   * @param {Object} description - Stage 1 输出的结构化描述
   * @param {Array<Object>} ruleExamples - 规则示例（few-shot）
   * @param {string} language - 目标语言
   * @returns {Promise<Object>} 候选规则 JSON
   */
  async stage2_generateRule(description, ruleExamples, language, provider, model, apiKey) {
    const userPrompt = [
      `Target Language: ${language}`,
      '',
      '=== Vulnerability Description ===',
      JSON.stringify(description, null, 2),
      '',
      '=== Rule Format Examples ===',
      JSON.stringify(ruleExamples, null, 2),
      '',
      '=== Requirements ===',
      '- Rule ID must be unique (format: generated_<language>_<vulnType>_<timestamp>)',
      '- Use semantic patterns (TaintSource, FuncCallTaintSink, etc.)',
      '- Include metadata section with: ruleId, generatedAt, caseId, language, vulnerabilityType',
      '- Follow YASA rule structure exactly',
      '',
      'Please generate a candidate rule following the output format specified in the system prompt.',
    ].join('\n');

    const response = await this.callLLM({
      provider,
      model,
      apiKey,
      messages: [
        { role: 'system', content: this.prompts.stage2 },
        { role: 'user', content: userPrompt },
      ],
      temperature: 0.2,
    });

    return this.parseJSON(response, 'stage2');
  }

  /**
   * Stage 3: 分析 FP/FN 并生成改进建议
   * 
   * @param {Object} evaluationResult - 评估结果
   * @param {Array} evaluationResult.fp - 误报案例
   * @param {Array} evaluationResult.fn - 漏报案例
   * @param {Object} currentRule - 当前规则
   * @returns {Promise<Object>} 改进建议 JSON
   */
  async stage3_analyzeFpFn(evaluationResult, currentRule, provider, model, apiKey) {
    const userPrompt = [
      '=== Current Rule ===',
      JSON.stringify(currentRule, null, 2),
      '',
      '=== False Positives (over-matched) ===',
      JSON.stringify(evaluationResult.fp || [], null, 2),
      '',
      '=== False Negatives (missed) ===',
      JSON.stringify(evaluationResult.fn || [], null, 2),
      '',
      'Please analyze these issues and provide structured improvement suggestions.',
    ].join('\n');

    const response = await this.callLLM({
      provider,
      model,
      apiKey,
      messages: [
        { role: 'system', content: this.prompts.stage3 },
        { role: 'user', content: userPrompt },
      ],
      temperature: 0.3,
    });

    return this.parseJSON(response, 'stage3');
  }

  /**
   * Stage 4: 优化 prompt
   * 
   * @param {string} originalPrompt - 原始 stage2 prompt
   * @param {Object} improvements - Stage 3 输出的改进建议
   * @returns {Promise<string>} 优化后的 prompt
   */
  async stage4_refinePrompt(originalPrompt, improvements, provider, model, apiKey) {
    const userPrompt = [
      '=== Original Rule Generation Prompt ===',
      originalPrompt,
      '',
      '=== Improvement Suggestions ===',
      JSON.stringify(improvements, null, 2),
      '',
      'Please merge these improvements into the original prompt while preserving the generation goal.',
    ].join('\n');

    const response = await this.callLLM({
      provider,
      model,
      apiKey,
      messages: [
        { role: 'system', content: this.prompts.stage4 },
        { role: 'user', content: userPrompt },
      ],
      temperature: 0.2,
    });

    return response.trim();
  }

  /**
   * 解析 LLM 返回的 JSON（容错处理）
   */
  parseJSON(text, stage) {
    // 尝试提取 JSON 代码块
    const jsonBlockMatch = text.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonBlockMatch) {
      text = jsonBlockMatch[1];
    }

    // 尝试解析
    try {
      return JSON.parse(text.trim());
    } catch (e) {
      throw new Error(`Stage ${stage} failed to parse JSON: ${e.message}\n\nRaw response:\n${text}`);
    }
  }

  /**
   * 完整单轮生成流程（Stage 1 + Stage 2）
   */
  async generateRuleFromCase(vulnCase, ruleExamples, provider, model, apiKey) {
    console.log(`[Pipeline] Stage 1: Generating description for case ${vulnCase.case_id}...`);
    const description = await this.stage1_generateDescription(vulnCase, provider, model, apiKey);
    
    console.log(`[Pipeline] Stage 2: Generating rule from description...`);
    const rule = await this.stage2_generateRule(description, ruleExamples, vulnCase.language, provider, model, apiKey);
    
    // 补充 metadata（如果 LLM 没生成完整）
    if (!rule.metadata) rule.metadata = {};
    rule.metadata.caseId = vulnCase.case_id;
    rule.metadata.language = vulnCase.language;
    rule.metadata.vulnerabilityType = vulnCase.vulnerability_type;
    rule.metadata.generatedAt = new Date().toISOString();
    rule.metadata.generatedBy = 'LLM-Pipeline';
    rule.metadata.iterationRound = 1;
    rule.metadata.validationStatus = 'pending';
    
    if (!rule.metadata.ruleId) {
      const timestamp = Date.now();
      rule.metadata.ruleId = `generated_${vulnCase.language}_${vulnCase.vulnerability_type}_${timestamp}`.replace(/\s+/g, '_');
    }

    return { description, rule };
  }

  /**
   * 完整迭代优化流程（Stage 1 → 2 → 3 → 4 → 2 ...）
   */
  async optimizeRuleIteratively(vulnCase, ruleExamples, testCases, evaluateFunc, provider, model, apiKey, maxRounds = 3) {
    const iterationLog = [];
    let currentPrompt = this.prompts.stage2;
    let bestRule = null;
    let bestF1 = 0;

    console.log(`[Pipeline] Starting iterative optimization (max ${maxRounds} rounds)...`);

    for (let round = 1; round <= maxRounds; round++) {
      console.log(`\n[Pipeline] === Round ${round}/${maxRounds} ===`);
      
      // Stage 1: 生成描述（只在第一轮）
      let description;
      if (round === 1) {
        console.log(`[Pipeline] Stage 1: Generating description...`);
        description = await this.stage1_generateDescription(vulnCase, provider, model, apiKey);
      } else {
        description = iterationLog[0].description; // 复用第一轮的描述
      }

      // Stage 2: 生成规则（使用当前 prompt）
      console.log(`[Pipeline] Stage 2: Generating rule (using ${round === 1 ? 'original' : 'refined'} prompt)...`);
      const rule = await this.stage2_generateRule(description, ruleExamples, vulnCase.language, provider, model, apiKey);
      
      // 补充 metadata
      if (!rule.metadata) rule.metadata = {};
      rule.metadata.caseId = vulnCase.case_id;
      rule.metadata.language = vulnCase.language;
      rule.metadata.vulnerabilityType = vulnCase.vulnerability_type;
      rule.metadata.generatedAt = new Date().toISOString();
      rule.metadata.generatedBy = 'LLM-Pipeline';
      rule.metadata.iterationRound = round;
      rule.metadata.validationStatus = 'pending';
      
      if (!rule.metadata.ruleId) {
        const timestamp = Date.now();
        rule.metadata.ruleId = `generated_${vulnCase.language}_${vulnCase.vulnerability_type}_r${round}_${timestamp}`.replace(/\s+/g, '_');
      }

      // 评估规则
      console.log(`[Pipeline] Evaluating rule against ${testCases.length} test cases...`);
      const evalResult = await evaluateFunc(rule, testCases);
      
      const f1 = evalResult.metrics.f1 || 0;
      console.log(`[Pipeline] Metrics: Precision=${evalResult.metrics.precision.toFixed(2)}, Recall=${evalResult.metrics.recall.toFixed(2)}, F1=${f1.toFixed(2)}`);

      // 记录本轮结果
      iterationLog.push({
        round,
        description,
        rule,
        evaluation: evalResult,
        prompt: currentPrompt,
      });

      // 更新最佳规则
      if (f1 > bestF1) {
        bestF1 = f1;
        bestRule = rule;
        console.log(`[Pipeline] New best rule found (F1=${f1.toFixed(2)})`);
      }

      // 如果 F1 达到阈值，提前结束
      if (f1 >= 0.95) {
        console.log(`[Pipeline] F1 score >= 0.95, stopping early.`);
        break;
      }

      // 如果不是最后一轮，执行 Stage 3 + Stage 4
      if (round < maxRounds) {
        console.log(`[Pipeline] Stage 3: Analyzing FP/FN...`);
        const improvements = await this.stage3_analyzeFpFn(evalResult, rule, provider, model, apiKey);
        
        console.log(`[Pipeline] Stage 4: Refining prompt...`);
        currentPrompt = await this.stage4_refinePrompt(currentPrompt, improvements, provider, model, apiKey);
      }
    }

    console.log(`\n[Pipeline] Optimization complete. Best F1: ${bestF1.toFixed(2)}`);

    return {
      bestRule,
      bestF1,
      iterationLog,
    };
  }
}

module.exports = { RuleGenerationPipeline };
