# Ma Yisheng Rule Configs

[Language: [中文](README.md) | **English**]

This directory contains rule files bundled with the Ma Yisheng client and used as scan-time YASA rule configs.

## Scan Logic

- **Languages**: Python, Java, Go, JS, PHP, C.
- **Modes**:
  - `minimal`: fewer rules and faster scans.
  - `full`: broader coverage and slower scans.
- **Config naming**: `rule_config_{language}_{minimal|full}.json`, for example:
  - `rule_config_python_minimal.json`
  - `rule_config_python_full.json`
  - `rule_config_php_minimal.json`
  - `rule_config_php_full.json`
  - `rule_config_c_minimal.json`
  - `rule_config_c_full.json`

The backend `app.js` selects these files from `ruleMode: "minimal" | "full"` and passes them as `--ruleConfigFile`.

## Engine Support

The bundled engine is wired for Python, Java, Go, JS, PHP, and C. PHP uses the official `PhpAnalyzer`; C uses `CAnalyzer`. Both use built-in parser wiring and do not require an extra `uastSDKPath`.
