# -*- coding: utf-8 -*-
"""Rule generation APIs integrated into the ma_yisheng FastAPI server."""

import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()
ROOT = os.path.dirname(os.path.abspath(__file__))


class RuleGenerationRequest(BaseModel):
    vulnCase: Dict[str, Any]
    provider: str = "deepseek"
    model: Optional[str] = None
    save: bool = True


class RuleValidationRequest(BaseModel):
    rule: Dict[str, Any]


def p(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_json(text: str) -> Any:
    if not text:
        raise ValueError("LLM returned empty content")
    s = text.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        return json.loads(s[start : end + 1])
    raise ValueError("LLM response is not valid JSON")


def rule_id(rule: Dict[str, Any]) -> str:
    rid = str((rule.get("metadata") or {}).get("ruleId") or "").strip()
    return rid or f"generated_rule_{int(time.time())}"


def existing_rule_ids() -> set:
    ids = set()
    for d in [
        p("yasa_engine", "rules-mayisheng"),
        p("ma_yisheng", "rules"),
        p("generated_rules", "staging"),
        p("generated_rules", "candidate"),
        p("generated_rules", "production"),
    ]:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".json"):
                continue
            try:
                data = load_json(os.path.join(d, name))
                for item in data if isinstance(data, list) else [data]:
                    rid = ((item or {}).get("metadata") or {}).get("ruleId")
                    if rid:
                        ids.add(str(rid))
            except Exception:
                pass
    return ids


def validate_generated_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    if not isinstance(rule, dict):
        return {"valid": False, "errors": [{"type": "type", "message": "rule must be an object"}], "warnings": []}

    checker_ids = rule.get("checkerIds")
    if not isinstance(checker_ids, list) or not checker_ids or not all(isinstance(x, str) and x.strip() for x in checker_ids):
        errors.append({"type": "required", "field": "checkerIds", "message": "checkerIds must be a non-empty string array"})

    sources = rule.get("sources")
    if not isinstance(sources, dict) or not sources:
        errors.append({"type": "required", "field": "sources", "message": "sources must be a non-empty object"})
    else:
        allowed = {"TaintSource", "FuncCallReturnValueTaintSource", "FuncCallArgTaintSource"}
        for kind, entries in sources.items():
            if kind not in allowed:
                errors.append({"type": "schema", "field": f"sources.{kind}", "message": "unsupported source kind"})
                continue
            if not isinstance(entries, list):
                errors.append({"type": "schema", "field": f"sources.{kind}", "message": "entries must be an array"})
                continue
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    errors.append({"type": "schema", "field": f"sources.{kind}[{i}]", "message": "entry must be an object"})
                    continue
                for field in ("scopeFile", "scopeFunc"):
                    if field not in entry:
                        errors.append({"type": "required", "field": f"sources.{kind}[{i}].{field}", "message": f"{field} is required"})
                if kind == "TaintSource" and "path" not in entry:
                    errors.append({"type": "required", "field": f"sources.{kind}[{i}].path", "message": "path is required"})
                if kind == "FuncCallReturnValueTaintSource" and ("fsig" not in entry or not isinstance(entry.get("values"), list)):
                    errors.append({"type": "required", "field": f"sources.{kind}[{i}]", "message": "fsig and values[] are required"})
                if kind == "FuncCallArgTaintSource" and ("fsig" not in entry or not isinstance(entry.get("args"), list)):
                    errors.append({"type": "required", "field": f"sources.{kind}[{i}]", "message": "fsig and args[] are required"})

    sinks = rule.get("sinks")
    sink_entries = sinks.get("FuncCallTaintSink") if isinstance(sinks, dict) else None
    if not isinstance(sink_entries, list) or not sink_entries:
        errors.append({"type": "required", "field": "sinks.FuncCallTaintSink", "message": "FuncCallTaintSink must be a non-empty array"})
    else:
        for i, sink in enumerate(sink_entries):
            if not isinstance(sink, dict):
                errors.append({"type": "schema", "field": f"sinks.FuncCallTaintSink[{i}]", "message": "entry must be an object"})
                continue
            if not sink.get("fsig") and not sink.get("fregex"):
                errors.append({"type": "required", "field": f"sinks.FuncCallTaintSink[{i}]", "message": "either fsig or fregex is required"})
            if not isinstance(sink.get("args"), list):
                errors.append({"type": "required", "field": f"sinks.FuncCallTaintSink[{i}].args", "message": "args array is required"})
            if not sink.get("attribute"):
                errors.append({"type": "required", "field": f"sinks.FuncCallTaintSink[{i}].attribute", "message": "attribute is required"})
            if sink.get("fregex") and not sink.get("fsig"):
                warnings.append({"type": "semantic", "field": f"sinks.FuncCallTaintSink[{i}].fregex", "message": "prefer fsig when known"})

    rid = rule_id(rule)
    if rid in existing_rule_ids():
        warnings.append({"type": "semantic", "field": "metadata.ruleId", "message": f"ruleId already exists: {rid}"})
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def load_rule_examples(language: str) -> List[Dict[str, Any]]:
    examples = []
    d = p("datasets", "rule_examples")
    if os.path.isdir(d):
        for name in os.listdir(d):
            if name.endswith(".json") and name != "README.json":
                try:
                    data = load_json(os.path.join(d, name))
                    examples.extend(data if isinstance(data, list) else [data])
                except Exception:
                    pass
    if examples:
        return examples[:3]
    for candidate in [p("ma_yisheng", "rules", f"rule_config_{language}_full.json"), p("yasa_engine", "rules-mayisheng", f"rule_config_{language}_full.json")]:
        if os.path.exists(candidate):
            data = load_json(candidate)
            return (data if isinstance(data, list) else [data])[:3]
    return []


