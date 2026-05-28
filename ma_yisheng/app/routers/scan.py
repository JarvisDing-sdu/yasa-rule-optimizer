"""Scan routes: /api/scan/*"""
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, File, Form, UploadFile, Header
from typing import Optional

from app.schemas.scan import ScanPathRequest
from app.deps import get_current_user

router = APIRouter(prefix="/api", tags=["scan"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


def _set_task(task_id: str, **kwargs):
    from app.deps import _set_task as _st
    return _st(task_id, **kwargs)


def _get_task(task_id: str):
    from app.deps import _get_task as _gt
    return _gt(task_id)


@router.post("/scan", summary="扫描服务器本地路径")
def scan_server_path(
    req: ScanPathRequest,
    background_tasks: BackgroundTasks,
    user: Dict = Depends(get_current_user),
):
    if not os.path.exists(req.path):
        raise HTTPException(status_code=400, detail=f"路径不存在：{req.path}")

    task_id = str(uuid.uuid4())
    _set_task(
        task_id, status="pending", progress=None, result=None,
        created_at=datetime.now().isoformat(),
        scan_path=req.path, lang=req.lang, user_id=user["user_id"],
    )

    from app.services.scan_service import run_scan_background
    background_tasks.add_task(
        run_scan_background,
        task_id, req.path, req.lang, req.scene, 300, False, "", user["user_id"], req.engine,
    )
    return {"task_id": task_id}


@router.post("/scan/upload", summary="上传 zip 包并扫描")
async def scan_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = Form("auto"),
    scene: str = Form("minimal"),
    timeout: int = Form(300),
    favorite: bool = Form(False),
    engine: str = Form("yasa"),
    user: Dict = Depends(get_current_user),
):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 压缩包")

    from config import MAX_UPLOAD_SIZE as CFG_MAX_UPLOAD
    content = await file.read()
    if len(content) > CFG_MAX_UPLOAD:
        raise HTTPException(status_code=413, detail=f"文件超过大小限制")

    temp_dir = tempfile.mkdtemp(prefix="yasa-upload-")
    try:
        zip_path = os.path.join(temp_dir, "upload.zip")
        with open(zip_path, "wb") as f:
            f.write(content)
        del content
        extract_dir = os.path.join(temp_dir, "src")
        os.makedirs(extract_dir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                member_path = os.path.realpath(os.path.join(extract_dir, member.filename))
                if not member_path.startswith(os.path.realpath(extract_dir) + os.sep):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    raise HTTPException(status_code=400, detail="zip 包含非法路径，拒绝解压")
            zf.extractall(extract_dir)
        os.remove(zip_path)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="zip 文件损坏")
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="文件处理失败，请重试")

    task_id = str(uuid.uuid4())
    _set_task(
        task_id, status="pending", progress=None, result=None,
        created_at=datetime.now().isoformat(),
        scan_path=extract_dir, lang=lang, user_id=user["user_id"],
    )

    from app.services.scan_service import run_scan_background
    background_tasks.add_task(
        run_scan_background,
        task_id, extract_dir, lang, scene, timeout, favorite, temp_dir, user["user_id"], engine,
    )
    return {"task_id": task_id}


@router.get("/scan/{task_id}", summary="查询扫描任务状态")
def get_task(task_id: str, user: Dict = Depends(get_current_user)):
    task = _get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    return {
        "task_id": task_id,
        "status": task.get("status"),
        "progress": task.get("progress"),
        "result": task.get("result"),
        "created_at": task.get("created_at"),
        "scan_path": task.get("scan_path"),
        "lang": task.get("lang"),
    }


@router.get("/tasks", summary="列出当前用户的所有任务")
def list_tasks(user: Dict = Depends(get_current_user)):
    from app.deps import _db
    import json as _json
    conn = _db()
    rows = conn.execute(
        "SELECT task_id, status, scan_path, lang, created_at, progress, result FROM scan_tasks WHERE user_id=? ORDER BY created_at DESC LIMIT 100",
        (user["user_id"],)
    ).fetchall()
    conn.close()
    tasks = []
    for row in rows:
        item = dict(row)
        if item.get("result"):
            try:
                item["result"] = _json.loads(item["result"])
            except Exception:
                pass
        tasks.append(item)
    return {"tasks": tasks, "count": len(tasks)}
