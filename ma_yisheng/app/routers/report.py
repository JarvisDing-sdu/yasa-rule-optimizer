"""Report routes: /api/reports/*"""
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from app.deps import get_current_user
from app.schemas.scan import FindingReviewBody

router = APIRouter(prefix="/api", tags=["reports"])
def _assert_report_owner(report_path: str, user_id: int) -> None:
    from config import get_reports_dir
    try:
        reports_dir = get_reports_dir().resolve()
        rp = Path(report_path).resolve()
        user_prefix = reports_dir / str(user_id)
        rp.relative_to(user_prefix)
    except ValueError:
        raise HTTPException(status_code=403, detail="无权访问此报告")
def _resolve_finding_index(findings: list, body: FindingReviewBody) -> int:
    if body.index is None and not body.fingerprint:
        raise HTTPException(status_code=400, detail="请提供 index 或 fingerprint")
    if body.fingerprint:
        fp = body.fingerprint.strip().lower()
        for i, f in enumerate(findings):
            if str(f.get("fingerprint", "")).lower() == fp:
                return i
        raise HTTPException(status_code=404, detail="找不到对应的漏洞条目")
    idx = int(body.index)
    if idx < 0 or idx >= len(findings):
        raise HTTPException(status_code=404, detail="找不到对应的漏洞条目")
    return idx
@router.get("/reports", summary="列出历史报告")
def get_reports(limit: int = 20, project: str = "", user: Dict = Depends(get_current_user)):
    from report import list_reports
    return {"reports": list_reports(limit=limit, project_filter=project, user_id=user["user_id"])}
@router.get("/reports/{report_path:path}/content", summary="获取报告内容")
def get_report_content_endpoint(report_path: str, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from report import get_report_content
    content = get_report_content(report_path)
    if content is None:
        raise HTTPException(status_code=404, detail="报告不存在或内容为空")
    return {"content": content}
@router.get("/reports/{report_path:path}/findings", summary="获取结构化漏洞列表")
def get_report_findings_endpoint(report_path: str, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from report import get_structured_findings
    rd = Path(report_path)
    if not rd.is_dir():
        raise HTTPException(status_code=404, detail="报告目录不存在")
    if not (rd / "report.json").exists() and not (rd / "report.sarif").exists():
        raise HTTPException(status_code=404, detail="报告不存在")
    findings = get_structured_findings(report_path)
    return {"findings": findings, "count": len(findings)}
@router.post("/reports/{report_path:path}/findings/review", summary="AI 二次研判")
def review_single_finding_endpoint(report_path: str, body: FindingReviewBody, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from llm import review_single_finding
    from report import get_structured_findings, update_report_findings
    rd = Path(report_path)
    if not rd.is_dir() or not (rd / "report.json").exists():
        raise HTTPException(status_code=404, detail="报告不存在或缺少 report.json")
    findings = get_structured_findings(report_path)
    if not findings:
        raise HTTPException(status_code=400, detail="当前报告无 findings")
    idx = _resolve_finding_index(findings, body)
    reviewed = review_single_finding(findings[idx])
    if not reviewed:
        raise HTTPException(status_code=503, detail="LLM 研判失败")
    findings[idx]["llm_verdict"] = reviewed["verdict"]
    findings[idx]["llm_reason"] = reviewed["reason"]
    findings[idx]["llm_reviewed_at"] = datetime.now().isoformat()
    update_report_findings(report_path, findings)
    return {"ok": True, "index": idx, "fingerprint": findings[idx].get("fingerprint"), **reviewed}
@router.post("/reports/{report_path:path}/findings/fix", summary="生成修复建议")
def fix_single_finding_endpoint(report_path: str, body: FindingReviewBody, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from llm import fix_finding
    from report import get_structured_findings, update_report_findings
    rd = Path(report_path)
    if not rd.is_dir():
        raise HTTPException(status_code=404, detail="报告目录不存在")
    findings = get_structured_findings(report_path)
    if not findings:
        raise HTTPException(status_code=400, detail="当前报告无 findings")
    idx = _resolve_finding_index(findings, body)
    result = fix_finding(findings[idx])
    if not result:
        raise HTTPException(status_code=503, detail="LLM 调用失败")
    findings[idx]["fix_explanation"] = result["explanation"]
    findings[idx]["fix_code"] = result["fix_code"]
    findings[idx]["attack_scenario"] = result["attack_scenario"]
    findings[idx]["fix_generated_at"] = datetime.now().isoformat()
    update_report_findings(report_path, findings)
    return {"ok": True, "index": idx, **result}
@router.post("/reports/{report_path:path}/findings/exploit", summary="可利用性评估")
def exploit_assessment_endpoint(report_path: str, body: FindingReviewBody, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from llm import assess_exploitability
    from report import get_structured_findings, update_report_findings
    rd = Path(report_path)
    if not rd.is_dir():
        raise HTTPException(status_code=404, detail="报告目录不存在")
    findings = get_structured_findings(report_path)
    if not findings:
        raise HTTPException(status_code=400, detail="当前报告无 findings")
    idx = _resolve_finding_index(findings, body)
    result = assess_exploitability(findings[idx])
    if not result:
        raise HTTPException(status_code=503, detail="LLM 调用失败")
    for key in ("exploitability", "preconditions", "attack_path", "poc_hint", "impact", "difficulty"):
        findings[idx][f"exploit_{key}"] = result.get(key)
    findings[idx]["exploit_assessed_at"] = datetime.now().isoformat()
    update_report_findings(report_path, findings)
    return {"ok": True, "index": idx, **result}
@router.get("/reports/{report_path:path}/export", summary="导出报告为 HTML")
def export_report_endpoint(report_path: str, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from report import export_report_html
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    try:
        export_report_html(report_path, tmp.name)
        return FileResponse(tmp.name, media_type="text/html", filename=f"report_{report_path.split('/')[-1]}.html")
    except Exception:
        raise HTTPException(status_code=500, detail="导出失败")
@router.post("/reports/{report_path:path}/favorite", summary="切换收藏状态")
def toggle_favorite_endpoint(report_path: str, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from report import is_favorite, mark_as_favorite, unmark_favorite
    if is_favorite(report_path):
        unmark_favorite(report_path)
        return {"ok": True, "favorite": False}
    else:
        mark_as_favorite(report_path)
        return {"ok": True, "favorite": True}

@router.delete("/reports/{report_path:path}", summary="删除报告")
def delete_report_endpoint(report_path: str, user: Dict = Depends(get_current_user)):
    _assert_report_owner(report_path, user["user_id"])
    from report import delete_report
    ok = delete_report(report_path)
    if not ok:
        raise HTTPException(status_code=400, detail="删除失败")
    return {"ok": True}
