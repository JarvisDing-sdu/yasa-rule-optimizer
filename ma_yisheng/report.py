# -*- coding: utf-8 -*-
"""报告生成模块"""

import html
import json
import re
import shutil
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

from sarif_parser import (
    parse_sarif,
    get_summary_from_findings,
    format_findings_text,
    normalize_findings_list,
)

FAVORITE_MARKER = ".favorite"
RETENTION_DAYS = 1

# 漏洞类型 -> 中文/严重程度（raw_output 解析用，SARIF 优先）
VULN_ATTR_MAP = {
    "PythonSqlInjection": ("SQL 注入", "高危"),
    "JavaSqlInjection": ("SQL 注入", "高危"),
    "PythonCommandExec": ("命令执行", "高危"),
    "PythonCodeExec": ("代码执行", "高危"),
    "PathTraversal": ("路径遍历", "中危"),
    "XSS": ("XSS", "中危"),
}


def _parse_report_summary(raw_output: str, findings: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """解析摘要：优先用 SARIF findings，否则用 raw_output"""
    if findings is not None:
        return get_summary_from_findings(findings)
    result = {"findings_count": 0, "vuln_types": [], "severity": "无", "files_analyzed": 0}
    if not raw_output:
        return result
    m = re.search(r"Total-findings\s*:\s*(\d+)", raw_output)
    if m:
        result["findings_count"] = int(m.group(1))
    m = re.search(r"Files analyzed\s*:\s*(\d+)", raw_output)
    if m:
        result["files_analyzed"] = int(m.group(1))
    high_risk = ["PythonSqlInjection", "JavaSqlInjection", "PythonCommandExec", "PythonCodeExec"]
    for attr, (name, sev) in VULN_ATTR_MAP.items():
        if attr in raw_output:
            if name not in result["vuln_types"]:
                result["vuln_types"].append(name)
    if result["vuln_types"]:
        result["severity"] = "高危" if any(a in raw_output for a in high_risk) else "中危"
    elif result["findings_count"] > 0:
        result["severity"] = "中危"
    return result


def mark_as_favorite(report_dir: str) -> bool:
    """在报告目录下创建收藏标记，收藏的报告永久保留。返回是否成功。"""
    try:
        (Path(report_dir) / FAVORITE_MARKER).touch()
        return True
    except Exception:
        return False


def is_favorite(report_dir: str) -> bool:
    """检查报告是否已收藏。"""
    return (Path(report_dir) / FAVORITE_MARKER).exists()


def unmark_favorite(report_dir: str) -> bool:
    """取消收藏。返回是否成功。"""
    try:
        marker = Path(report_dir) / FAVORITE_MARKER
        if marker.exists():
            marker.unlink()
        return True
    except Exception:
        return False


def delete_report(report_dir: str) -> bool:
    """删除报告目录。仅允许删除未收藏的报告。返回是否成功。"""
    rd = Path(report_dir)
    if not rd.is_dir():
        return False
    if (rd / FAVORITE_MARKER).exists():
        return False
    try:
        shutil.rmtree(rd)
        return True
    except Exception:
        return False


def save_report(
    report_dir: str,
    scan_path: str,
    lang: str,
    yasa_stdout: str,
) -> Tuple[str, str]:
    """
    保存报告到 report_dir 下的 .json 和 .txt
    解析 SARIF 并写入结构化 findings，同时更新 summary.txt 为结构化+原始格式
    返回 (json_path, txt_path)
    """
    rd = Path(report_dir)
    rd.mkdir(parents=True, exist_ok=True)

    txt_path = rd / "summary.txt"
    json_path = rd / "report.json"
    sarif_path = rd / "report.sarif"

    # 解析 SARIF 获取结构化 findings
    findings = []
    if sarif_path.exists():
        findings = normalize_findings_list(parse_sarif(str(sarif_path)))
    # TXT: 结构化报告 + 原始 YASA 输出
    txt_parts = []
    if findings:
        txt_parts.append(format_findings_text(findings, scan_path))
        txt_parts.append("\n\n--- 原始 YASA 输出 ---\n")
    txt_parts.append(yasa_stdout)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("".join(txt_parts))

    # JSON: 结构化摘要 + findings
    project_name = Path(scan_path).resolve().name or "unknown"
    summary = {
        "project": project_name,
        "scan_path": str(scan_path),
        "language": lang,
        "raw_output": yasa_stdout,
        "findings": findings,
        "findings_count": len(findings),
    }
    diag_path = rd / "yasa-diagnostics-log.txt"
    if diag_path.exists():
        try:
            lines = []
            with open(diag_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        lines.append(json.loads(line))
            summary["diagnostics"] = lines
        except Exception:
            pass

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return str(json_path), str(txt_path)


def list_reports(limit: int = 20, project_filter: str = "", user_id: int = None) -> List[dict]:
    """
    列出最近的扫描报告。
    limit: 最多返回数量
    project_filter: 按项目名过滤，空则不过滤
    user_id: 只返回该用户的报告，None 则返回所有（管理员用）
    返回 [{"path": str, "project": str, "mtime": float, "favorite": bool}, ...]
    """
    from config import get_reports_dir

    reports_dir = get_reports_dir()
    if not reports_dir.exists():
        return []

    # 如果指定了 user_id，只扫描该用户的子目录
    if user_id is not None:
        user_dir = reports_dir / str(user_id)
        if not user_dir.exists():
            return []
        scan_roots = [user_dir]
    else:
        scan_roots = [reports_dir]

    items = []
    for root in scan_roots:
        for report_dir in root.rglob("*"):
            if not report_dir.is_dir():
                continue
            if not (
                (report_dir / "report.json").exists()
                or (report_dir / "report.sarif").exists()
                or (report_dir / "summary.txt").exists()
            ):
                continue
            proj_name = report_dir.parent.name
            if project_filter and project_filter.lower() not in proj_name.lower():
                continue
            try:
                mtime = report_dir.stat().st_mtime
                fav = (report_dir / FAVORITE_MARKER).exists()
                json_path = report_dir / "report.json"
                scan_path = ""
                lang = ""
                raw_output = ""
                findings = None
                if json_path.exists():
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            scan_path = data.get("scan_path", "")
                            lang = data.get("language", "")
                            findings = data.get("findings")
                            if findings is None:
                                raw_output = data.get("raw_output", "")
                    except Exception:
                        pass
                summary = _parse_report_summary(raw_output, findings if findings is not None else None)
                items.append({
                    "path": str(report_dir),
                    "project": proj_name,
                    "report_name": report_dir.name,
                    "mtime": mtime,
                    "favorite": fav,
                    "scan_path": scan_path,
                    "language": lang,
                    "findings_count": summary.get("findings_count", 0),
                    "vuln_types": summary.get("vuln_types", []),
                    "severity": summary.get("severity", "无"),
                    "files_analyzed": summary.get("files_analyzed", 0),
                })
            except Exception:
                pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items[:limit]


def get_report_content(report_path: str, max_chars: int = 8000) -> Optional[str]:
    """
    获取指定报告的内容摘要。
    report_path: 报告目录路径（list_reports 返回的 path）
    返回 summary.txt 内容（含结构化+原始），失败返回 None
    """
    rd = Path(report_path)
    if not rd.is_dir():
        return None
    txt_path = rd / "summary.txt"
    if txt_path.exists():
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n...（内容已截断）"
            return content
        except Exception:
            pass
    # 旧报告可能无 summary.txt 或格式不同，尝试从 json+sarif 生成
    findings = get_structured_findings(report_path)
    json_path = rd / "report.json"
    raw = ""
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw = json.load(f).get("raw_output", "")
        except Exception:
            pass
    if findings:
        return format_findings_text(findings) + "\n\n--- 原始输出 ---\n\n" + raw[:max_chars]
    return raw[:max_chars] if raw else None


def update_report_findings(report_path: str, findings: List[Dict]) -> bool:
    """更新报告中的 findings（如 LLM 研判后的结果），同时刷新 summary.txt。返回是否成功。"""
    rd = Path(report_path)
    json_path = rd / "report.json"
    txt_path = rd / "summary.txt"
    if not json_path.exists():
        return False
    try:
        findings = normalize_findings_list(findings)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["findings"] = findings
        data["findings_count"] = len(findings)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 刷新 summary.txt
        raw = data.get("raw_output", "")
        new_txt = format_findings_text(findings) + "\n\n--- 原始 YASA 输出 ---\n\n" + raw
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(new_txt)
        return True
    except Exception:
        return False


def get_structured_findings(report_path: str) -> List[Dict]:
    """从报告目录获取结构化 findings，优先从 report.json，否则解析 SARIF。统一按严重级别排序并带 fingerprint。"""
    rd = Path(report_path)
    json_path = rd / "report.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                findings = data.get("findings")
                if findings is not None:
                    return normalize_findings_list(findings)
        except Exception:
            pass
    sarif_path = rd / "report.sarif"
    if sarif_path.exists():
        return normalize_findings_list(parse_sarif(str(sarif_path)))
    return []


def export_report_html(report_path: str, output_path: str) -> bool:
    """将报告导出为 HTML 文件，结构化展示漏洞。返回是否成功。"""
    rd = Path(report_path)
    json_path = rd / "report.json"
    title = rd.name
    scan_path = ""
    lang = ""
    findings = get_structured_findings(report_path)

    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                title = data.get("project", title)
                scan_path = data.get("scan_path", "")
                lang = data.get("language", "")
        except Exception:
            pass

    escaped_title = html.escape(title)
    escaped_scan = html.escape(scan_path)

    # 结构化漏洞表格
    findings_html = ""
    if findings:
        by_severity = {"高危": [], "中危": [], "低危": []}
        for f in findings:
            sev = f.get("severity", "中危")
            by_severity.get(sev, by_severity["中危"]).append(f)
        for sev, items in by_severity.items():
            if not items:
                continue
            sev_class = "high" if sev == "高危" else "medium" if sev == "中危" else "low"
            verdict_display = {"true_positive": "✅ 真漏洞", "false_positive": "❌ 误报", "needs_review": "⚠️ 需人工确认"}
            findings_html += f'<h3 class="sev-{sev_class}">{sev} ({len(items)} 条)</h3><table class="findings-table">'
            findings_html += "<tr><th>#</th><th>类型</th><th>研判</th><th>文件:行</th><th>代码</th></tr>"
            for i, f in enumerate(items, 1):
                file_line = f"{html.escape(f.get('file', ''))}:{f.get('line', 0)}"
                snippet = html.escape((f.get("snippet") or "")[:80])
                vuln_name = html.escape(f.get("vuln_name", ""))
                verdict = verdict_display.get(f.get("llm_verdict"), "")
                findings_html += f"<tr><td>{i}</td><td>{vuln_name}</td><td>{verdict}</td><td>{file_line}</td><td><code>{snippet}</code></td></tr>"
            findings_html += "</table>"
    else:
        findings_html = "<p>无结构化数据，请查看原始输出。</p>"

    # 原始输出
    raw_content = get_report_content(report_path, max_chars=100000)
    escaped_raw = html.escape(raw_content or "")

    html_body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>YASA 扫描报告 - {escaped_title}</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; margin: 24px; background: #f8f9fa; }}
h1 {{ color: #0D9488; }}
h3 {{ margin-top: 24px; }}
h3.sev-high {{ color: #dc2626; }}
h3.sev-medium {{ color: #ea580c; }}
h3.sev-low {{ color: #ca8a04; }}
.meta {{ color: #6c757d; margin-bottom: 20px; }}
.findings-table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; }}
.findings-table th, .findings-table td {{ border: 1px solid #e5e7eb; padding: 8px 12px; text-align: left; }}
.findings-table th {{ background: #f3f4f6; }}
.findings-table code {{ font-size: 12px; background: #1e293b; color: #e2e8f0; padding: 2px 6px; border-radius: 4px; }}
.raw-section {{ margin-top: 24px; }}
pre {{ background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; font-size: 12px; }}
</style>
</head>
<body>
<h1>YASA 漏洞扫描报告</h1>
<div class="meta">项目: {escaped_title} | 路径: {escaped_scan} | 语言: {lang}</div>

<h2>结构化漏洞 ({len(findings)} 条)</h2>
{findings_html}

<div class="raw-section">
<h2>原始输出</h2>
<pre>{escaped_raw}</pre>
</div>
</body>
</html>"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        return True
    except Exception:
        return False


def cleanup_old_reports(max_age_days: int = 7) -> int:
    """
    删除超过 max_age_days 天且未收藏的报告目录。
    返回删除的报告数量。
    """
    from config import get_reports_dir
    reports_dir = get_reports_dir()
    if not reports_dir.exists():
        return 0

    cutoff = time.time() - max_age_days * 86400
    deleted = 0

    for user_dir in reports_dir.iterdir():
        if not user_dir.is_dir():
            continue
        for project_dir in user_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for report_dir in list(project_dir.iterdir()):
                if not report_dir.is_dir():
                    continue
                try:
                    if (report_dir / FAVORITE_MARKER).exists():
                        continue
                    if report_dir.stat().st_mtime < cutoff:
                        shutil.rmtree(report_dir, ignore_errors=True)
                        deleted += 1
                except Exception:
                    pass
            # 清理空的项目目录
            try:
                if not any(project_dir.iterdir()):
                    project_dir.rmdir()
            except Exception:
                pass

    return deleted
