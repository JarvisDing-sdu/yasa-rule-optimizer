# Experiment Structure

This repository is organized around a paper-inspired pipeline for cross-language static-analysis rule generation and optimization.

## Core directories

- `apps/web/`: current web frontend
- `apps/client/`: desktop/client application workspace
- `yasa_engine/`: existing YASA engine, binaries, rules, and runtime dependencies
- `yasa_engine/yasa-api-agent/`: current backend API service
- `datasets/`: benchmark inputs, labels, and curated rule examples
- `prompts/`: prompt templates for each LLM stage
- `workflows/`: orchestration logic for each pipeline stage
- `schemas/`: JSON schemas and structural constraints for intermediate artifacts
- `outputs/`: generated descriptions, rules, evaluations, and iteration artifacts
- `docs/`: experiment plans and notes

## Recommended first experiment

Start with a single language and vulnerability type, for example Python SSRF.

Pipeline:
1. Prepare labeled vulnerability cases under `datasets/vuln_cases/`
2. Write expected findings under `datasets/expected_results/`
3. Store a few high-quality existing rules in `datasets/rule_examples/`
4. Author stage prompts in `prompts/`
5. Implement pipeline scripts in `workflows/`
6. Save generated artifacts in `outputs/`

## Notes

Keep YASA engine internals in `yasa_engine/` and put your LLM-driven optimization workflow in the top-level folders above. This keeps the engine base separate from the experimental pipeline.
