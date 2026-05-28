# -*- coding: utf-8 -*-
"""Agent 模块：手写 tool calling 循环，支持深度思考模式"""

from typing import Optional

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

SYSTEM_PROMPT = """你是一个代码安全分析助手。回答要求：简洁、准确、直接。

## 场景决策表（收到用户请求后，按此表决定工具调用顺序）

### 规则生成场景（最重要，严格按此执行）

| 用户输入特征 | 工具调用顺序 | 说明 |
|-------------|-------------|------|
| 提到具体 CVE ID + 要生成规则 | ① enrich_cve → ② build_rule_from_cve | 一步完成 CVE情报→规则生成→入库。绝对不要用 generate_rule |
| 提到具体 CVE ID + 只问情报 | enrich_cve | 返回 CVSS、EPSS、KEV 状态、风险评分 |
| 想检测某类漏洞，无具体 CVE | ① search_cve → ② 展示结果让用户选 → ③ build_rules_from_cves | 先搜再确认再生成 |
| 手写描述漏洞模式，无 CVE ID | generate_rule | 仅在用户自行描述 source/sink 且无任何 CVE 时使用 |
| 优化已有规则 | optimize_rule | 需要之前已调用过 generate_rule |
| 多个 CVE 要排序优先级 | prioritize_cves | 按 CVSS×EPSS×KEV 排序 |

### 扫描场景

| 用户输入特征 | 工具调用顺序 | 说明 |
|-------------|-------------|------|
| 要扫描某个项目 | scan_project | 必须先确认 scan_path，无路径主动问 |
| 提供仓库 URL + 要分析安全 | ① git_clone → ② git_log → ③ scan_project | 克隆后扫描 |
| 查看扫描报告 | get_scan_report / list_scan_reports / get_report_by_index | 按需选择 |
| 收藏报告 | favorite_last_report | 用户说「收藏」时 |

### 搜索场景

| 用户输入特征 | 工具调用顺序 | 说明 |
|-------------|-------------|------|
| 查某个包/依赖的漏洞 | query_osv | 提供包名、版本、生态 |
| 检查 CVE 是否正被利用 | check_kev | 快速 CISA KEV 查 |
| 搜索 NVD（非开源软件） | search_nvd | 比 search_cve 覆盖更广 |
| 搜开源项目/GitHub 代码 | github_search | 仓库用 repositories，代码用 code |
| 搜网页/技术文档 | web_search | 通用搜索 |
| Git 仓库提交/diff 分析 | git_log / git_show / git_diff | 用于分析代码变更找漏洞 |

## 关键规则（必须遵守）

1. **CVE ID + 规则 → enrich_cve + build_rule_from_cve**。这是最重要的规则。看到 CVE-YYYY-NNNNN 且用户想要规则时，绝对不要跳到 generate_rule。
2. **generate_rule 仅用于无 CVE 的手写描述**。它只有单次 LLM 调用，质量远不如 build_rule_from_cve 的 4 阶段流水线。
3. **扫描前必须确认路径**。用户没说 scan_path 就主动问，给出具体路径选项。
4. **能搜就搜**。任何涉及外部知识（项目、工具、漏洞）的问题，先调对应搜索工具，不凭训练数据回答。
5. **不确定就确认**。用户输入模糊时，列出选项让用户选，不要猜测。

## 已知项目信息（无需搜索，直接使用）
- YASA = 蚂蚁集团（antgroup）开源的静态分析引擎，GitHub: antgroup/YASA-Engine
- 核心创新：UAST（统一抽象语法树），将 Python/Java/Go/JS/PHP/C 源码统一转为中间表示后分析
- 本系统集成了 YASA 引擎做污点追踪（数据流漏洞），同时集成 Semgrep 做模式匹配
- 规则文件位于 rules/rule_config_{lang}_{mode}.json，支持 minimal 和 full 两种模式
- 每个用户可以拥有自己的规则库（在规则工坊页面管理），扫描时可选择官方规则库或个人规则库

## 输出要求
- 先说结论，再说细节
- 不用比喻、拟人、故事化表达
- 不废话，信息密度高
"""  # noqa: E501


def _langchain_tools_to_openai(tools: list) -> list[dict]:
    """将 LangChain StructuredTool 列表转为 OpenAI function calling 格式"""
    result = []
    for t in tools:
        params = {"type": "object", "properties": {}, "required": []}
        if hasattr(t, "args_schema") and t.args_schema:
            schema = t.args_schema.model_json_schema()
            params["properties"] = schema.get("properties", {})
            if "required" in schema:
                params["required"] = schema["required"]
        result.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": params,
            },
        })
    return result


