"""CVE search + ingest routes: /api/cve/*"""
import threading
import time
import typing as t
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from starlette.concurrency import run_in_threadpool

from app.deps import get_current_user_or_local_desktop
from app.services.rule_service import (
    search_github_advisories,
    search_codeql_tests,
    fetch_cve_detail,
    ingest_cves_to_rules,
    add_rules_to_set,
    build_rule_pipeline,
)

router = APIRouter(prefix="/api/cve", tags=["cve"])

_ingest_jobs_lock = threading.Lock()
_ingest_jobs: t.Dict[str, t.Dict[str, t.Any]] = {}
_latest_job_by_user: t.Dict[int, str] = {}


def _job_snapshot(job: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "total": job["total"],
        "done": job["done"],
        "current": job.get("current", ""),
        "generated": job["generated"],
        "failed": job["failed"],
        "rules_generated": job["rules_generated"],
        "details": list(job["details"]),
        "logs": list(job["logs"][-200:]),
        "error": job.get("error", ""),
        "started_at": job["started_at"],
        "updated_at": job["updated_at"],
    }


def _append_job_log(job: t.Dict[str, t.Any], message: str, ok: t.Optional[bool] = None) -> None:
    job["logs"].append({
        "time": time.time(),
        "message": message,
        "ok": ok,
    })
    job["updated_at"] = time.time()


def _run_ingest_job(job_id: str) -> None:
    with _ingest_jobs_lock:
        job = _ingest_jobs.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["updated_at"] = time.time()

    ghsa_ids = list(job["ghsa_ids"])
    for index, ghsa_id in enumerate(ghsa_ids, start=1):
        with _ingest_jobs_lock:
            job = _ingest_jobs.get(job_id)
            if not job:
                return
            job["current"] = ghsa_id
            _append_job_log(job, f"开始：{ghsa_id}")

        try:
            result = ingest_cves_to_rules(
                user_id=job["user_id"],
                rule_set_id=job["rule_set_id"],
                ghsa_ids=[ghsa_id],
                provider=job["provider"],
                model=job["model"],
                api_key=job["api_key"],
            )
        except Exception as exc:
            result = {
                "generated": 0,
                "failed": 1,
                "rules_generated": 0,
                "details": [{
                    "ghsa_id": ghsa_id,
                    "status": "request_failed",
                    "error": str(exc),
                }],
            }

        details = result.get("details") or []
        generated = int(result.get("generated") or 0)
        failed = int(result.get("failed") or 0)
        rules_generated = int(result.get("rules_generated") or 0)

        with _ingest_jobs_lock:
            job = _ingest_jobs.get(job_id)
            if not job:
                return
            job["done"] = index
            job["generated"] += generated
            job["failed"] += failed
            job["rules_generated"] += rules_generated
            job["details"].extend(details)
            if failed:
                _append_job_log(job, f"失败：{ghsa_id}", False)
            else:
                _append_job_log(job, f"完成：{ghsa_id}，加入 {generated} 条", True)

    with _ingest_jobs_lock:
        job = _ingest_jobs.get(job_id)
        if not job:
            return
        job["status"] = "completed" if job["failed"] == 0 else "completed_with_errors"
        job["current"] = ""
        job["updated_at"] = time.time()


