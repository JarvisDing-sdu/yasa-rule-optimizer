# -*- coding: utf-8 -*-
"""LLM 调用模块（DeepSeek/OpenAI 兼容）"""

import json
import logging
import os
import re
import traceback
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

_log = logging.getLogger("llm")


def _ensure_no_proxy():
    """确保 LLM API 域名不走系统代理（兼容 TUN/全局代理场景）"""
    try:
        host = urlparse(LLM_BASE_URL).hostname or ""
        if not host:
            return
        no_proxy = os.environ.get("NO_PROXY", "")
        existing = [x.strip() for x in no_proxy.split(",") if x.strip()]
        if host not in existing:
            existing.append(host)
            os.environ["NO_PROXY"] = ",".join(existing)
            os.environ["no_proxy"] = ",".join(existing)
    except Exception:
        pass


_client = None


def _get_client():
    """获取 OpenAI 兼容的客户端（单例复用，避免连接池泄漏）"""
    global _client
    if _client is not None:
        return _client
    _ensure_no_proxy()
    try:
        from openai import OpenAI
        import httpx
        _client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            http_client=httpx.Client(proxy=None),
        )
        return _client
    except (ImportError, TypeError):
        try:
            from openai import OpenAI
            _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
            return _client
        except ImportError:
            return None


def call_llm(system: str, user: str) -> Optional[str]:
    """调用 LLM，返回回复内容。失败返回 None。"""
    client = _get_client()
    if not client or not LLM_API_KEY:
        return None
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            stream=False,
        )
        content = resp.choices[0].message.content
        return (content or "").strip()
    except Exception:
        _log.error("call_llm failed:\n%s", traceback.format_exc())
        return None


def parse_language(user_input: str) -> Optional[str]:
    """
    从用户自然语言输入解析出语言。
    返回 python/java/go/js/php/c 之一，解析失败返回 None。
    """
    inp = (user_input or "").strip()
    if not inp:
        return None

    # 先尝试直接匹配数字
    direct = {"1": "python", "2": "java", "3": "go", "4": "js", "5": "php", "6": "c"}
    if inp in direct:
        return direct[inp]

    # 尝试关键词
    inp_lower = inp.lower()
    for kw, lang in [("python", "python"), ("java", "java"), ("go", "go"), ("php", "php"), ("js", "js"), ("javascript", "js"), ("c语言", "c"), ("c language", "c")]:
        if kw in inp_lower:
            return lang

    # 调用 LLM 解析
    system = """你是一个语言识别助手。用户会输入一句话，可能是对编程语言的选择或纠正。
请从用户输入中识别出编程语言，只返回以下之一：python、java、go、js、php、c。
如果无法识别，只返回：unknown"""
    result = call_llm(system, inp)
    if not result:
        return None
    result = result.lower().strip()
    if result in ("python", "java", "go", "js", "php", "c"):
        return result
    return None


def parse_scene(user_input: str, lang: str = "") -> Optional[str]:
    """
    从用户输入解析模式。返回 minimal/full，失败返回 None。
    """
    inp = (user_input or "").strip().lower()
    if inp in ("1", "minimal", "精简", "快"):
        return "minimal"
    if inp in ("2", "full", "全面", "慢"):
        return "full"
    if "精简" in inp or "快" in inp:
        return "minimal"
    if "全面" in inp or "慢" in inp:
        return "full"
    return None


def chat(messages: list) -> Optional[str]:
    """
    多轮对话，messages 格式：[{"role": "user"|"assistant", "content": "..."}, ...]
    返回 assistant 的回复，失败返回 None。
    """
    client = _get_client()
    if not client or not LLM_API_KEY:
        return None
    system = "你是 DeepSeek，扮演「马医生」这个角色——一个代码安全扫描和漏洞分析助手。你说话温和、专业，会用比喻把技术问题讲清楚，偶尔带一点幽默。请用中文回复。"
    api_messages = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m.get("content", "")} for m in messages
    ]
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=api_messages,
            stream=False,
        )
        content = resp.choices[0].message.content
        return (content or "").strip()
    except Exception:
        _log.error("chat failed:\n%s", traceback.format_exc())
        return None


def chat_stream(messages: list, on_chunk):
    """
    流式对话，每收到一块内容调用 on_chunk(accumulated_text)。
    on_chunk 会在工作线程调用，GUI 更新需用 app.after 切回主线程。
    成功返回最终文本，失败返回 None。
    """
    client = _get_client()
    if not client or not LLM_API_KEY:
        return None
    system = "你是 DeepSeek，扮演「马医生」这个角色——一个代码安全扫描和漏洞分析助手。你说话温和、专业，会用比喻把技术问题讲清楚，偶尔带一点幽默。请用中文回复。"
    api_messages = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m.get("content", "")} for m in messages
    ]
    try:
        stream = client.chat.completions.create(
            model=LLM_MODEL,
            messages=api_messages,
            stream=True,
        )
        accumulated = ""
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and getattr(delta, "content", None):
                accumulated += delta.content
                on_chunk(accumulated)
        return accumulated.strip() or None
    except Exception:
        _log.error("chat_stream failed:\n%s", traceback.format_exc())
        return None


