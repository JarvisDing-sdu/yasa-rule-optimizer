const fs = require('fs');
const path = require('path');
const Ajv = require('ajv');
const addFormats = require('ajv-formats');

/**
 * YASA 规则校验器
 * 
 * 功能：
 * 1. JSON Schema 结构校验
 * 2. YASA 语义规则校验
 * 3. 规则 ID 唯一性检查
 */

class RuleValidator {
  constructor() {
    this.ajv = new Ajv({ allErrors: true, strict: false });
    addFormats(this.ajv);
    
    // 加载 schema
    const schemaPath = path.resolve(__dirname, '../../schemas/generated-rule.schema.json');
    this.schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
    this.validate = this.ajv.compile(this.schema);
    
    // 已存在的规则 ID 集合（用于唯一性检查）
    this.existingRuleIds = new Set();
  }

  /**
   * 加载现有规则配置，提取所有 ruleId
   */
  loadExistingRules(rulesDir) {
    const rulesPath = path.resolve(__dirname, rulesDir);
    if (!fs.existsSync(rulesPath)) return;
    
    const files = fs.readdirSync(rulesPath).filter(f => f.endsWith('.json'));
    for (const file of files) {
      try {
        const content = JSON.parse(fs.readFileSync(path.join(rulesPath, file), 'utf8'));
        if (Array.isArray(content)) {
          content.forEach(rule => {
            if (rule.metadata && rule.metadata.ruleId) {
              this.existingRuleIds.add(rule.metadata.ruleId);
            }
          });
        }
      } catch (e) {
        console.warn(`Failed to load ${file}:`, e.message);
      }
    }
  }