@router.get("/search", summary="搜索 GitHub Advisory 漏洞")
async def search_cve(
    language: str = Query("python"),
    vuln_type: str = Query(""),
    count: int = Query(10, ge=1, le=100),
    keyword: str = Query(""),
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    try:
        results = await search_github_advisories(
            language=language, vuln_type=vuln_type,
            count=count, keyword=keyword,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"results": results, "count": len(results)}


@router.get("/codeql-search", summary="搜索本地 CodeQL 安全测试集")
async def search_codeql(
    language: str = Query("python"),
    vuln_type: str = Query(""),
    count: int = Query(20, ge=0, le=5000),
    keyword: str = Query(""),
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    results = search_codeql_tests(
        language=language,
        vuln_type=vuln_type,
        count=count,
        keyword=keyword,
    )
    return {"results": results, "count": len(results)}


@router.get("/detail/{ghsa_id}", summary="获取 CVE 详情")
async def cve_detail(
    ghsa_id: str,
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    detail = await fetch_cve_detail(ghsa_id)
    if not detail:
        raise HTTPException(status_code=404, detail="无法获取该 Advisory 详情")
    return {"detail": detail}


@router.post("/ingest", summary="将 CVE 转换为规则并加入规则集")
async def ingest_cve(
    body: t.Dict,
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    """body: { ghsa_ids: [...], rule_set_id: int, provider?: str, model?: str }"""
    ghsa_ids = body.get("ghsa_ids", [])
    rule_set_id = body.get("rule_set_id")
    if not ghsa_ids or not rule_set_id:
        raise HTTPException(status_code=400, detail="ghsa_ids 和 rule_set_id 为必填")

    provider = body.get("provider", "deepseek")
    model = body.get("model")
    api_key = body.get("api_key")

    results = await run_in_threadpool(
        ingest_cves_to_rules,
        user_id=user["user_id"],
        rule_set_id=rule_set_id,
        ghsa_ids=ghsa_ids,
        provider=provider,
        model=model,
        api_key=api_key,
    )
    return {"ok": True, **results}


@router.post("/ingest-jobs", summary="启动后台规则生成任务")
async def start_ingest_job(
    body: t.Dict,
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    ghsa_ids = body.get("ghsa_ids", [])
    rule_set_id = body.get("rule_set_id")
    if not ghsa_ids or not rule_set_id:
        raise HTTPException(status_code=400, detail="ghsa_ids 和 rule_set_id 为必填")

    job_id = uuid.uuid4().hex
    now = time.time()
    job = {
        "job_id": job_id,
        "user_id": user["user_id"],
        "rule_set_id": rule_set_id,
        "ghsa_ids": list(ghsa_ids),
        "provider": body.get("provider", "deepseek"),
        "model": body.get("model"),
        "api_key": body.get("api_key"),
        "status": "queued",
        "total": len(ghsa_ids),
        "done": 0,
        "current": "",
        "generated": 0,
        "failed": 0,
        "rules_generated": 0,
        "details": [],
        "logs": [],
        "started_at": now,
        "updated_at": now,
    }
    with _ingest_jobs_lock:
        _ingest_jobs[job_id] = job
        _latest_job_by_user[user["user_id"]] = job_id
        _append_job_log(job, f"任务已创建，共 {len(ghsa_ids)} 个条目")

    thread = threading.Thread(target=_run_ingest_job, args=(job_id,), daemon=True)
    thread.start()
    return {"ok": True, "job": _job_snapshot(job)}


@router.get("/ingest-jobs/latest", summary="获取当前用户最新规则生成任务")
async def latest_ingest_job(
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    with _ingest_jobs_lock:
        job_id = _latest_job_by_user.get(user["user_id"])
        job = _ingest_jobs.get(job_id or "")
        return {"job": _job_snapshot(job) if job else None}


@router.get("/ingest-jobs/{job_id}", summary="获取规则生成任务进度")
async def get_ingest_job(
    job_id: str,
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    with _ingest_jobs_lock:
        job = _ingest_jobs.get(job_id)
        if not job or job["user_id"] != user["user_id"]:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"job": _job_snapshot(job)}


@router.post("/generate-rules", summary="从漏洞描述直接生成规则（不走 CVE）")
async def generate_rules_from_case(
    body: t.Dict,
    user: t.Dict = Depends(get_current_user_or_local_desktop),
):
    """
    body: {
      vuln_case: {...},      -- vulnerability case JSON
      rule_set_id: int,      -- target rule set
      provider?: str,
      model?: str,
      api_key?: str,
    }
    """
    vuln_case = body.get("vuln_case")
    rule_set_id = body.get("rule_set_id")
    if not vuln_case or not rule_set_id:
        raise HTTPException(status_code=400, detail="vuln_case 和 rule_set_id 为必填")

    provider = body.get("provider", "deepseek")
    model = body.get("model")
    api_key = body.get("api_key")

    result = await run_in_threadpool(
        build_rule_pipeline,
        vuln_case,
        provider,
        model,
        api_key,
        test_dirs=None,
        max_iterations=1,
    )
    rules = result["rules"] if result else None
    if not rules:
        raise HTTPException(status_code=500, detail="规则生成失败，LLM 返回为空")

    added = add_rules_to_set(user["user_id"], rule_set_id, rules)
    return {
        "ok": True,
        "rules_generated": len(rules),
        "rules_added": added,
        "rules": rules,
    }