def _build_review_batch(findings: List[Dict[str, Any]], start: int, batch_size: int) -> tuple:
    """构建一个研判批次的 LLM 请求参数，返回 (system, user_content, start, batch_size)"""
    batch = findings[start : start + batch_size]
    batch_text = []
    for i, f in enumerate(batch):
        idx = start + i
        flow = " -> ".join(f"L{step.get('line')}" for step in (f.get("code_flow") or [])[:4])
        batch_text.append(
            f"[{idx}] {f.get('vuln_name', '')} | {f.get('file', '')}:{f.get('line', 0)}\n"
            f"  代码: {f.get('snippet', '')[:80]}\n"
            f"  污点路径: {flow}"
        )
    user_content = "请逐条研判以下漏洞，判断是「真漏洞」「误报」还是「需人工确认」。\n\n" + "\n\n".join(batch_text)
    user_content += "\n\n请严格按 JSON 数组格式回复，每项 {\"i\": 序号, \"v\": \"真漏洞\"|\"误报\"|\"需人工确认\", \"r\": \"一句话理由\"}，不要其他内容。"
    system = """你是代码安全专家。根据漏洞类型、代码上下文、污点路径，判断扫描结果是否为真漏洞。
- 真漏洞：用户输入可到达危险 sink，存在实际利用可能
- 误报：可信来源（如配置、常量）、已 sanitize、或明显误判
- 需人工确认：无法确定，需人工看代码"""
    return system, user_content, start


def _parse_review_result(result: str, reviewed: List[Dict], total_len: int):
    """解析单个批次的 LLM 研判结果，原地更新 reviewed 列表"""
    if not result:
        return
    try:
        arr = None
        m = re.search(r"\[[\s\S]*\]", result)
        if m:
            arr = json.loads(m.group())
        if not arr and result.strip().startswith("["):
            arr = json.loads(result)
        if arr:
            for item in arr:
                i = item.get("i", -1)
                if isinstance(i, str) and i.isdigit():
                    i = int(i)
                if 0 <= i < total_len:
                    v = str(item.get("v", "")).strip()
                    r = str(item.get("r", "")).strip()
                    if "真" in v or "true" in v.lower():
                        reviewed[i]["llm_verdict"] = "true_positive"
                    elif "误" in v or "false" in v.lower():
                        reviewed[i]["llm_verdict"] = "false_positive"
                    else:
                        reviewed[i]["llm_verdict"] = "needs_review"
                    reviewed[i]["llm_reason"] = r or v
    except Exception:
        pass


def review_single_finding(finding: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    对单条 finding 做 LLM 二次研判（供用户点击触发）。
    返回 {"verdict": "true_positive"|"false_positive"|"needs_review", "reason": str}，失败返回 None。
    """
    if not finding or not LLM_API_KEY:
        return None

    flow = " -> ".join(
        f"L{step.get('line')}" for step in (finding.get("code_flow") or [])[:10]
    )
    user_content = (
        f"漏洞类型: {finding.get('vuln_name', '')} ({finding.get('sink_attribute', '')})\n"
        f"位置: {finding.get('file', '')}:{finding.get('line', 0)}\n"
        f"规则: {finding.get('sink_rule', '')}\n"
        f"扫描器说明: {finding.get('message', '')}\n"
        f"代码片段:\n{finding.get('snippet', '')[:800]}\n"
        f"污点路径摘要: {flow}\n\n"
        "请判断本条静态扫描结果是「真漏洞」「误报」还是「需人工确认」。\n"
        '请严格只输出一个 JSON 对象，不要 markdown，格式：'
        '{"v":"真漏洞"|"误报"|"需人工确认","r":"一句话理由"}'
    )
    system = """你是代码安全专家。根据漏洞类型、代码片段、污点路径判断扫描结果是否成立。
- 真漏洞：不可信数据可到达危险 sink，存在现实利用可能
- 误报：来源可信、已校验/转义、或明显不构成漏洞
- 需人工确认：信息不足，必须人工看完整代码与业务
结论供开发参考，最终责任在人。"""
    result = call_llm(system, user_content)
    if not result:
        return None
    try:
        m = re.search(r"\{[\s\S]*\}", result)
        if not m:
            return None
        obj = json.loads(m.group())
        v = str(obj.get("v", "")).strip()
        r = str(obj.get("r", "")).strip()
        if "真" in v or "true" in v.lower():
            verdict = "true_positive"
        elif "误" in v or "false" in v.lower():
            verdict = "false_positive"
        else:
            verdict = "needs_review"
        return {"verdict": verdict, "reason": r or v}
    except Exception:
        _log.error("review_single_finding failed:\n%s", traceback.format_exc())
        return None


def review_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    对每条漏洞进行 LLM 二次研判，判断：真漏洞 / 误报 / 需人工确认。
    返回带 llm_verdict、llm_reason 的 findings 列表。
    批次间并行调用 LLM 提升速度。
    """
    if not findings or not LLM_API_KEY:
        return findings

    from concurrent.futures import ThreadPoolExecutor, as_completed

    BATCH_SIZE = 5
    MAX_WORKERS = 4
    reviewed = list(findings)

    batches = []
    for start in range(0, len(findings), BATCH_SIZE):
        batches.append(_build_review_batch(findings, start, BATCH_SIZE))

    def _call_batch(batch_args):
        system, user_content, start = batch_args
        return start, call_llm(system, user_content)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_call_batch, b): b for b in batches}
        for future in as_completed(futures):
            try:
                start, result = future.result()
                _parse_review_result(result, reviewed, len(reviewed))
            except Exception:
                pass

    return reviewed


