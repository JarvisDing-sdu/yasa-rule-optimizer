# Ma Yisheng Code Security Scanner

[Language: [中文](README.md) | **English**]

Ma Yisheng is a code security scanning platform built on the YASA static analysis engine and LLM-assisted workflows. It supports vulnerability scanning, CVE-driven rule generation, personal rule libraries, report management, and an AI Agent interface.

## Features

- **Vulnerability scanning**: dual-engine scanning with YASA taint analysis and Semgrep pattern matching.
- **Language support**: Python, Java, Go, JavaScript, PHP, and C.
- **C vulnerability detection**: CAnalyzer-based YASA rules for taint flows such as unsafe input, buffer overflow patterns, and command injection sinks.
- **AI Agent workflow**: search advisories, generate rules, scan projects, and summarize reports through chat.
- **CVE-driven rule generation**: search GitHub Advisory data and generate YASA rules through an LLM pipeline.
- **Personal rule library**: clone official rules, create custom rules, and enable or disable individual rules.
- **Reports**: JSON, SARIF, TXT, HTML export, favorites, and AI-assisted triage.

## Desktop Client (macOS / Linux)

1. Download the installer from [Releases](https://github.com/JarvisDing-sdu/yasa-rule-optimizer/releases): macOS `.dmg` or Linux `.AppImage`.
2. **macOS**: Open the `.dmg`, drag the app into Applications, and launch it.
   **Linux**: Mark it executable and run — no installation needed:
   ```bash
   chmod +x "Ma Yisheng-*.AppImage"
   ./"Ma Yisheng-*.AppImage"
   ```
3. Enter your LLM API Key, register an account, and start scanning.

> The YASA engine is bundled inside the installer — no separate download or path configuration required. The backend starts automatically when the app opens.
>
> All data (accounts, reports, rule libraries) is stored locally — Linux: `~/.config/Ma Yisheng/runtime/`, macOS: `~/Library/Application Support/Ma Yisheng/runtime/`. Desktop data is independent from the web version.

## Self-hosted / Development

```bash
cd ma_yisheng
cp .env.example .env
# Fill LLM_API_KEY, SMTP, YASA_BUNDLE_PATH, JWT_SECRET, and other settings.
python3 -m venv .venv
source .venv/bin/activate
pip install -r server_requirements.txt
python3 main.py --host 0.0.0.0 --port 8000
```

Open:

- Scanner: `http://localhost:8000/`
- Rule workshop: `http://localhost:8000/rule-workshop`
- API docs: `http://localhost:8000/docs`

## C Language Extension

This repository includes the C extension migrated into the latest project layout:

- `.c` and `.h` language detection in the Python scanner.
- C entries in YASA analyzer/checker mapping.
- PHP entries in YASA analyzer/checker mapping, using official `PhpAnalyzer`.
- C options in the web UI and rule workshop.
- `rule_config_c_minimal.json` and `rule_config_c_full.json` rule packs.
- A C-capable `yasa-engine-linux-x64` binary.

## Project Layout

```text
ma_yisheng/                  FastAPI backend, scanner, auth, reports, Agent tools
apps/web/public/             lightweight web UI for the YASA API agent
frontend_src/                React frontend source
rules/                       official rule configs
yasa_engine/                 bundled YASA engine, SDKs, and rules-mayisheng configs
generated_rules/             LLM-generated rules lifecycle directories
workflows/                   notes and automation scripts for rule generation
```

## Common Flow

1. Log in.
2. Choose a local path or upload a zip.
3. Select language, engine, and rule sets.
4. Start the scan.
5. Review findings, export reports, or ask AI for triage and remediation advice.
