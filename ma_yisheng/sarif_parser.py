# -*- coding: utf-8 -*-
"""SARIF 解析模块：解析 YASA 生成的 report.sarif，去重并返回结构化漏洞列表"""

import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# sinkAttribute -> (中文名, 严重程度)
SINK_SEVERITY_MAP = {
    # Python
    "PythonPathTraversal": ("路径遍历", "中危"),
    "PythonCommandInjection": ("命令注入", "高危"),
    "PythonCommandExec": ("命令执行", "高危"),
    "PythonCodeExec": ("代码执行", "高危"),
    "PythonSqlInjection": ("SQL 注入", "高危"),
    "PythonNoSqlInjection": ("NoSQL 注入", "高危"),
    "PythonSSRF": ("SSRF", "高危"),
    "PythonXSS": ("XSS", "中危"),
    "PythonDeserialization": ("反序列化", "高危"),
    "PythonDeserializationGadget": ("反序列化利用链", "中危"),
    "PythonTemplateInjection": ("模板注入", "高危"),
    "PythonLogInjection": ("日志注入", "中危"),
    "PythonInfoLeak": ("信息泄露", "中危"),
    "PythonLdapInjection": ("LDAP 注入", "高危"),
    "PythonResponseWrite": ("响应写入", "中危"),
    "Chromium": ("Chromium", "中危"),
    # Java
    "JavaSqlInjection": ("SQL 注入", "高危"),
    "JavaCodeExec": ("代码执行", "高危"),
    "JavaCommandExec": ("命令执行", "高危"),
    "JavaCommandInjection": ("命令注入", "高危"),
    "JavaDeserialization": ("反序列化", "高危"),
    "JavaDeserializationGadget": ("反序列化利用链", "中危"),
    "JavaNoSqlInjection": ("NoSQL 注入", "高危"),
    "JavaSSRF": ("SSRF", "高危"),
    "JavaXSS": ("XSS", "中危"),
    "JavaPathTraversal": ("路径遍历", "中危"),
    "JavaTemplateInjection": ("模板注入", "高危"),
    "JavaLdapInjection": ("LDAP 注入", "高危"),
    "JavaLogInjection": ("日志注入", "中危"),
    "JavaInfoLeak": ("信息泄露", "中危"),
    "JavaJNDI": ("JNDI 注入", "高危"),
    "JavaXPath": ("XPath 注入", "中危"),
    "JavaXXE": ("XXE", "高危"),
    "JavaResponseWrite": ("响应写入", "中危"),
    # Go
    "GoCommandExec": ("命令执行", "高危"),
    "GoCommandInjection": ("命令注入", "高危"),
    "GoDeserializationGadget": ("反序列化利用链", "中危"),
    "GoInfoLeak": ("信息泄露", "中危"),
    "GoLogInjection": ("日志注入", "中危"),
    "GoNoSqlInjection": ("NoSQL 注入", "高危"),
    "GoPathTraversal": ("路径遍历", "中危"),
    "GoResponseWrite": ("响应写入", "中危"),
    "GoSSRF": ("SSRF", "高危"),
    "GoSqlInjection": ("SQL 注入", "高危"),
    "GoTemplateInjection": ("模板注入", "高危"),
    "GoXSS": ("XSS", "中危"),
    # JavaScript / Node.js
    "NodejsCommandInjection": ("命令注入", "高危"),
    "NodejsDeserializationGadget": ("反序列化利用链", "中危"),
    "NodejsExec": ("代码执行", "高危"),
    "NodejsFileOperator": ("文件操作", "中危"),
    "NodejsInfoLeak": ("信息泄露", "中危"),
    "NodejsLogInjection": ("日志注入", "中危"),
    "NodejsModuleDeserialize": ("反序列化", "高危"),
    "NodejsNoSqlInjection": ("NoSQL 注入", "高危"),
    "NodejsPathTraversal": ("路径遍历", "中危"),
    "NodejsResponseWrite": ("响应写入", "中危"),
    "NodejsSSRF": ("SSRF", "高危"),
    "NodejsSqlInjection": ("SQL 注入", "高危"),
    "NodejsTemplateInjection": ("模板注入", "高危"),
    "NodejsVm2Run": ("沙箱逃逸", "高危"),
    "NodejsXSS": ("XSS", "中危"),
    # C
    "CBufferOverflow": ("缓冲区溢出", "高危"),
    "CFormatOrBufferOverflow": ("格式化/缓冲区溢出", "高危"),
    "CCommandInjection": ("命令注入", "高危"),
    "CFormatString": ("格式化字符串漏洞", "高危"),
    "CPathTraversal": ("路径遍历", "中危"),
    # PHP
    "PhpSqlInjection": ("SQL 注入", "高危"),
    "PhpCommandInjection": ("命令注入", "高危"),
    "PhpCodeInjection": ("代码注入", "高危"),
    "PhpFileInclusion": ("文件包含", "高危"),
    "PhpPathTraversal": ("路径遍历", "中危"),
    "PhpXSS": ("XSS", "中危"),
    "PhpSSRF": ("SSRF", "高危"),
    "PhpDeserialization": ("反序列化", "高危"),
    # Generic / legacy
    "XSS": ("XSS", "中危"),
    "PathTraversal": ("路径遍历", "中危"),
}

