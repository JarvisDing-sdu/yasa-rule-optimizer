"""CVE search + ingest routes: /api/cve/*"""
import typing as t
from fastapi import APIRouter, HTTPException, Depends, Query

from app.deps import get_current_user
from app.services.rule_service import (
    search_github_advisories,
    fetch_cve_detail,
    ingest_cves_to_rules,
    add_rules_to_set,
    build_rule_pipeline,
)

router = APIRouter(prefix="/api/cve", tags=["cve"])


@router.get("/search", summary="搜索 GitHub Advisory 漏洞")
async def search_cve(
    language: str = Query("python"),
    vuln_type: str = Query(""),
    count: int = Query(10, ge=1, le=30),
    keyword: str = Query(""),
    user: t.Dict = Depends(get_current_user),
):
    try:
        results = await search_github_advisories(
            language=language, vuln_type=vuln_type,
            count=count, keyword=keyword,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"results": results, "count": len(results)}


@router.get("/detail/{ghsa_id}", summary="获取 CVE 详情")
async def cve_detail(
    ghsa_id: str,
    user: t.Dict = Depends(get_current_user),
):
    detail = await fetch_cve_detail(ghsa_id)
    if not detail:
        raise HTTPException(status_code=404, detail="无法获取该 Advisory 详情")
    return {"detail": detail}


@router.post("/ingest", summary="将 CVE 转换为规则并加入规则集")
async def ingest_cve(
    body: t.Dict,
    user: t.Dict = Depends(get_current_user),
):
    """body: { ghsa_ids: [...], rule_set_id: int, provider?: str, model?: str }"""
    ghsa_ids = body.get("ghsa_ids", [])
    rule_set_id = body.get("rule_set_id")
    if not ghsa_ids or not rule_set_id:
        raise HTTPException(status_code=400, detail="ghsa_ids 和 rule_set_id 为必填")

    provider = body.get("provider", "deepseek")
    model = body.get("model")
    api_key = body.get("api_key")

    results = ingest_cves_to_rules(
        user_id=user["user_id"],
        rule_set_id=rule_set_id,
        ghsa_ids=ghsa_ids,
        provider=provider,
        model=model,
        api_key=api_key,
    )
    return {"ok": True, **results}


@router.post("/generate-rules", summary="从漏洞描述直接生成规则（不走 CVE）")
async def generate_rules_from_case(
    body: t.Dict,
    user: t.Dict = Depends(get_current_user),
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

    result = build_rule_pipeline(vuln_case, provider, model, api_key,
                                 test_dirs=None, max_iterations=1)
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
