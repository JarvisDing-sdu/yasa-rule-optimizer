# 马医生规则配置（克隆自 D:\apps\马医生\rules）

本目录为「马医生」客户端自带的规则文件，已克隆到 yasa-bundle 作为**扫描用规则配置**。

## 扫描逻辑（马医生客户端）

- **语言**：Python / Java / Go / JS
- **模式**：
  - **minimal（精简）**：规则少、扫描快
  - **full（全面）**：规则多、覆盖全、扫描慢
- **配置文件**：按 `rule_config_{语言}_{minimal|full}.json` 选择，例如：
  - `rule_config_python_minimal.json`
  - `rule_config_python_full.json`
  - 同理 go / java / js

后端 `app.js` 已接好：请求里传 `ruleMode: 'minimal' | 'full'`，会使用本目录下对应文件作为 `--ruleConfigFile`。未找到时回退到仓库根目录的 `rules.json`。

## 当前 yasa-bundle 支持的引擎语言

- 仅 **Python、Go** 已配置 UAST 与引擎；Java/JS 的规则文件存在，但若引擎未装对应 analyzer，扫描会报错。需要时再扩展 `LANG_CONFIG` 与 SDK。
