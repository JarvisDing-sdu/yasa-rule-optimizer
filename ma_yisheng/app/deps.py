"""Shared dependencies: DB access, auth, task storage."""
import json as _json_mod
from typing import Any, Dict, Optional
from fastapi import Header, HTTPException


def _db():
    from auth import get_db_path
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _set_task(task_id: str, **kwargs) -> None:
    import time as _time
    conn = _db()
    # BEGIN IMMEDIATE 串行化写入，消除 SELECT-then-INSERT/UPDATE 竞态
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT task_id FROM scan_tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO scan_tasks (task_id, user_id, status, scan_path, lang, progress, result, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    kwargs.get("user_id", 0),
                    kwargs.get("status", "pending"),
                    kwargs.get("scan_path"),
                    kwargs.get("lang"),
                    kwargs.get("progress"),
                    _json_mod.dumps(kwargs.get("result"), ensure_ascii=False) if kwargs.get("result") is not None else None,
                    kwargs.get("created_at"),
                )
            )
        else:
            sets, vals = [], []
            for col in ("status", "scan_path", "lang", "progress", "user_id", "created_at"):
                if col in kwargs:
                    sets.append(f"{col}=?")
                    vals.append(kwargs[col])
            if "result" in kwargs:
                sets.append("result=?")
                vals.append(_json_mod.dumps(kwargs["result"], ensure_ascii=False) if kwargs["result"] is not None else None)
            if kwargs.get("status") in ("completed", "failed", "cancelled", "done"):
                sets.append("finished_at=?")
                vals.append(_time.time())
            if sets:
                vals.append(task_id)
                conn.execute(f"UPDATE scan_tasks SET {', '.join(sets)} WHERE task_id=?", vals)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _get_task(task_id: str) -> Optional[Dict[str, Any]]:
    conn = _db()
    row = conn.execute("SELECT * FROM scan_tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("result"):
        try:
            d["result"] = _json_mod.loads(d["result"])
        except Exception:
            pass
    return d


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    from config import JWT_SECRET
    from auth import verify_jwt_token
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="认证格式错误")
    token = parts[1]
    user = verify_jwt_token(token, JWT_SECRET)
    if not user:
        raise HTTPException(status_code=401, detail="认证失败或已过期")
    return user
