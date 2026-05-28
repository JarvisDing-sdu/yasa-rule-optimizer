# 马医生规则配置

[语言：**中文** | [English](README.en.md)]

本目录为「马医生」客户端自带的规则文件，已克隆到 yasa-bundle 作为**扫描用规则配置**。

## 扫描逻辑（马医生客户端）

- **语言**：Python / Java / Go / JS / PHP / C
- **模式**：
  - **minimal（精简）**：规则少、扫描快
  - **full（全面）**：规则多、覆盖全、扫描慢
- **配置文件**：按 `rule_config_{语言}_{minimal|full}.json` 选择，例如：
  - `rule_config_python_minimal.json`
  - `rule_config_python_full.json`
  - 同理 go / java / js / php / c

后端 `app.js` 已接好：请求里传 `ruleMode: 'minimal' | 'full'`，会使用本目录下对应文件作为 `--ruleConfigFile`。未找到时回退到仓库根目录的 `rules.json`。

## 当前 yasa-bundle 支持的引擎语言

- 当前 bundle 已接入 Python / Java / Go / JS / PHP / C；PHP 通过官方 `PhpAnalyzer` 运行，C 通过 `CAnalyzer` 与内置 parser 运行，这两者都不需要额外 `uastSDKPath`。
