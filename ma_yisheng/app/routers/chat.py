"""Chat routes: /api/chat/*, agent streaming, conversation memory."""
import os
import time
import json as _json
from typing import Any, Dict, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from app.deps import get_current_user
from app.schemas.scan import ChatRequest
from app.services import memory

# 速率限制（内存模式，滑动窗口）
_RATE_LIMIT_STORE: Dict[str, List[float]] = {}

def _check_rate_limit(key: str, max_req: int = 20, window: int = 60) -> bool:
    now = time.time()
    cutoff = now - window
    bucket = _RATE_LIMIT_STORE.get(key, [])
    bucket = [t for t in bucket if t > cutoff]
    if len(bucket) >= max_req:
        _RATE_LIMIT_STORE[key] = bucket
        return False
    bucket.append(now)
    _RATE_LIMIT_STORE[key] = bucket
    # 定期清理过期 key 防止内存泄漏
    if len(_RATE_LIMIT_STORE) > 2000:
        stale = [k for k, v in _RATE_LIMIT_STORE.items() if all(t <= cutoff for t in v)]
        for k in stale:
            del _RATE_LIMIT_STORE[k]
    return True

router = APIRouter(prefix="/api", tags=["chat"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/chat/upload", summary="上传文件供 Agent 分析")
async def chat_upload(file: UploadFile = File(...), user: Dict = Depends(get_current_user)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".py", ".java", ".go", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".php", ".zip"}:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件最大 10MB")
    import uuid
    save_name = f"{uuid.uuid4().hex}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    with open(save_path, "wb") as f:
        f.write(content)
    try:
        text = content.decode("utf-8", errors="replace")[:50000]
    except Exception:
        text = f"[binary file, {len(content)} bytes]"
    return {"filename": file.filename, "size": len(content), "path": save_path, "preview": text[:3000]}


@router.post("/chat", summary="普通对话")
def chat_endpoint(req: ChatRequest, user: Dict = Depends(get_current_user)):
    if not _check_rate_limit(f"chat:{user['user_id']}"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
    from llm import chat as llm_chat
    messages = req.messages or [{"role": "user", "content": req.get_user_input()}]
    reply = llm_chat(messages)
    if reply is None:
        raise HTTPException(status_code=503, detail="LLM 调用失败")
    return {"reply": reply}


@router.post("/chat/agent", summary="Agent 对话（支持工具调用，兼容旧前端）")
def agent_chat_endpoint(
    req: ChatRequest,
    user: Dict = Depends(get_current_user),
    conversation_id: int = Query(None, description="继续已有对话"),
):
    if not _check_rate_limit(f"agent:{user['user_id']}"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
    from agent import create_agent, agent_invoke, agent_invoke_stream
    from agent_tools import set_agent_user_context

    user_input = req.get_user_input()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 加载或创建对话记忆
    if conversation_id:
        conv = memory.get_conversation(conversation_id, user["user_id"])
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        stored_msgs = conv["messages"]
    else:
        conv = memory.create_conversation(user["user_id"])
        stored_msgs = []

    # 合并：前端传来的历史 + 数据库持久化的历史
    frontend_history = req.get_history()
    chat_history = stored_msgs + frontend_history if frontend_history else stored_msgs

    # 保存当前用户消息
    memory.add_message(conv["id"], user["user_id"], "user", user_input)
    chat_history.append({"role": "user", "content": user_input})

    set_agent_user_context(user["user_id"])
    agent_ctx = create_agent(deep_thinking=req.deep_thinking)
    if not agent_ctx:
        raise HTTPException(status_code=503, detail="Agent 初始化失败，请检查 API 配置")

    # 流式输出
    if req.stream:
        def event_stream():
            reply_parts = []
            try:
                for event in agent_invoke_stream(agent_ctx, user_input, chat_history):
                    yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
                    if event.get("type") in ("done", "reply") and event.get("reply"):
                        reply_parts.append(event.get("reply", ""))
            except Exception as e:
                yield f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                full_reply = "".join(reply_parts)
                if full_reply:
                    memory.add_message(conv["id"], user["user_id"], "assistant", full_reply)
                yield f"data: {_json.dumps({'type': 'conversation', 'id': conv['id']}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # 非流式输出
    result = agent_invoke(agent_ctx, user_input, chat_history)
    reply_text = result.get("reply", "")
    memory.add_message(conv["id"], user["user_id"], "assistant", reply_text)

    return {
        "reply": reply_text,
        "sources": result.get("sources", []),
        "steps": result.get("steps", []),
        "conversation_id": conv["id"],
    }


@router.post("/chat/agent/stream", summary="Agent 对话（纯流式 SSE，新前端专用）")
def agent_chat_stream_endpoint(
    req: ChatRequest,
    user: Dict = Depends(get_current_user),
    conversation_id: int = Query(None),
):
    """纯 SSE 流式，兼容新旧请求格式。"""
    from agent import create_agent, agent_invoke_stream
    from agent_tools import set_agent_user_context

    user_input = req.get_user_input()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息不能为空")

    set_agent_user_context(user["user_id"])

    if conversation_id:
        conv = memory.get_conversation(conversation_id, user["user_id"])
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        chat_history = conv["messages"]
    else:
        conv = memory.create_conversation(user["user_id"])
        chat_history = []

    memory.add_message(conv["id"], user["user_id"], "user", user_input)
    chat_history.append({"role": "user", "content": user_input})

    agent_ctx = create_agent()

    def event_stream():
        reply_parts = []
        try:
            for event in agent_invoke_stream(agent_ctx, user_input, chat_history):
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "reply") and event.get("reply"):
                    reply_parts.append(event.get("reply", ""))
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            full_reply = "".join(reply_parts)
            if full_reply:
                memory.add_message(conv["id"], user["user_id"], "assistant", full_reply)
            yield f"data: {_json.dumps({'type': 'conversation', 'id': conv['id']}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/reports/{report_path:path}/chat", summary="针对报告的对话")
def report_chat_endpoint(report_path: str, req: ChatRequest, user: Dict = Depends(get_current_user)):
    from app.routers.report import _assert_report_owner
    _assert_report_owner(report_path, user["user_id"])
    from llm import chat_with_report
    from report import get_structured_findings
    rd = Path(report_path)
    if not rd.is_dir():
        raise HTTPException(status_code=404, detail="报告目录不存在")
    findings = get_structured_findings(report_path)
    reply = chat_with_report(req.get_user_input(), findings)
    if reply is None:
        raise HTTPException(status_code=503, detail="LLM 调用失败")
    return {"reply": reply}


@router.get("/reports/{report_path:path}/chat/stream", summary="报告流式对话")
def report_chat_stream_endpoint(report_path: str, messages: str, user: Dict = Depends(get_current_user)):
    from app.routers.report import _assert_report_owner
    _assert_report_owner(report_path, user["user_id"])
    from llm import chat_with_report_stream
    from report import get_structured_findings
    rd = Path(report_path)
    if not rd.is_dir():
        raise HTTPException(status_code=404, detail="报告目录不存在")
    try:
        msgs = _json.loads(messages)
    except Exception:
        raise HTTPException(status_code=400, detail="messages 参数格式错误")
    findings = get_structured_findings(report_path)

    def event_stream():
        try:
            for chunk in chat_with_report_stream(msgs, findings):
                yield f"data: {_json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        except Exception:
            pass
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/scan/{task_id}/chain-analysis", summary="跨文件漏洞链分析")
def chain_analysis_endpoint(task_id: str, user: Dict = Depends(get_current_user)):
    from app.deps import _get_task
    task = _get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    if task.get("status") not in ("done", "completed"):
        raise HTTPException(status_code=400, detail="扫描尚未完成")
    scan_path = task.get("scan_path")
    if not scan_path or not os.path.isdir(scan_path):
        raise HTTPException(status_code=400, detail="扫描路径不存在")
    all_findings = []
    result_data = task.get("result") or {}
    if isinstance(result_data, dict):
        for scan in result_data.get("scans", []):
            rdir = scan.get("report_dir", "")
            if rdir and os.path.isdir(rdir):
                from report import get_structured_findings
                all_findings.extend(get_structured_findings(rdir))
    from llm import analyze_cross_file_chains
    result = analyze_cross_file_chains(scan_path, all_findings)
    if not result:
        raise HTTPException(status_code=503, detail="LLM 调用失败或源码为空")
    return {"ok": True, "task_id": task_id, **result}