def analyze_yasa_results(yasa_output: str) -> Optional[str]:
    """
    用 DeepSeek 分析 YASA 扫描结果，生成易读的漏洞说明。
    失败返回 None。
    """
    if not yasa_output or not yasa_output.strip():
        return None
    system = """你是一个代码安全分析助手。用户会给你 YASA 静态分析工具的扫描输出。
请用简洁清晰的中文总结：
1. 检测到哪些漏洞（类型、位置、风险等级）
2. 漏洞的原因简要说明
3. 修复建议（如有）
如果检测结果为空或未发现漏洞，请说明"未发现漏洞"。
保持简洁，不要冗长。"""
    content = yasa_output[:8000] if len(yasa_output) > 8000 else yasa_output
    return call_llm(system, content)


def fix_finding(finding: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    针对单条漏洞生成修复建议和修复代码。
    返回 {"explanation": str, "fix_code": str, "attack_scenario": str}，失败返回 None。
    """
    if not finding or not LLM_API_KEY:
        return None

    flow = " -> ".join(
        f"L{step.get('line')}" for step in (finding.get("code_flow") or [])[:10]
    )
    user_content = (
        f"漏洞类型: {finding.get('vuln_name', '')} ({finding.get('sink_attribute', '')})\n"
        f"位置: {finding.get('file', '')}:{finding.get('line', 0)}\n"
        f"规则: {finding.get('sink_rule', '')}\n"
        f"代码片段:\n{finding.get('snippet', '')[:1200]}\n"
        f"污点路径: {flow}\n\n"
        "请完成以下三项，严格只输出一个 JSON 对象，不要 markdown 代码块：\n"
        '{"explanation":"漏洞原理说明（2-3句）","fix_code":"修复后的代码片段","attack_scenario":"攻击者如何利用此漏洞（1-2句，具体说明攻击载荷和危害）"}'
    )
    system = """你是代码安全专家，擅长漏洞修复。
- explanation：用简洁中文解释漏洞成因，不超过3句
- fix_code：给出修复后的代码片段，保持原有语言和风格，只改有问题的部分
- attack_scenario：具体描述攻击者如何利用此漏洞，包括攻击载荷示例和实际危害
只输出 JSON，不要任何其他内容。"""

    result = call_llm(system, user_content)
    if not result:
        return None
    try:
        m = re.search(r"\{[\s\S]*\}", result)
        if not m:
            return None
        obj = json.loads(m.group())
        return {
            "explanation": str(obj.get("explanation", "")).strip(),
            "fix_code": str(obj.get("fix_code", "")).strip(),
            "attack_scenario": str(obj.get("attack_scenario", "")).strip(),
        }
    except Exception:
        _log.error("fix_finding failed:\n%s", traceback.format_exc())
        return None


def assess_exploitability(finding: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    对单条漏洞做可利用性评估：攻击路径完整性、前置条件、实际危害等级、PoC 思路。
    返回结构化结果，失败返回 None。
    """
    if not finding or not LLM_API_KEY:
        return None

    flow = " -> ".join(
        f"L{step.get('line')}" for step in (finding.get("code_flow") or [])[:10]
    )
    user_content = (
        f"漏洞类型: {finding.get('vuln_name', '')} ({finding.get('sink_attribute', '')})\n"
        f"位置: {finding.get('file', '')}:{finding.get('line', 0)}\n"
        f"规则: {finding.get('sink_rule', '')}\n"
        f"代码片段:\n{finding.get('snippet', '')[:1200]}\n"
        f"污点路径: {flow}\n\n"
        "请从攻击者视角评估此漏洞的实际可利用性，严格只输出一个 JSON 对象：\n"
        '{"exploitability":"高|中|低","preconditions":"利用此漏洞需要满足的前置条件（认证状态、参数可控性等）","attack_path":"完整攻击路径描述（从入口到危害）","poc_hint":"PoC 构造思路（不超过3句）","impact":"实际危害（数据泄露/RCE/权限提升等，说明影响范围）","difficulty":"利用难度说明"}'
    )
    system = """你是渗透测试专家，擅长漏洞可利用性分析。
评估维度：
- exploitability 高：无需特殊条件，攻击者可直接利用
- exploitability 中：需要一定前置条件（如登录态、特定参数）
- exploitability 低：利用条件苛刻或危害有限
只输出 JSON，不要任何其他内容。"""

    result = call_llm(system, user_content)
    if not result:
        return None
    try:
        m = re.search(r"\{[\s\S]*\}", result)
        if not m:
            return None
        obj = json.loads(m.group())
        return {
            "exploitability": str(obj.get("exploitability", "")).strip(),
            "preconditions": str(obj.get("preconditions", "")).strip(),
            "attack_path": str(obj.get("attack_path", "")).strip(),
            "poc_hint": str(obj.get("poc_hint", "")).strip(),
            "impact": str(obj.get("impact", "")).strip(),
            "difficulty": str(obj.get("difficulty", "")).strip(),
        }
    except Exception:
        _log.error("assess_exploitability failed:\n%s", traceback.format_exc())
        return None


def audit_business_logic(scan_path: str, findings: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    业务逻辑漏洞审计：读取扫描目录源文件，让 LLM 从业务角度找权限绕过/越权/逻辑缺陷。
    返回 {"issues": [...], "summary": str}，失败返回 None。
    """
    if not LLM_API_KEY:
        return None

    import os as _os
    from pathlib import Path as _Path

    SUPPORTED_EXT = {".py", ".java", ".go", ".js", ".ts", ".jsx", ".tsx", ".php", ".c", ".h"}
    MAX_CHARS = 800_000  # 约 200K token，给 1M 窗口留余量

    # 收集源文件内容
    code_parts = []
    total_chars = 0
    try:
        for root, dirs, files in _os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "__pycache__", "vendor", "dist", "build"}]
            for fname in sorted(files):
                if _Path(fname).suffix.lower() not in SUPPORTED_EXT:
                    continue
                fpath = _os.path.join(root, fname)
                rel = _os.path.relpath(fpath, scan_path)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if len(content) > 50_000:
                        content = content[:50_000] + "\n... (截断)"
                    part = f"\n\n### 文件: {rel}\n```\n{content}\n```"
                    if total_chars + len(part) > MAX_CHARS:
                        break
                    code_parts.append(part)
                    total_chars += len(part)
                except Exception:
                    continue
    except Exception:
        return None

    if not code_parts:
        return None

    # 把已知静态漏洞摘要也注入，帮助 LLM 聚焦
    known = ""
    if findings:
        lines = [f"- {f.get('vuln_name','')} @ {f.get('file','')}:{f.get('line',0)}" for f in findings[:20]]
        known = "\n\n已知静态扫描发现的漏洞（供参考，不要重复列举）：\n" + "\n".join(lines)

    user_content = (
        "以下是待审计的完整项目源代码。请从业务逻辑角度找出静态扫描工具无法发现的漏洞，"
        "重点关注：权限绕过、越权访问、逻辑缺陷、状态机问题、竞态条件、不安全的直接对象引用（IDOR）等。"
        + known
        + "\n\n源代码：" + "".join(code_parts)
        + "\n\n请严格只输出一个 JSON 对象：\n"
        '{"issues":[{"title":"漏洞标题","file":"文件路径","description":"漏洞描述","severity":"高|中|低","recommendation":"修复建议"}],"summary":"整体业务逻辑安全评估（2-3句）"}'
    )
    system = """你是资深代码审计专家，专注业务逻辑漏洞。
不要重复静态扫描已发现的语法层漏洞（SQL注入、XSS等），专注于：
- 认证/授权逻辑缺陷
- 越权（水平/垂直）
- 业务流程绕过
- 状态机/时序问题
- 数据一致性问题
只输出 JSON，不要任何其他内容。"""

    result = call_llm(system, user_content)
    if not result:
        return None
    try:
        m = re.search(r"\{[\s\S]*\}", result, re.DOTALL)
        if not m:
            return None
        obj = json.loads(m.group())
        return {
            "issues": obj.get("issues", []),
            "summary": str(obj.get("summary", "")).strip(),
            "files_analyzed": len(code_parts),
            "chars_analyzed": total_chars,
        }
    except Exception:
        _log.error("audit_business_logic failed:\n%s", traceback.format_exc())
        return None


def analyze_cross_file_chains(scan_path: str, findings: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    跨文件漏洞链分析：把整个项目源码塞进 LLM（利用 DeepSeek V4 Pro 1M 上下文），
    找规则引擎看不到的跨文件数据流漏洞链。
    返回 {"chains": [...], "summary": str}，失败返回 None。
    """
    if not LLM_API_KEY:
        return None

    import os as _os
    from pathlib import Path as _Path

    SUPPORTED_EXT = {".py", ".java", ".go", ".js", ".ts", ".jsx", ".tsx", ".php", ".c", ".h"}
    MAX_CHARS = 2_000_000  # 约 500K token，DeepSeek V4 Pro 1M 窗口的一半留给输出

    code_parts = []
    total_chars = 0
    file_index = []
    try:
        for root, dirs, files in _os.walk(scan_path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "__pycache__", "vendor", "dist", "build"}]
            for fname in sorted(files):
                if _Path(fname).suffix.lower() not in SUPPORTED_EXT:
                    continue
                fpath = _os.path.join(root, fname)
                rel = _os.path.relpath(fpath, scan_path)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if len(content) > 100_000:
                        content = content[:100_000] + "\n... (截断)"
                    part = f"\n\n### [{len(file_index)}] {rel}\n```\n{content}\n```"
                    if total_chars + len(part) > MAX_CHARS:
                        break
                    code_parts.append(part)
                    file_index.append(rel)
                    total_chars += len(part)
                except Exception:
                    continue
    except Exception:
        return None

    if not code_parts:
        return None

    known = ""
    if findings:
        lines = [f"- [{i}] {f.get('vuln_name','')} @ {f.get('file','')}:{f.get('line',0)}" for i, f in enumerate(findings[:30])]
        known = "\n\n静态扫描已发现的单文件漏洞（作为起点参考）：\n" + "\n".join(lines)

    user_content = (
        f"以下是完整项目源码（共 {len(file_index)} 个文件）。"
        "请找出跨文件的漏洞利用链：即污染数据从一个文件的入口进入，经过多个文件的传递/处理，最终在另一个文件触发危险操作。"
        "这类漏洞是单文件静态分析工具无法发现的。"
        + known
        + "\n\n源代码：" + "".join(code_parts)
        + "\n\n请严格只输出一个 JSON 对象：\n"
        '{"chains":[{"title":"漏洞链标题","severity":"高|中|低","entry_file":"入口文件","entry_line":0,"sink_file":"触发文件","sink_line":0,"chain":"完整调用链描述（文件A:函数→文件B:函数→...→危险操作）","vuln_type":"漏洞类型","description":"详细说明"}],"summary":"跨文件漏洞链分析总结（2-3句）"}'
    )
    system = """你是代码安全专家，专注跨文件数据流分析（污点分析）。
目标：找出单文件静态分析工具无法发现的漏洞链，即：
- 用户输入在文件A进入系统
- 经过文件B、C的处理/传递（可能经过多层调用）
- 最终在文件D触发危险操作（SQL执行、命令执行、文件写入、反序列化等）
重点关注：函数调用链、模块间数据传递、全局变量/共享状态的跨文件污染。
只输出 JSON，不要任何其他内容。"""

    result = call_llm(system, user_content)
    if not result:
        return None
    try:
        m = re.search(r"\{[\s\S]*\}", result, re.DOTALL)
        if not m:
            return None
        obj = json.loads(m.group())
        return {
            "chains": obj.get("chains", []),
            "summary": str(obj.get("summary", "")).strip(),
            "files_analyzed": len(file_index),
            "chars_analyzed": total_chars,
        }
    except Exception:
        _log.error("analyze_cross_file_chains failed:\n%s", traceback.format_exc())
        return None


def chat_with_report(
    messages: List[Dict[str, str]],
    findings: List[Dict[str, Any]],
) -> Optional[str]:
    """
    带漏洞报告上下文的对话。findings 作为系统上下文注入，用户可针对报告提问。
    messages 格式：[{"role": "user"|"assistant", "content": "..."}, ...]
    """
    client = _get_client()
    if not client or not LLM_API_KEY:
        return None

    # 构建漏洞摘要注入到 system prompt
    if findings:
        vuln_lines = []
        for i, f in enumerate(findings[:30]):  # 最多30条，避免超 token
            verdict = f.get("llm_verdict", "")
            verdict_str = {"true_positive": "✅真漏洞", "false_positive": "❌误报", "needs_review": "⚠️待确认"}.get(verdict, "")
            flow = " -> ".join(f"L{s.get('line')}" for s in (f.get("code_flow") or [])[:4])
            vuln_lines.append(
                f"[{i}] {f.get('severity','')} | {f.get('vuln_name','')} | "
                f"{f.get('file','')}:{f.get('line',0)} {verdict_str}\n"
                f"    代码: {(f.get('snippet') or '')[:80]}\n"
                f"    路径: {flow}"
            )
        report_ctx = "当前报告共 {} 条漏洞：\n\n{}".format(len(findings), "\n\n".join(vuln_lines))
    else:
        report_ctx = "当前报告未发现漏洞。"

    system = (
        "你是 DeepSeek，扮演「马医生」这个代码安全分析角色。用户正在查看一份扫描报告，你已掌握完整漏洞列表。\n\n"
        + report_ctx
        + "\n\n用户可以问你：某条漏洞怎么修、是否误报、攻击者如何利用、整体风险评估等。"
        "回答要具体，引用漏洞编号 [N] 和代码位置。用中文回复。"
    )

    api_messages = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m.get("content", "")} for m in messages
    ]
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=api_messages,
            stream=False,
        )
        content = resp.choices[0].message.content
        return (content or "").strip()
    except Exception:
        _log.error("chat_with_report failed:\n%s", traceback.format_exc())
        return None


