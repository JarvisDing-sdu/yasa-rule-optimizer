"""Rule set management routes: /api/rule-sets/*"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.schemas.rule_set import RuleSetCreate, RuleSetCloneOfficial, RuleToggle
from app.deps import get_current_user_or_local_desktop
from app.services.rule_service import (
    get_official_rule_set_detail,
    get_official_rule_sets,
    list_user_rule_sets,
    create_rule_set,
    get_rule_set_detail,
    delete_rule_set,
    toggle_rule_in_set,
    clone_official_rules,
    add_rules_to_set,
)

router = APIRouter(prefix="/api/rule-sets", tags=["rule-sets"])


@router.get("", summary="列出所有可用规则集")
def list_rule_sets(
    user: Dict = Depends(get_current_user_or_local_desktop),
    include_official: bool = Query(True),
) -> Dict[str, Any]:
    result = []
    if include_official:
        result.extend(get_official_rule_sets())
    result.extend(list_user_rule_sets(user["user_id"]))
    return {"rule_sets": result, "count": len(result)}


@router.post("", summary="创建新规则集")
def create_new_rule_set(
    req: RuleSetCreate,
    user: Dict = Depends(get_current_user_or_local_desktop),
) -> Dict[str, Any]:
    rs = create_rule_set(
        user_id=user["user_id"],
        name=req.name,
        lang=req.lang,
        scene=req.scene,
        description=req.description,
    )
    return {"ok": True, "rule_set": rs}


@router.get("/{rule_set_id}", summary="获取规则集详情")
def get_rule_set(
    rule_set_id: str,
    user: Dict = Depends(get_current_user_or_local_desktop),
) -> Dict[str, Any]:
    if rule_set_id.startswith("official_"):
        detail = get_official_rule_set_detail(rule_set_id)
    else:
        try:
            rid = int(rule_set_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="规则集不存在")
        detail = get_rule_set_detail(user["user_id"], rid)
    if not detail:
        raise HTTPException(status_code=404, detail="规则集不存在")
    return {"rule_set": detail}


@router.delete("/{rule_set_id}", summary="删除规则集")
def remove_rule_set(
    rule_set_id: int,
    user: Dict = Depends(get_current_user_or_local_desktop),
) -> Dict[str, Any]:
    ok = delete_rule_set(user["user_id"], rule_set_id)
    if not ok:
        raise HTTPException(status_code=404, detail="规则集不存在或无权删除")
    return {"ok": True}


@router.post("/{rule_set_id}/clone-official", summary="克隆官方规则")
def clone_official(
    rule_set_id: int = 0,
    req: RuleSetCloneOfficial = RuleSetCloneOfficial(),
    user: Dict = Depends(get_current_user_or_local_desktop),
) -> Dict[str, Any]:
    if rule_set_id > 0:
        detail = get_rule_set_detail(user["user_id"], rule_set_id)
        if not detail:
            raise HTTPException(status_code=404, detail="规则集不存在")
        import json
        from pathlib import Path
        rules_dir = Path(__file__).resolve().parent.parent.parent / "rules"
        l = detail["lang"]; s = detail["scene"]; fname = f"rule_config_{l}_{s}.json"
        fpath = rules_dir / fname
        if not fpath.exists():
            raise HTTPException(status_code=404, detail="官方规则文件不存在")
        data = json.loads(fpath.read_text(encoding="utf-8"))
        rules_list = data if isinstance(data, list) else [data]
        added = add_rules_to_set(user["user_id"], rule_set_id, rules_list)
        return {"ok": True, "rule_set": detail, "added": added}
    else:
        rs = clone_official_rules(
            user_id=user["user_id"],
            lang=req.lang,
            scene=req.scene,
        )
        if not rs:
            raise HTTPException(status_code=500, detail="克隆失败，官方规则文件不存在")
        return {"ok": True, "rule_set": rs}


@router.put("/{rule_set_id}/rules/{rule_db_id}/toggle", summary="启用/禁用规则")
def toggle_rule(
    rule_set_id: int,
    rule_db_id: int,
    req: RuleToggle,
    user: Dict = Depends(get_current_user_or_local_desktop),
) -> Dict[str, Any]:
    ok = toggle_rule_in_set(user["user_id"], rule_set_id, rule_db_id, req.is_enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"ok": True}


@router.delete("/{rule_set_id}/rules/{rule_db_id}", summary="删除规则")
def remove_rule_from_set(
    rule_set_id: int,
    rule_db_id: int,
    user: Dict = Depends(get_current_user_or_local_desktop),
) -> Dict[str, Any]:
    from app.services.rule_service import remove_rule_from_set as _remove
    ok = _remove(user["user_id"], rule_set_id, rule_db_id)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"ok": True}