def call_rule_llm(system: str, user: str) -> str:
    """Call LLM using the project's shared llm module."""
    from llm import call_llm
    result = call_llm(system, user)
    if result is None:
        raise HTTPException(status_code=502, detail="LLM returned empty content")
    return result


@router.get("/api/rule-generation/status", summary="Rule generation capability status")
def rule_generation_status() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "ma_yisheng FastAPI + YASA rule generation",
        "cases_dir": p("datasets", "vuln_cases"),
        "staging_dir": p("generated_rules", "staging"),
        "candidate_dir": p("generated_rules", "candidate"),
        "existing_rule_ids": len(existing_rule_ids()),
    }


@router.get("/api/rule-cases", summary="List vulnerability cases")
def list_rule_cases() -> Dict[str, Any]:
    cases = []
    d = p("datasets", "vuln_cases")
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.endswith(".json"):
                try:
                    data = load_json(os.path.join(d, name))
                    cases.append({"file": name, "case_id": data.get("case_id"), "language": data.get("language"), "vulnerability_type": data.get("vulnerability_type"), "notes": data.get("notes", "")})
                except Exception as e:
                    cases.append({"file": name, "error": str(e)})
    return {"cases": cases, "count": len(cases)}


@router.post("/api/validate-rule", summary="Validate a generated YASA rule")
def validate_rule_endpoint(req: RuleValidationRequest) -> Dict[str, Any]:
    return {"success": True, "validation": validate_generated_rule(req.rule)}


@router.post("/api/generate-rule-from-case", summary="Generate and validate a YASA rule from a vulnerability case")
def generate_rule_from_case_endpoint(req: RuleGenerationRequest, request: Request) -> Dict[str, Any]:
    # Rate limit: max 10/min per IP, using shared limiter from api.py
    client_ip = request.client.host if request.client else "unknown"
    from chat import _check_rate_limit as _api_rate_limit
    if not _api_rate_limit(f"rule-gen:{client_ip}", max_req=10, window=60):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
    vuln = req.vulnCase
    if not vuln or not vuln.get("case_id"):
        raise HTTPException(status_code=400, detail="vulnCase.case_id is required")
    try:
        stage1_prompt = open(p("prompts", "stage1_vulnerability_description.md"), "r", encoding="utf-8").read()
        stage2_prompt = open(p("prompts", "stage2_rule_generation.md"), "r", encoding="utf-8").read()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Prompt file missing: {e}")
    stage1_user = "\n".join([
        f"Case ID: {vuln.get('case_id')}", f"Language: {vuln.get('language')}", f"Vulnerability Type: {vuln.get('vulnerability_type')}", "",
        "=== Source Code Before Fix ===", vuln.get("source_code_before") or "(empty)", "",
        "=== Source Code After Fix ===", vuln.get("source_code_after") or "(empty)", "",
        "=== Source Function Hints ===", json.dumps(vuln.get("source_function_hints") or [], ensure_ascii=False, indent=2), "",
        "=== Sink Function Hints ===", json.dumps(vuln.get("sink_function_hints") or [], ensure_ascii=False, indent=2),
    ])
    description = extract_json(call_rule_llm(system=stage1_prompt, user=stage1_user))
    examples = load_rule_examples(str(vuln.get("language") or "python"))
    stage2_user = "\n".join([
        "=== Structured Vulnerability Description ===", json.dumps(description, ensure_ascii=False, indent=2), "",
        "=== Reference Rule Examples ===", json.dumps(examples, ensure_ascii=False, indent=2), "",
        "Generate one YASA rule JSON object. Include metadata.ruleId, caseId, language, vulnerabilityType, generatedAt, generatedBy, validationStatus.",
    ])
    rule = extract_json(call_rule_llm(system=stage2_prompt, user=stage2_user))
    meta = rule.setdefault("metadata", {})
    meta.setdefault("ruleId", f"{vuln.get('case_id')}_generated_{int(time.time())}")
    meta.setdefault("caseId", vuln.get("case_id"))
    meta.setdefault("language", vuln.get("language"))
    meta.setdefault("vulnerabilityType", vuln.get("vulnerability_type"))
    meta.setdefault("generatedAt", datetime.now().isoformat())
    meta.setdefault("generatedBy", "ma_yisheng-fastapi-rule-generation")
    validation = validate_generated_rule(rule)
    meta["validationStatus"] = "valid" if validation["valid"] else "invalid"
    saved_path = None
    if req.save and validation["valid"]:
        d = p("generated_rules", "staging")
        os.makedirs(d, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", rule_id(rule))
        saved_path = os.path.join(d, f"{safe_name}.json")
        with open(saved_path, "w", encoding="utf-8") as f:
            json.dump(rule, f, ensure_ascii=False, indent=2)
    return {"success": True, "description": description, "rule": rule, "validation": validation, "savedPath": saved_path}