def chat_with_report_stream(
    messages: List[Dict[str, str]],
    findings: List[Dict[str, Any]],
):
    """
    带报告上下文的流式对话，返回 generator，每次 yield 一个文本 chunk。
    """
    client = _get_client()
    if not client or not LLM_API_KEY:
        return

    if findings:
        vuln_lines = []
        for i, f in enumerate(findings[:30]):
            verdict = f.get("llm_verdict", "")
            verdict_str = {"true_positive": "✅真漏洞", "false_positive": "❌误报", "needs_review": "⚠️待确认"}.get(verdict, "")
            flow = " -> ".join(f"L{s.get('line')}" for s in (f.get("code_flow") or [])[:4])
            vuln_lines.append(
                f"[{i}] {f.get('severity','')} | {f.get('vuln_name','')} | "
                f"{f.get('file','')}:{f.get('line',0)} {verdict_str}\n"
                f"    代码: {(f.get('snippet') or '')[:80]}\n"
                f"    路径: {flow}"
            )
        report_ctx = "当前报告共 {} 条漏洞：\n\n{}".format(len(findings), "\n\n".join(vuln_lines))
    else:
        report_ctx = "当前报告未发现漏洞。"

    system = (
        "你是 DeepSeek，扮演「马医生」这个代码安全分析角色。用户正在查看一份扫描报告，你已掌握完整漏洞列表。\n\n"
        + report_ctx
        + "\n\n用户可以问你：某条漏洞怎么修、是否误报、攻击者如何利用、整体风险评估等。"
        "回答要具体，引用漏洞编号 [N] 和代码位置。用中文回复。"
    )

    api_messages = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m.get("content", "")} for m in messages
    ]
    try:
        stream = client.chat.completions.create(
            model=LLM_MODEL,
            messages=api_messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and getattr(delta, "content", None):
                yield delta.content
    except Exception:
        _log.error("chat_with_report_stream failed:\n%s", traceback.format_exc())
        return


# ============================================================
# 规则生成与优化模块（基于 GitHub yasa-rule-optimizer 4 阶段管道思路）
# ============================================================

# YASA 规则 JSON Schema，注入 prompt 供 LLM 生成时参考
_RULE_SCHEMA_BRIEF = """{
  "checkerIds": ["<taint_flow checkers>"],
  "sources": {
    "FuncCallReturnValueTaintSource": [
      {"fsig": "<func>", "values": ["0"], "scopeFile": "all", "scopeFunc": "all"}
    ],
    "FuncCallArgTaintSource": [
      {"fsig": "<func>", "args": ["*"], "scopeFile": "all", "scopeFunc": "all"}
    ],
    "TaintSource": [
      {"path": "<variable or field>", "scopeFile": "all", "scopeFunc": "all"}
    ]
  },
  "sinks": {
    "FuncCallTaintSink": [
      {"args": ["<arg index or *>"], "attribute": "<VulnType>", "fsig": "<func signature>",
       "fregex": "<optional regex for complex call patterns>"}
    ]
  },
  "sanitizers": []
}"""

# 各语言默认 checkerIds 提示
_LANG_CHECKER_HINTS = {
    "python": "taint_flow_python_input, taint_flow_python_input_inner, taint_flow_python_django_input",
    "java": "taint_flow_java_input, taint_flow_java_input_inner, taint_flow_spring_input",
    "go": "taint_flow_go_input",
    "js": "taint_flow_js_input, taint_flow_express_input, taint_flow_egg_input",
    "php": "taint_flow_php_input",
    "c": "taint_flow_c_input",
}


def _build_rule_generation_prompt(lang: str) -> str:
    """构建规则生成的 system prompt"""
    hint = _LANG_CHECKER_HINTS.get(lang.lower(), "taint_flow_python_input")
    return (
        "你是 YASA 静态分析引擎的规则专家。根据用户提供的漏洞案例，生成一条精确的污点追踪规则。\n\n"
        f"## 规则输出格式（必须严格遵守）\n"
        f"```json\n{_RULE_SCHEMA_BRIEF}\n```\n\n"
        "## 字段说明\n"
        "- checkerIds: 污点流 checker 数组，**必须从以下列表选择**，不要自创\n"
        f"  {hint}\n"
        "- sources: 污点来源（不可信数据入口）\n"
        "  - FuncCallReturnValueTaintSource: 函数返回值作为污点。fsig=函数名, values=[\"0\"]表示返回值\n"
        "  - FuncCallArgTaintSource: 函数参数被污染。args=[\"*\"]表示所有参数\n"
        "  - TaintSource: 变量/字段直接作为污点源。path=变量名\n"
        "- sinks: 危险操作（污点汇聚点）\n"
        "  - args: 第几个参数是危险的（\"0\"=第一个, \"*\"=所有）\n"
        "  - attribute: 漏洞类型标识，参考现有命名: PythonSqlInjection/PythonCommandExec/PythonSSRF/"
        "PythonCodeExec/PythonPathTraversal/PythonDeserialize/PythonXxe/PythonOpenRedirect 等\n"
        "  - fsig: 精确函数签名匹配\n"
        "  - fregex: 正则匹配（用于复杂调用模式，如链式调用）\n"
        "- sanitizers: 净化函数列表，可为空数组\n\n"
        "## 重要原则\n"
        "1. **优先语义精度的 source/sink 匹配**，避免过于宽泛导致大量误报\n"
        "2. scopeFile 和 scopeFunc 默认填 \"all\"，除非明确知道限定范围\n"
        "3. 每个 source 只描述一个具体入口函数，不要合并\n"
        "4. 每个 sink 的 attribute 必须准确描述漏洞类型\n"
        "5. **只输出 JSON 数组**，不要 markdown 代码块，不要任何解释性文字\n"
        "6. **fsig 必须只写函数名，不包含参数部分**（如 \"os.system\" 而非 \"os.system(command)\"）"
    )


def generate_rule_from_case(
    vuln_description: str,
    lang: str = "python",
    code_snippet: str = "",
    reference_rules: str = "",
) -> Optional[List[Dict[str, Any]]]:
    """
    根据漏洞案例生成 YASA 污点追踪规则。
    vuln_description: 漏洞描述（类型、source/sink 模式、触发条件）
    lang: 目标语言
    code_snippet: 相关代码片段（可选，帮助 LLM 识别精确的函数签名）
    reference_rules: 参考规则示例（可选，注入到 prompt 供 LLM 学习）
    返回规则列表（可直接写入 rule_config_xxx.json），失败返回 None。
    """
    if not LLM_API_KEY:
        return None

    system = _build_rule_generation_prompt(lang)

    parts = [f"## 漏洞描述\n{vuln_description}"]
    if code_snippet:
        parts.append(f"\n## 相关代码\n```{lang}\n{code_snippet}\n```")
    if reference_rules:
        parts.append(f"\n## 参考规则示例（格式参考）\n```json\n{reference_rules}\n```")
    parts.append(
        "\n## 要求\n"
        "请生成规则 JSON。注意：\n"
        "- fsig 只写函数名，不写参数\n"
        "- checkerIds 必须使用上方指定的值\n"
        "- 只输出纯 JSON 数组，不要 markdown"
    )
    user = "\n".join(parts)

    result = call_llm(system, user)
    if not result:
        return None

    try:
        m = re.search(r"\[[\s\S]*\]", result)
        if not m:
            _log.error("generate_rule_from_case: no JSON array found in result")
            return None
        rules = json.loads(m.group())
        if not isinstance(rules, list):
            return None
        # 基本校验每条规则的结构
        for r in rules:
            if not isinstance(r, dict):
                return None
            if "checkerIds" not in r and "sinks" not in r:
                return None
        return rules
    except json.JSONDecodeError:
        _log.error("generate_rule_from_case: JSON parse failed:\n%s", traceback.format_exc())
        return None
    except Exception:
        _log.error("generate_rule_from_case failed:\n%s", traceback.format_exc())
        return None


def analyze_rule_quality(
    rule: Dict[str, Any],
    scan_findings: List[Dict[str, Any]],
    false_positives=None,
    false_negatives=None,
    evaluation: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    分析扫描结果的误报/漏报，给出改进方向（对应论文 Stage 3 LLM-3）。
    rule: 当前使用的规则 JSON
    scan_findings: 扫描找出的漏洞列表
    false_positives: 用户标记为误报的漏洞摘要（可选）
    false_negatives: 用户标记为漏报的漏洞摘要（可选）
    evaluation: rule_evaluator 返回的评估结果（含 TP/FP/FN/precision/recall/f1）
    返回 {"issues": [...], "recommendation": str}，失败返回 None。
    """
    if not LLM_API_KEY:
        return None

    # 优先使用真实 YASA 扫描评估结果
    eval_text = ""
    if evaluation and evaluation.get("success"):
        eval_text = (
            f"## 真实扫描评估\n"
            f"- TP（正确检出）: {evaluation['tp']}\n"
            f"- FP（误报）: {evaluation['fp']}\n"
            f"- FN（漏报）: {evaluation['fn']}\n"
            f"- Precision: {evaluation['precision']}\n"
            f"- Recall: {evaluation['recall']}\n"
            f"- F1: {evaluation['f1']}\n"
            f"- 扫描耗时: {evaluation.get('scan_time', '?')}s\n"
        )
        # 附上具体的 FP/FN 详情，帮助 LLM 精准定位
        if evaluation.get("unmatched"):
            eval_text += "\n## 误报详情（扫描发现但不在预期中）\n"
            for item in evaluation["unmatched"][:5]:
                f = item.get("finding", {})
                eval_text += f"- [{f.get('vuln_name', '?')}] {f.get('file', '')}:{f.get('line', 0)} — {item.get('reason', '')}\n"
        if evaluation.get("missed"):
            eval_text += "\n## 漏报详情（预期但未扫描到）\n"
            for item in evaluation["missed"][:5]:
                e = item.get("expected", {})
                eval_text += f"- {e.get('vuln_type', '?')} @ {e.get('file', '?')} — {item.get('reason', '')}\n"

    fp_text = ""
    fn_text = ""
    if false_positives:
        fp_text = "## 已确认误报\n" + "\n".join(f"- {x}" for x in false_positives)
    if false_negatives:
        fn_text = "## 已确认漏报\n" + "\n".join(f"- {x}" for x in false_negatives)

    if not fp_text and not fn_text and not eval_text:
        summary = f"规则扫描到 {len(scan_findings)} 个潜在漏洞。"
        fp_text = "## 扫描结果概述\n" + "\n".join(
            f"- [{f.get('severity', '?')}] {f.get('vuln_name', '')} @ {f.get('file', '')}:{f.get('line', 0)}"
            for f in scan_findings[:15]
        )
        eval_text = summary + "\n\n" + fp_text

    system = """你是 YASA 静态分析规则优化专家。根据真实扫描评估数据（TP/FP/FN/Precision/Recall），分析当前规则的问题并给出精准改进方案。

关注点：
- source/sink 的 fsig 是否过于宽泛？是否匹配到了不应匹配的函数？
- 是否需要增加 sanitizer 排除安全路径？
- sink 的 attribute 是否正确归类？
- 是否有遗漏的 source 入口导致漏报？
- 根据 FP/FN 详情，哪些具体函数签名需要调整？

只输出一个 JSON 对象，不要 markdown：
{"issues":[{"problem":"具体问题","severity":"高|中|低","suggestion":"改进方案"}],"recommendation":"总体优化方向（1-2句）"}"""

    user = (
        f"## 当前规则\n```json\n{json.dumps(rule, ensure_ascii=False, indent=2)}\n```\n\n"
        f"{eval_text}\n\n{fp_text}\n\n{fn_text}\n\n"
        "请根据以上真实评估数据，分析规则质量，给出改进建议。"
    )

    result = call_llm(system, user)
    if not result:
        return None

    try:
        m = re.search(r"\{[\s\S]*\}", result)
        if not m:
            return None
        obj = json.loads(m.group())
        return {
            "issues": obj.get("issues", []),
            "recommendation": str(obj.get("recommendation", "")).strip(),
        }
    except Exception:
        _log.error("analyze_rule_quality failed:\n%s", traceback.format_exc())
        return None


def optimize_rule(
    rule: Dict[str, Any],
    quality_report: Dict[str, Any],
    lang: str = "python",
) -> Optional[List[Dict[str, Any]]]:
    """
    根据质量分析结果优化规则（对应 GitHub 管道 LLM-4）。
    rule: 当前规则
    quality_report: analyze_rule_quality 的输出
    lang: 目标语言
    返回优化后的规则列表，失败返回 None。
    """
    if not LLM_API_KEY:
        return None

    system = _build_rule_generation_prompt(lang) + "\n\n你现在的任务是**优化**一条已有规则，而不是从零生成。"

    recommendations = json.dumps(quality_report.get("issues", []), ensure_ascii=False, indent=2)
    overall = quality_report.get("recommendation", "")

    user = (
        f"## 当前规则（需要优化）\n```json\n{json.dumps(rule, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## 质量分析发现的问题\n{recommendations}\n\n"
        f"## 总体优化方向\n{overall}\n\n"
        "请输出优化后的完整规则 JSON 数组。只输出 JSON，不要 markdown。"
    )

    result = call_llm(system, user)
    if not result:
        return None

    try:
        m = re.search(r"\[[\s\S]*\]", result)
        if not m:
            return None
        rules = json.loads(m.group())
        if not isinstance(rules, list):
            return None
        return rules
    except Exception:
        _log.error("optimize_rule failed:\n%s", traceback.format_exc())
        return None


def run_rule_pipeline(
    vuln_description: str,
    lang: str = "python",
    code_snippet: str = "",
    reference_rules: str = "",
    max_iterations: int = 2,
    on_progress=None,
) -> Optional[Dict[str, Any]]:
    """
    完整的规则生成→验证→优化管道。
    max_iterations: 最大迭代次数（默认 2，对应 LLM-1 到 LLM-4 的最小闭环）
    on_progress: 进度回调 on_progress(stage, message)
    返回 {"final_rule": [...], "iterations": [...], "summary": str}
    """
    if not LLM_API_KEY:
        return None

    stages = []
    current_rule = None
    final_rule = None

    # Stage 1+2: 首次生成规则
    if on_progress:
        on_progress("generate", "根据漏洞描述生成初始规则...")
    current_rule = generate_rule_from_case(vuln_description, lang, code_snippet, reference_rules)
    if not current_rule:
        if on_progress:
            on_progress("failed", "规则生成失败")
        return None
    stages.append({"stage": "generate", "status": "ok", "rule": current_rule})

    # Stage 3+4 迭代
    for i in range(max_iterations):
        if on_progress:
            on_progress("optimize", f"优化迭代 {i + 1}/{max_iterations}...")

        # 用规则做一次轻量评估（只分析规则本身，不实际扫描）
        quality = analyze_rule_quality(
            current_rule[0] if isinstance(current_rule, list) else current_rule,
            [],
        )
        if not quality or not quality.get("issues"):
            stages.append({"stage": f"optimize_{i + 1}", "status": "no_issues_found"})
            break

        optimized = optimize_rule(
            current_rule[0] if isinstance(current_rule, list) else current_rule,
            quality,
            lang,
        )
        if not optimized:
            stages.append({"stage": f"optimize_{i + 1}", "status": "optimize_failed"})
            break

        stages.append({
            "stage": f"optimize_{i + 1}",
            "status": "ok",
            "rule": optimized,
            "issues": quality.get("issues", []),
            "recommendation": quality.get("recommendation", ""),
        })
        current_rule = optimized

    final_rule = current_rule

    if on_progress:
        on_progress("done", f"管道完成，共 {len(stages)} 个阶段")

    return {
        "final_rule": final_rule,
        "iterations": stages,
        "summary": (
            f"规则生成完成：{len(stages)} 个阶段，"
            f"最终规则包含 {len(final_rule)} 条 checker"
            if isinstance(final_rule, list)
            else "管道执行异常"
        ),
    }
