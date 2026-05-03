#!/bin/bash

# 安装规则生成系统所需的依赖

echo "=== Installing dependencies for rule generation system ==="
echo ""

cd "$(dirname "$0")/../yasa_engine/yasa-api-agent"

echo "Current directory: $(pwd)"
echo ""

echo "Installing ajv and ajv-formats..."
npm install ajv ajv-formats --save

echo ""
echo "=== Installation complete ==="
echo ""
echo "Installed packages:"
npm list ajv ajv-formats

echo ""
echo "Next steps:"
echo "1. Start the API server: cd yasa_engine/yasa-api-agent && node app.js"
echo "2. Test rule generation: cd yasa_engine/scripts && node test_generate_rule.js python_sqli_001 <your-api-key>"