# 数字越小越优先展示（主流工具：先高危）
SEVERITY_RANK = {"高危": 0, "中危": 1, "低危": 2}


def _extract_file_path(uri: str) -> str:
    """从 SARIF uri 提取文件名，如 /mnt/d/.../model_usage.py 或 file:///model_usage.py -> model_usage.py"""
    if not uri:
        return ""
    path = uri
    if uri.startswith("file:///"):
        path = uri[9:]
    elif uri.startswith("file://"):
        path = uri[7:]
    # 取最后一段作为文件名（兼容 /mnt/d/.../model_usage.py）
    return path.split("/")[-1] if "/" in path else path


def _normalize_sink_attribute(value: Any) -> Tuple[str, str]:
    """YASA may emit sinkAttribute as a string or an array; return display + primary key."""
    if isinstance(value, list):
        items = [str(v) for v in value if v]
        if not items:
            return "", ""
        return ", ".join(items), items[0]
    text = str(value or "")
    return text, text


def _dedupe_key(f: Dict) -> Tuple:
    """去重键：同一文件、同一行、同一漏洞类型视为重复"""
    loc = f.get("location") or {}
    if isinstance(loc, dict) and loc.get("file") is not None:
        return (str(loc.get("file", "")), int(loc.get("line") or 0), f.get("sink_attribute", ""))
    return (str(f.get("file", "")), int(f.get("line") or 0), f.get("sink_attribute", ""))


def finding_fingerprint(f: Dict[str, Any]) -> str:
    """稳定指纹：用于 API 定位单条 finding（与去重逻辑一致）"""
    key = f"{f.get('file', '')}|{f.get('line', 0)}|{f.get('sink_attribute', '')}|{f.get('sink_rule', '')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def sort_findings_by_severity(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按严重级别（高危→中危→低危），再按文件、行、规则类型排序，便于用户优先处理高风险。"""

    def sort_key(f: Dict[str, Any]) -> Tuple:
        sev = f.get("severity", "中危")
        rank = SEVERITY_RANK.get(sev, 1)
        return (
            rank,
            f.get("file", "") or "",
            int(f.get("line") or 0),
            f.get("sink_attribute", "") or "",
        )

    return sorted(findings, key=sort_key)


def normalize_findings_list(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """排序并补全 fingerprint（不修改调用方传入的原始 dict，返回新列表）"""
    if not findings:
        return []
    copies = [dict(f) for f in findings]
    ordered = sort_findings_by_severity(copies)
    for f in ordered:
        f["fingerprint"] = finding_fingerprint(f)
    return ordered


def parse_sarif(sarif_path: str) -> List[Dict[str, Any]]:
    """
    解析 SARIF 文件，返回去重后的结构化漏洞列表。
    每个元素: {
        "file": str,
        "line": int,
        "column": int,
        "sink_rule": str,
        "sink_attribute": str,
        "vuln_name": str,
        "severity": str,
        "message": str,
        "snippet": str,
        "code_flow": list,  # 污点传播路径摘要
    }
    """
    p = Path(sarif_path)
    if not p.exists():
        return []

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    runs = data.get("runs", [])
    if not runs:
        return []

    findings = []
    seen = set()

    for run in runs:
        results = run.get("results", [])
        for r in results:
            sink_info = r.get("sinkInfo", {})
            sink_rule = sink_info.get("sinkRule", "")
            sink_attr, primary_sink_attr = _normalize_sink_attribute(sink_info.get("sinkAttribute", ""))
            vuln_name, severity = SINK_SEVERITY_MAP.get(
                primary_sink_attr, (sink_attr or "未知", "中危")
            )

            locs = r.get("locations", [])
            if not locs:
                continue
            ploc = locs[0].get("physicalLocation", {})
            artifact = ploc.get("artifactLocation", {})
            region = ploc.get("region", {})
            uri = artifact.get("uri", "")
            file_path = _extract_file_path(uri)
            line = region.get("startLine", 0)
            col = region.get("startColumn", 0)
            snippet = region.get("snippet", {}).get("text", "")

            # 从 codeFlows 提取污点路径摘要
            code_flow = []
            for cf in r.get("codeFlows", []):
                for tf in cf.get("threadFlows", []):
                    for loc in tf.get("locations", [])[:5]:  # 最多 5 步
                        ll = loc.get("location", {})
                        ppl = ll.get("physicalLocation", {})
                        rr = ppl.get("region", {})
                        msg = ll.get("message", {}).get("text", "")
                        snip = rr.get("snippet", {}).get("text", "")
                        code_flow.append({
                            "step": msg,
                            "line": rr.get("startLine"),
                            "snippet": snip[:80] if snip else "",
                        })

            finding = {
                "file": file_path,
                "line": line,
                "column": col,
                "sink_rule": sink_rule,
                "sink_attribute": sink_attr,
                "vuln_name": vuln_name,
                "severity": severity,
                "message": r.get("message", {}).get("text", ""),
                "snippet": snippet,
                "code_flow": code_flow,
            }

            key = _dedupe_key(finding)
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)

    return findings