  /**
   * 主校验入口
   */
  validateRule(rule) {
    const errors = [];
    const warnings = [];

    // 1. JSON Schema 校验
    const schemaValid = this.validate(rule);
    if (!schemaValid) {
      errors.push({
        type: 'schema',
        message: 'JSON Schema validation failed',
        details: this.validate.errors,
      });
    }

    // 2. 必填字段检查
    if (!rule.checkerIds || rule.checkerIds.length === 0) {
      errors.push({ type: 'required', field: 'checkerIds', message: 'checkerIds is required and must not be empty' });
    }

    if (!rule.sources || Object.keys(rule.sources).length === 0) {
      errors.push({ type: 'required', field: 'sources', message: 'sources must contain at least one source type' });
    }

    if (!rule.sinks || Object.keys(rule.sinks).length === 0) {
      errors.push({ type: 'required', field: 'sinks', message: 'sinks must contain at least one sink type' });
    }

    // 3. 语义校验：sources
    if (rule.sources) {
      this.validateSources(rule.sources, errors, warnings);
    }

    // 4. 语义校验：sinks
    if (rule.sinks) {
      this.validateSinks(rule.sinks, errors, warnings);
    }

    // 5. 规则 ID 唯一性检查
    if (rule.metadata && rule.metadata.ruleId) {
      if (this.existingRuleIds.has(rule.metadata.ruleId)) {
        errors.push({
          type: 'uniqueness',
          field: 'metadata.ruleId',
          message: `Rule ID "${rule.metadata.ruleId}" already exists`,
        });
      }
    } else {
      warnings.push({
        type: 'metadata',
        field: 'metadata.ruleId',
        message: 'Rule ID not specified in metadata',
      });
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  /**
   * 校验 sources 语义
   */
  validateSources(sources, errors, warnings) {
    const validSourceTypes = ['TaintSource', 'FuncCallReturnValueTaintSource', 'FuncCallArgTaintSource'];
    
    for (const [sourceType, sourceList] of Object.entries(sources)) {
      if (!validSourceTypes.includes(sourceType)) {
        errors.push({
          type: 'semantic',
          field: `sources.${sourceType}`,
          message: `Invalid source type "${sourceType}". Must be one of: ${validSourceTypes.join(', ')}`,
        });
        continue;
      }

      if (!Array.isArray(sourceList)) {
        errors.push({
          type: 'semantic',
          field: `sources.${sourceType}`,
          message: `Source type "${sourceType}" must be an array`,
        });
        continue;
      }

      sourceList.forEach((source, idx) => {
        // TaintSource 必须有 path
        if (sourceType === 'TaintSource' && !source.path) {
          errors.push({
            type: 'semantic',
            field: `sources.${sourceType}[${idx}].path`,
            message: 'TaintSource must have "path" field',
          });
        }

        // FuncCallReturnValueTaintSource 必须有 fsig 和 values
        if (sourceType === 'FuncCallReturnValueTaintSource') {
          if (!source.fsig) {
            errors.push({
              type: 'semantic',
              field: `sources.${sourceType}[${idx}].fsig`,
              message: 'FuncCallReturnValueTaintSource must have "fsig" field',
            });
          }
          if (!source.values || !Array.isArray(source.values)) {
            errors.push({
              type: 'semantic',
              field: `sources.${sourceType}[${idx}].values`,
              message: 'FuncCallReturnValueTaintSource must have "values" array',
            });
          }
        }

        // FuncCallArgTaintSource 必须有 fsig 和 args
        if (sourceType === 'FuncCallArgTaintSource') {
          if (!source.fsig) {
            errors.push({
              type: 'semantic',
              field: `sources.${sourceType}[${idx}].fsig`,
              message: 'FuncCallArgTaintSource must have "fsig" field',
            });
          }
          if (!source.args || !Array.isArray(source.args)) {
            errors.push({
              type: 'semantic',
              field: `sources.${sourceType}[${idx}].args`,
              message: 'FuncCallArgTaintSource must have "args" array',
            });
          }
        }

        // scopeFile 和 scopeFunc 必填
        if (!source.scopeFile) {
          errors.push({
            type: 'semantic',
            field: `sources.${sourceType}[${idx}].scopeFile`,
            message: 'scopeFile is required (use "all" for global scope)',
          });
        }
        if (!source.scopeFunc) {
          errors.push({
            type: 'semantic',
            field: `sources.${sourceType}[${idx}].scopeFunc`,
            message: 'scopeFunc is required (use "all" for global scope)',
          });
        }
      });
    }
  }

  /**
   * 校验 sinks 语义
   */
  validateSinks(sinks, errors, warnings) {
    const validSinkTypes = ['FuncCallTaintSink'];
    
    for (const [sinkType, sinkList] of Object.entries(sinks)) {
      if (!validSinkTypes.includes(sinkType)) {
        errors.push({
          type: 'semantic',
          field: `sinks.${sinkType}`,
          message: `Invalid sink type "${sinkType}". Must be one of: ${validSinkTypes.join(', ')}`,
        });
        continue;
      }

      if (!Array.isArray(sinkList)) {
        errors.push({
          type: 'semantic',
          field: `sinks.${sinkType}`,
          message: `Sink type "${sinkType}" must be an array`,
        });
        continue;
      }

      sinkList.forEach((sink, idx) => {
        // 必须有 fsig 或 fregex（至少一个）
        if (!sink.fsig && !sink.fregex) {
          errors.push({
            type: 'semantic',
            field: `sinks.${sinkType}[${idx}]`,
            message: 'FuncCallTaintSink must have either "fsig" or "fregex"',
          });
        }

        // 必须有 args
        if (!sink.args || !Array.isArray(sink.args)) {
          errors.push({
            type: 'semantic',
            field: `sinks.${sinkType}[${idx}].args`,
            message: 'FuncCallTaintSink must have "args" array',
          });
        }

        // 必须有 attribute
        if (!sink.attribute) {
          errors.push({
            type: 'semantic',
            field: `sinks.${sinkType}[${idx}].attribute`,
            message: 'FuncCallTaintSink must have "attribute" field (e.g., PythonSqlInjection)',
          });
        }

        // 如果同时有 fsig 和 fregex，给出警告
        if (sink.fsig && sink.fregex) {
          warnings.push({
            type: 'semantic',
            field: `sinks.${sinkType}[${idx}]`,
            message: 'Both "fsig" and "fregex" are specified. "fsig" will take precedence.',
          });
        }
      });
    }
  }
}

/**
 * CLI 入口
 */
function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: node validate_rule.js <rule.json>');
    process.exit(1);
  }

  const ruleFile = args[0];
  if (!fs.existsSync(ruleFile)) {
    console.error(`File not found: ${ruleFile}`);
    process.exit(1);
  }

  const validator = new RuleValidator();
  
  // 加载现有规则（用于唯一性检查）
  validator.loadExistingRules('../rules-mayisheng');
  validator.loadExistingRules('../../generated_rules/staging');
  validator.loadExistingRules('../../generated_rules/candidate');
  validator.loadExistingRules('../../generated_rules/production');

  const rule = JSON.parse(fs.readFileSync(ruleFile, 'utf8'));
  const result = validator.validateRule(rule);

  console.log('\n=== Rule Validation Result ===\n');
  console.log(`Valid: ${result.valid ? '✓ YES' : '✗ NO'}\n`);

  if (result.errors.length > 0) {
    console.log('Errors:');
    result.errors.forEach((err, i) => {
      console.log(`  ${i + 1}. [${err.type}] ${err.field || ''}: ${err.message}`);
      if (err.details) {
        console.log(`     Details: ${JSON.stringify(err.details, null, 2)}`);
      }
    });
    console.log('');
  }

  if (result.warnings.length > 0) {
    console.log('Warnings:');
    result.warnings.forEach((warn, i) => {
      console.log(`  ${i + 1}. [${warn.type}] ${warn.field || ''}: ${warn.message}`);
    });
    console.log('');
  }

  process.exit(result.valid ? 0 : 1);
}

// 如果直接运行此脚本
if (require.main === module) {
  main();
}

module.exports = { RuleValidator };