def _call_tool_by_name(name: str, args: dict, tools: list) -> str:
    """根据工具名调用对应的 LangChain 工具"""
    for t in tools:
        if t.name == name:
            return str(t.invoke(args))
    return f"错误：未找到工具 {name}"


def _build_openai_messages(chat_history: list, user_input: str) -> list[dict]:
    """构建 OpenAI 格式的消息列表"""
    from datetime import datetime; today = datetime.now().strftime("%Y年%m月%d日 %A"); messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\n\n当前日期：{today}"}]
    if chat_history:
        for m in chat_history:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_input})
    return messages


def _should_force_search(user_input: str) -> str | None:
    """检测用户输入是否属于必须搜索的类型，返回搜索提示或 None"""
    import re as _re
    text = user_input.lower()
    patterns = [
        (r"cve-\d{4}-\d+.*(?:规则|rule|生成|检测规则|build.?rule|generate.?rule|创建规则)",
         "CVE规则生成 → 先用 enrich_cve 获取漏洞情报，再用 build_rule_from_cve 一键生成检测规则"),
        (r"https?://(?:github|gitlab)\.com/\S+",
         "仓库URL → 用 git_clone 克隆仓库，然后 git_log 查看提交历史，最后 scan_project 扫描"),
        (r"(?:包|依赖|package|dependency|library).*(?:漏洞|vuln|安全|检查|查询)",
         "依赖漏洞 → 用 query_osv 查询包的已知漏洞"),
        (r"最新|cve|漏洞情报|最近.*漏洞|近期.*漏洞",
         "news/vuln → 用 web_search 搜索最新漏洞情报"),
        (r"github.*项目|开源.*仓库|github.*repo|代码.*搜索",
         "github → 用 github_search"),
        (r"介绍一下|分析.*工具|是什么|怎么用|原理|架构",
         "tech/tool → 先用 github_search 搜官方仓库"),
        (r"cve-\d{4}-\d+.*(?:poc|exploit|利用代码|漏洞利用|复现|proof.of.concept)",
         "CVE/PoC → 用 github_search search_type=code 搜 PoC 代码"),
    ]
    hints = []
    for pattern, hint in patterns:
        if _re.search(pattern, text, _re.IGNORECASE):
            hints.append(hint)
    return "；".join(hints) if hints else None


def _make_step_summary(result_text: str) -> str:
    """根据工具返回文本生成简短摘要"""
    import re as _re
    if "搜索「" in result_text and "」的结果" in result_text:
        count = len(_re.findall(r"\d+\.\s", result_text))
        return f"找到 {count} 条网页结果"
    if "GitHub" in result_text and "搜索" in result_text:
        count_m = _re.search(r"共 (\d+) 个", result_text)
        count = count_m.group(1) if count_m else "?"
        return f"找到 {count} 个 GitHub 结果"
    if "扫描完成" in result_text:
        return "扫描完成"
    if "扫描失败" in result_text:
        return "扫描失败"
    return result_text[:60] + ("..." if len(result_text) > 60 else "")


def _extract_search_sources(tool_messages: list) -> list[dict]:
    """从工具消息中提取搜索链接"""
    import re as _re
    sources = []
    for msg in tool_messages:
        content = str(msg.get("content", "")) if isinstance(msg, dict) else str(msg)
        if "搜索「" in content and "」的结果" in content:
            for m in _re.finditer(r"\d+\.\s*(.+?)\n\s+(https?://[^\s]+)", content):
                title = m.group(1).strip()
                url = m.group(2).strip()
                dm = _re.search(r"https?://([^/]+)", url)
                sources.append({"title": title, "url": url, "domain": dm.group(1) if dm else ""})
        elif "GitHub" in content and "搜索" in content:
            for m in _re.finditer(r"\d+\.\s*(.+?)\n\s+(https://github\.com/[^\s]+)", content):
                title = m.group(1).strip()
                url = m.group(2).strip()
                dm = _re.search(r"github\.com/([^/]+/[^/\s]+)", url)
                sources.append({"title": title, "url": url, "domain": dm.group(1) if dm else "github.com"})
    return sources