def get_summary_from_findings(findings: List[Dict]) -> Dict[str, Any]:
    """从结构化 findings 生成摘要，供 list_reports 等使用"""
    result = {
        "findings_count": len(findings),
        "vuln_types": [],
        "severity": "无",
        "files_analyzed": len(set(f.get("file", "") for f in findings)),
    }
    if not findings:
        return result

    vuln_names = set()
    severities = set()
    for f in findings:
        vuln_names.add(f.get("vuln_name", ""))
        severities.add(f.get("severity", "中危"))
    result["vuln_types"] = list(vuln_names)
    result["severity"] = "高危" if "高危" in severities else "中危"
    return result


def parse_semgrep_sarif(sarif_path: str) -> List[Dict[str, Any]]:
    """
    解析 Semgrep 输出的标准 SARIF 文件，返回与 parse_sarif() 相同结构的列表。
    Semgrep SARIF 使用标准字段，没有 sinkInfo / codeFlows。
    """
    p = Path(sarif_path)
    if not p.exists():
        return []

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    runs = data.get("runs", [])
    if not runs:
        return []

    # 构建 ruleId -> rule metadata 映射
    rule_meta: Dict[str, Dict] = {}
    for run in runs:
        for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
            rid = rule.get("id", "")
            props = rule.get("properties", {})
            rule_meta[rid] = {
                "name": rule.get("name") or rid,
                "severity": _semgrep_severity(
                    rule.get("defaultConfiguration", {}).get("level", ""),
                    props.get("impact", ""),
                    props.get("severity", ""),
                ),
                "message": rule.get("shortDescription", {}).get("text", "")
                           or rule.get("fullDescription", {}).get("text", ""),
            }

    findings = []
    seen: set = set()

    for run in runs:
        for r in run.get("results", []):
            rule_id = r.get("ruleId", "")
            meta = rule_meta.get(rule_id, {})

            locs = r.get("locations", [])
            if not locs:
                continue
            ploc = locs[0].get("physicalLocation", {})
            artifact = ploc.get("artifactLocation", {})
            region = ploc.get("region", {})

            uri = artifact.get("uri", "")
            file_path = _extract_file_path(uri)
            line = region.get("startLine", 0)
            col = region.get("startColumn", 0)
            snippet = region.get("snippet", {}).get("text", "")

            message = r.get("message", {}).get("text", "") or meta.get("message", "")
            severity = meta.get("severity", "中危")
            vuln_name = meta.get("name") or rule_id

            finding = {
                "file": file_path,
                "line": line,
                "column": col,
                "sink_rule": rule_id,
                "sink_attribute": rule_id,
                "vuln_name": vuln_name,
                "severity": severity,
                "message": message,
                "snippet": snippet,
                "code_flow": [],
                "engine": "semgrep",
            }

            key = _dedupe_key(finding)
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)

    return findings


def _semgrep_severity(level: str, impact: str, severity_prop: str) -> str:
    """将 Semgrep 的 level/impact/severity 字段映射到高危/中危/低危"""
    combined = f"{level} {impact} {severity_prop}".lower()
    if any(w in combined for w in ("error", "high", "critical")):
        return "高危"
    if any(w in combined for w in ("warning", "medium")):
        return "中危"
    return "低危"


def format_findings_text(findings: List[Dict], scan_path: str = "") -> str:
    """将结构化 findings 格式化为易读的文本"""
    if not findings:
        return "未发现漏洞。"

    lines = [
        "=" * 60,
        "【结构化漏洞报告】",
        f"共 {len(findings)} 条（已去重）",
        "=" * 60,
    ]

    by_severity = {"高危": [], "中危": [], "低危": []}
    for f in findings:
        sev = f.get("severity", "中危")
        by_severity.get(sev, by_severity["中危"]).append(f)

    VERDICT_MAP = {"true_positive": "✅ 真漏洞", "false_positive": "❌ 误报", "needs_review": "⚠️ 需人工确认"}

    for sev in ["高危", "中危", "低危"]:
        items = by_severity[sev]
        if not items:
            continue
        lines.append(f"\n## {sev} ({len(items)} 条)")
        lines.append("-" * 40)
        for i, f in enumerate(items, 1):
            verdict = f.get("llm_verdict")
            verdict_str = f" {VERDICT_MAP.get(verdict, '')}" if verdict else ""
            lines.append(f"\n{i}. 【{f.get('vuln_name', '未知')}】{verdict_str} {f.get('file', '')}:{f.get('line', 0)}")
            if f.get("llm_reason"):
                lines.append(f"   马医生: {f['llm_reason']}")
            if f.get("snippet"):
                lines.append(f"   代码: {f['snippet'][:60].strip()}...")
            if f.get("code_flow"):
                flow_sum = " -> ".join(
                    f"L{step.get('line')}" for step in f["code_flow"][:4]
                )
                lines.append(f"   污点路径: {flow_sum}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