def create_agent(deep_thinking: bool = False):
    """创建 Agent 上下文。返回 {"client": OpenAI, "tools": list, "deep_thinking": bool}"""
    if not LLM_API_KEY:
        return None
    try:
        from openai import OpenAI
        import httpx
        from agent_tools import create_tools_for_langchain

        tools = create_tools_for_langchain()
        http_client = httpx.Client(proxy=None)
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            http_client=http_client,
        )
        return {"client": client, "tools": tools, "deep_thinking": deep_thinking}
    except Exception:
        return None


def agent_invoke_stream(agent_ctx: dict, user_input: str, chat_history: Optional[list] = None):
    """
    流式版 Agent：用 OpenAI streaming API，实时产出推理内容、工具调用和最终回复。
    每次 yield 一个 dict: {"type": "reasoning"|"tool_call"|"tool_result"|"reply"|"done", ...}
    """
    import json as _json

    if not agent_ctx:
        yield {"type": "done", "reply": "Agent 初始化失败，请检查 API 配置。", "sources": [], "steps": []}
        return

    client = agent_ctx["client"]
    tools = agent_ctx["tools"]
    deep_thinking = agent_ctx["deep_thinking"]

    try:
        search_hint = _should_force_search(user_input)
        if search_hint:
            user_input = f"[系统指令：本问题涉及 {search_hint}。必须先调用对应工具搜索，绝对不要凭训练数据作答。]\n\n用户问题：{user_input}"

        messages = _build_openai_messages(chat_history or [], user_input)
        oai_tools = _langchain_tools_to_openai(tools)
        reasoning_cache = None
        steps = []
        tool_call_msgs = []

        for _iteration in range(8):
            kwargs = {
                "model": LLM_MODEL,
                "messages": messages,
                "temperature": 0.1,
                "tools": oai_tools,
                "stream": True,
                "extra_body": {"thinking": {"type": "enabled"}} if deep_thinking else {"thinking": {"type": "disabled"}},
            }
            if reasoning_cache:
                for m in reversed(messages):
                    if m.get("role") == "assistant":
                        m["reasoning_content"] = reasoning_cache
                        break

            stream = client.chat.completions.create(**kwargs)

            # 收集本次调用的所有 chunk
            tool_call_buf: dict[str, dict] = {}  # index -> {id, name, args_str}
            reasoning_text = ""
            content_text = ""

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # reasoning_content 实时流出
                rc = getattr(delta, "reasoning_content", None)
                if rc:
                    reasoning_text += rc
                    yield {"type": "reasoning", "text": rc}

                # 工具调用 delta
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_buf:
                            tool_call_buf[idx] = {"id": "", "name": "", "args_str": ""}
                        if tc_delta.id:
                            tool_call_buf[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_call_buf[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_call_buf[idx]["args_str"] += tc_delta.function.arguments

                # 普通内容
                c = getattr(delta, "content", None)
                if c:
                    content_text += c

            # 缓存 reasoning
            if reasoning_text:
                reasoning_cache = reasoning_text

            if tool_call_buf:
                # 有工具调用
                assistant_msg: dict = {"role": "assistant", "content": content_text}
                if reasoning_cache:
                    assistant_msg["reasoning_content"] = reasoning_cache

                tc_list = []
                for idx in sorted(tool_call_buf.keys()):
                    tc = tool_call_buf[idx]
                    try:
                        args = _json.loads(tc["args_str"])
                    except Exception:
                        args = {}
                    tc_list.append({
                        "id": tc["id"], "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["args_str"]},
                    })
                    desc = f"调用 {tc['name']}"
                    if tc["name"] == "web_search":
                        desc = f"搜索网页：{args.get('query', '')[:60]}"
                    elif tc["name"] == "github_search":
                        desc = f"搜索 GitHub {args.get('search_type', 'repositories')}：{args.get('query', '')[:60]}"
                    step = {"type": "tool_call", "tool": tc["name"], "desc": desc}
                    steps.append(step)
                    yield {"type": "tool_call", "tool": tc["name"], "desc": desc}

                assistant_msg["tool_calls"] = tc_list
                messages.append(assistant_msg)

                for idx in sorted(tool_call_buf.keys()):
                    tc = tool_call_buf[idx]
                    try:
                        args = _json.loads(tc["args_str"])
                    except Exception:
                        args = {}
                    result_text = _call_tool_by_name(tc["name"], args, tools)
                    tool_msg = {"role": "tool", "tool_call_id": tc["id"], "content": result_text}
                    messages.append(tool_msg)
                    tool_call_msgs.append(tool_msg)
                    summary = _make_step_summary(result_text)
                    steps.append({"type": "tool_result", "desc": summary})
                    yield {"type": "tool_result", "desc": summary}
            else:
                # 最终回复
                sources = _extract_search_sources(tool_call_msgs)
                yield {"type": "done", "reply": content_text.strip(), "sources": sources, "steps": steps}
                return

        yield {"type": "done", "reply": "Agent 达到最大迭代次数，请简化问题重试。", "sources": [], "steps": steps}
    except Exception as e:
        yield {"type": "done", "reply": "Agent 调用失败，请稍后重试", "sources": [], "steps": []}


def agent_invoke(agent_ctx: dict, user_input: str, chat_history: Optional[list] = None) -> dict:
    """
    调用 Agent，返回 {"reply": str, "sources": list, "steps": list}
    手写 tool calling 循环，正确处理 reasoning_content 的缓存和回传。
    """
    if not agent_ctx:
        return {"reply": "Agent 初始化失败，请检查 API 配置。", "sources": [], "steps": []}

    client = agent_ctx["client"]
    tools = agent_ctx["tools"]
    deep_thinking = agent_ctx["deep_thinking"]

    try:
        # 强制搜索
        search_hint = _should_force_search(user_input)
        if search_hint:
            user_input = f"[系统指令：本问题涉及 {search_hint}。必须先调用对应工具搜索，绝对不要凭训练数据作答。]\n\n用户问题：{user_input}"

        messages = _build_openai_messages(chat_history or [], user_input)
        oai_tools = _langchain_tools_to_openai(tools)
        reasoning_cache = None
        reasoning_chunks = []  # 收集所有 reasoning_content
        steps = []
        tool_call_msgs = []

        for _iteration in range(8):
            kwargs = {
                "model": LLM_MODEL,
                "messages": messages,
                "temperature": 0.1,
                "tools": oai_tools,
                "extra_body": {"thinking": {"type": "enabled"}} if deep_thinking else {"thinking": {"type": "disabled"}},
            }

            # 回注缓存的 reasoning_content
            if reasoning_cache:
                for m in reversed(messages):
                    if m.get("role") == "assistant":
                        m["reasoning_content"] = reasoning_cache
                        break

            resp = client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message

            # 缓存本次 reasoning_content，并收集展示用
            rc = getattr(msg, "reasoning_content", None)
            if rc:
                reasoning_cache = rc
                reasoning_chunks.append(rc)

            if msg.tool_calls:
                assistant_msg = {"role": "assistant", "content": msg.content or ""}
                if reasoning_cache:
                    assistant_msg["reasoning_content"] = reasoning_cache

                tc_list = []
                for tc in msg.tool_calls:
                    try:
                        import json as _json
                        args = _json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    tc_list.append({
                        "id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    })
                    desc = f"调用 {tc.function.name}"
                    if tc.function.name == "web_search":
                        desc = f"搜索网页：{args.get('query', '')[:60]}"
                    elif tc.function.name == "github_search":
                        desc = f"搜索 GitHub {args.get('search_type', 'repositories')}：{args.get('query', '')[:60]}"
                    elif tc.function.name == "scan_project":
                        desc = f"扫描 {args.get('scan_path', '')} [{args.get('engine', 'yasa')}/{args.get('language', '')}]"
                    steps.append({"type": "tool_call", "tool": tc.function.name, "desc": desc})

                assistant_msg["tool_calls"] = tc_list
                messages.append(assistant_msg)

                for tc in msg.tool_calls:
                    try:
                        import json as _json
                        args = _json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    result_text = _call_tool_by_name(tc.function.name, args, tools)
                    tool_msg = {"role": "tool", "tool_call_id": tc.id, "content": result_text}
                    messages.append(tool_msg)
                    tool_call_msgs.append(tool_msg)
                    steps.append({"type": "tool_result", "desc": _make_step_summary(result_text)})
            else:
                reply = msg.content or ""
                sources = _extract_search_sources(tool_call_msgs)
                return {"reply": reply.strip(), "sources": sources, "steps": steps, "reasoning": reasoning_chunks}

        return {"reply": "Agent 达到最大迭代次数，请简化问题重试。", "sources": [], "steps": steps, "reasoning": reasoning_chunks}
    except Exception as e:
        return {"reply": "Agent 调用失败，请稍后重试", "sources": [], "steps": [], "reasoning": []}
