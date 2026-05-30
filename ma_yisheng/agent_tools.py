# -*- coding: utf-8 -*-
"""Agent 工具定义：供 LangChain Agent 调用的扫描与报告能力"""

from pathlib import Path
from typing import Optional

import config
from scanner import detect_language, run_yasa_scan, run_semgrep_scan
from report import save_report, mark_as_favorite, is_favorite, list_reports, get_report_content

# 最近一次扫描结果，供 get_scan_report 使用
_last_scan_result: Optional[dict] = None

# 最近生成的规则，供 optimize_rule 复用
_last_generated_rules: dict = {}


def _set_last_scan(ok: bool, out: str, err: str, report_dir: str, scan_path: str, lang: str):
    global _last_scan_result
    _last_scan_result = {
        "ok": ok,
        "output": out or "",
        "error": err or "",
        "report_dir": report_dir or "",
        "scan_path": scan_path,
        "language": lang,
    }


def get_last_scan_result() -> Optional[dict]:
    return _last_scan_result


def set_last_scan_from_manual(ok: bool, out: str, err: str, report_dir: str, scan_path: str, lang: str):
    """手动扫描完成后调用，同步结果供 Agent 的 get_scan_report 使用"""
    _set_last_scan(ok, out, err, report_dir, scan_path, lang)


def _is_safe_scan_path(scan_path: str) -> bool:
    """只允许扫描 /home、/opt、/srv、/tmp 下的路径，拒绝系统目录"""
    try:
        p = Path(scan_path).resolve()
        allowed = [Path("/home").resolve(), Path("/opt").resolve(), Path("/srv").resolve(), Path("/tmp").resolve()]
        return any(p == a or str(p).startswith(str(a) + "/") for a in allowed)
    except Exception:
        return False


def tool_scan_project(
    scan_path: str,
    language: str = "python",
    mode: str = "minimal",
    engine: str = "yasa",
    favorite: bool = False,
) -> str:
    """
    对指定路径执行代码漏洞扫描。
    scan_path: 要扫描的项目路径（文件或目录）
    language: 编程语言，python/java/go/js/php/c
    mode: 扫描模式，minimal=精简快，full=全面慢（所有语言均支持）
    engine: 扫描引擎，yasa=污点分析（深 pero 慢），semgrep=模式匹配（快 pero 浅）。用户说「用 yasa 扫」「污点分析」时选 yasa，说「用 semgrep」「快速扫」时选 semgrep，不指定时默认 yasa。
    favorite: 是否收藏报告。True=永久保留，False=仅保留 1 天。用户说「收藏」「要收藏」「永久保存」时传 True
    """
    path = Path(scan_path)
    if not path.exists():
        return f"错误：路径不存在 {scan_path}"
    if not _is_safe_scan_path(scan_path):
        return f"错误：不允许扫描该路径 {scan_path}，只能扫描 /home、/opt、/srv、/tmp 下的目录"
    if language not in ("python", "java", "go", "js", "php", "c"):
        return f"错误：不支持的语言 {language}，请用 python/java/go/js/php/c"
    if engine not in ("yasa", "semgrep"):
        return f"错误：不支持的引擎 {engine}，请用 yasa 或 semgrep"

    timeout = None if config.SCAN_TIMEOUT <= 0 else config.SCAN_TIMEOUT

    if engine == "semgrep":
        ok, out, err, report_dir = run_semgrep_scan(scan_path, language, timeout=timeout, silent=True)
    else:
        ok, out, err, report_dir = run_yasa_scan(scan_path, language, mode, timeout=timeout, silent=True)

    if ok and report_dir:
        save_report(report_dir, scan_path, language, out or "")
        if favorite:
            mark_as_favorite(report_dir)
    _set_last_scan(ok, out or "", err or "", report_dir or "", scan_path, language)

    engine_label = "Semgrep" if engine == "semgrep" else "YASA"
    if ok:
        summary = (out or "")[:6000]
        fav_note = "（已收藏，报告永久保留）" if favorite else "（未收藏，仅保留 1 天。若要收藏请说「收藏本次报告」）"
        return f"[{engine_label}] 扫描完成{fav_note}。\n路径: {scan_path}\n语言: {language}\n模式: {mode}\n\n输出摘要:\n{summary}"
    return f"[{engine_label}] 扫描失败: {err or '未知错误'}"


def tool_favorite_last_report() -> str:
    """
    将最近一次扫描的报告标记为收藏，永久保留。
    用户说「收藏」「收藏本次报告」「要收藏」时调用。
    """
    r = get_last_scan_result()
    if not r or not r.get("report_dir"):
        return "没有可收藏的报告。请先执行扫描。"
    report_dir = r["report_dir"]
    if is_favorite(report_dir):
        return "该报告已收藏，无需重复操作。"
    if mark_as_favorite(report_dir):
        return "已收藏，报告将永久保留。"
    return "收藏失败，请重试。"


def tool_get_scan_report() -> str:
    """
    获取最近一次扫描的结果。若尚未执行过扫描，返回提示信息。
    用于回答「刚才扫出什么了」「扫描结果是什么」等问题。
    """
    r = get_last_scan_result()
    if not r:
        return "尚未执行过扫描。请先使用 scan_project 工具扫描项目。"
    if not r["ok"]:
        return f"上次扫描失败: {r['error']}"
    out = r["output"]
    if not out.strip():
        return "上次扫描完成但无输出内容。"
    return f"最近扫描路径: {r['scan_path']}\n语言: {r['language']}\n\nYASA 输出:\n{out[:6000]}"


def tool_list_reports(limit: int = 10, project_filter: str = "") -> str:
    """
    列出最近的扫描报告。
    limit: 最多返回数量，默认 10
    project_filter: 按项目名过滤，空则不过滤
    返回报告列表，用户可据此选择「查看第 N 个报告」。
    """
    import time
    items = list_reports(limit=limit, project_filter=project_filter)
    if not items:
        return "暂无扫描报告。请先执行扫描。"
    lines = []
    for i, r in enumerate(items, 1):
        mtime_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["mtime"]))
        fav = "★" if r["favorite"] else ""
        cnt = r.get("findings_count", 0)
        sev = r.get("severity", "无")
        summary = f"漏洞{cnt}个 {sev}" if cnt > 0 else "无漏洞"
        lines.append(f"{i}. {r['project']} | {mtime_str} | {r['language']} {fav} | {summary}\n   路径: {r['scan_path'] or r['report_name']}\n")
    return "最近扫描报告：\n\n" + "\n".join(lines) + "\n（说「查看第 N 个报告」可获取详情）"


def tool_get_report_content(report_index: int) -> str:
    """
    获取指定报告的内容。report_index 为 list_reports 返回列表中的序号（从 1 开始）。
    用户说「查看第 3 个报告」「第 2 个报告」时调用。
    """
    items = list_reports(limit=20)
    if not items:
        return "暂无报告。"
    if report_index < 1 or report_index > len(items):
        return f"索引无效。请使用 1 到 {len(items)} 之间的数字。"
    r = items[report_index - 1]
    content = get_report_content(r["path"])
    if not content:
        return f"无法读取报告：{r['path']}"
    return f"报告 [{r['project']}] {r['report_name']}:\n\n{content}"


def tool_web_search(query: str, max_results: int = 5) -> str:
    """
    Search web via Bing (cn.bing.com). Use when you need up-to-date information not in training data.
    """
    import re as _re
    import os
    import urllib.request, urllib.parse, ssl, random, time

    ctx = ssl.create_default_context()
    for attempt in range(2):
        try:
            ua = random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
            ])
            q = urllib.parse.quote(query)
            url = f"https://cn.bing.com/search?q={q}&count={max_results}"
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            })
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            if not html or len(html) < 1000:
                continue

            # Parse: h2>a = title, cite = URL
            title_links = _re.findall(
                r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html, _re.DOTALL
            )
            cites = _re.findall(r"<cite>([^<]+)</cite>", html)

            results = []
            seen = set()
            for i, (href, raw_title) in enumerate(title_links[:max_results]):
                title = _re.sub(r"<[^>]+>", "", raw_title).strip()
                url_clean = href
                # Try to get cleaner URL from cites
                if i < len(cites):
                    cite_url = _re.sub(r"<[^>]+>", "", cites[i]).strip().replace(" ", "")
                    if cite_url.startswith("http"):
                        url_clean = cite_url.split(" › ")[0] if " › " in cite_url else cite_url

                if url_clean in seen or not title:
                    continue
                seen.add(url_clean)
                results.append(f"- [{title[:200]}]({url_clean})")

            if results:
                return "\n".join(results)
            return f"Bing found no results for '{query}'"

        except Exception as e:
            if attempt < 1:
                time.sleep(2)
                continue
            return f"Search failed: {str(e)}"

    return "Search failed"

def tool_github_search(query: str, search_type: str = "repositories", max_results: int = 5) -> str:
    """
    搜索 GitHub 上的仓库、代码或议题。当用户想找某个开源项目、代码示例、漏洞 PoC 时调用。
    query: 搜索关键词（支持 GitHub 搜索语法，如 \"YASA static analysis\" \"CVE-2025 SQL\" \"lang:python\"）
    search_type: 搜索类型。repositories=仓库, code=代码, issues=议题
    max_results: 返回结果数量，默认5条
    """
    import json as _json
    import urllib.parse
    import os
    import urllib.request
    import ssl

    # 先尝试直连 GitHub API，超时设短（国内可能不稳）
    try:
        endpoint = {"repositories": "repositories", "code": "code", "issues": "issues"}.get(search_type, "repositories")
        q = urllib.parse.quote(query)
        url = f"https://api.github.com/search/{endpoint}?q={q}&sort=stars&per_page={max_results}"

        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MaYisheng-Scanner/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            data = _json.loads(resp.read().decode("utf-8", errors="replace"))

        items = data.get("items", [])
        if not items:
            return f"在 GitHub 上未找到关于「{query}」的{endpoint}结果。"

        results = []
        for r in items[:max_results]:
            full_name = r.get("full_name", r.get("repository", {}).get("full_name", ""))
            desc = (r.get("description") or "").strip()
            html_url = r.get("html_url", "")
            stars = r.get("stargazers_count", r.get("stargazers_count", 0))
            lang = r.get("language") or ""
            if not full_name and "repository" in r:
                full_name = r["repository"].get("full_name", "")
            name = full_name or r.get("name", "")
            path = r.get("path", "")

            line = f"{len(results) + 1}. {name}"
            if stars:
                line += f" ⭐{stars}"
            if lang:
                line += f" | {lang}"
            if path:
                line += f" | {path}"
            line += f"\n   {html_url}"
            if desc:
                line += f"\n   {desc[:300]}"
            results.append(line)

        type_label = {"repositories": "仓库", "code": "代码", "issues": "议题"}.get(search_type, "仓库")
        return f"GitHub {type_label}搜索「{query}」的结果（共 {data.get('total_count', 0)} 个）：\n\n" + "\n\n".join(results)

    except Exception:
        # GitHub API 不通，降级为搜狗 site:github.com 搜索
        pass

    # 降级：用搜狗搜索 GitHub
    try:
        fallback_q = f"site:github.com {query}"
        fallback_result = tool_web_search(fallback_q, max_results=max_results)
        if "搜索失败" in fallback_result or "未找到" in fallback_result:
            return f"GitHub API 不可达，site:github.com 降级搜索也未找到结果。请稍后重试。"
        return "（GitHub API 不可达，已降级为网页搜索）\n\n" + fallback_result
    except Exception:
        return "GitHub 搜索失败: API 不可达且降级搜索也失败，请稍后重试"


def tool_generate_rule(
    vuln_description: str,
    language: str = "python",
    code_snippet: str = "",
    save_to_rules: bool = False,
    rule_name: str = "",
) -> str:
    """
    根据漏洞描述生成 YASA 污点追踪规则。
    vuln_description: 漏洞详细描述，包括漏洞类型、source 入口函数、sink 危险函数、触发条件等
    language: 目标编程语言，python/java/go/js/php/c
    code_snippet: 相关代码片段（选填，帮助精确识别函数签名）
    save_to_rules: 是否保存到 rules 目录。用户说「保存」「加到规则库」时传 True
    rule_name: 保存时使用的规则文件名（不含路径和扩展名），例如 my_ssrf_rule
    返回生成的规则 JSON。
    """
    if language not in ("python", "java", "go", "js", "php", "c"):
        return f"错误：不支持的语言 {language}，请用 python/java/go/js/php/c"

    import json as _json
    from llm import generate_rule_from_case

    try:
        rules = generate_rule_from_case(
            vuln_description=vuln_description,
            lang=language,
            code_snippet=code_snippet,
        )
    except Exception as e:
        return f"规则生成失败: {str(e)}"

    if not rules:
        return "规则生成失败：LLM 未能生成有效规则，请补充更多漏洞细节后重试。"

    rules_json = _json.dumps(rules, ensure_ascii=False, indent=2)

    msg_parts = [f"✅ 成功生成 {len(rules)} 条规则：\n\n```json\n{rules_json}\n```"]

    if save_to_rules:
        name = (rule_name or "generated").strip().replace(" ", "_").replace("/", "_")
        fname = f"rule_config_{language}_{name}.json"
        target = Path(__file__).resolve().parent / "rules" / fname
        try:
            with open(target, "w", encoding="utf-8") as f:
                _json.dump(rules, f, ensure_ascii=False, indent=2)
            msg_parts.append(f"\n📁 已保存到 rules/{fname}")
        except Exception as e:
            msg_parts.append(f"\n⚠️ 保存失败: {str(e)}")

    msg_parts.append(
        "\n💡 提示：可以用新规则扫描项目，执行 scan_project 即可。"
        "也可以说「帮我优化这条规则」进入优化流程。"
    )
    return "\n".join(msg_parts)


def tool_optimize_rule(
    rule_index: int = 0,
    feedback: str = "",
    language: str = "python",
) -> str:
    """
    根据用户反馈优化最近生成的规则。
    rule_index: 要优化的规则索引（从 0 开始，默认优化第一条）
    feedback: 用户反馈，如「这个规则误报太多」「没扫出某类漏洞」「source 太宽泛了」
    language: 目标语言
    返回优化后的规则。
    """
    if language not in ("python", "java", "go", "js", "php", "c"):
        return f"错误：不支持的语言 {language}"

    import json as _json
    from llm import optimize_rule

    # 复用最近生成的规则（保存在模块级变量中）
    rule = _last_generated_rules.get(language)
    if not rule:
        return "没有可优化的规则。请先使用 generate_rule 生成一条规则。"
    if isinstance(rule, list) and rule_index >= 0:
        if rule_index >= len(rule):
            return f"规则索引 {rule_index} 越界，当前只有 {len(rule)} 条规则"
        target = rule[rule_index]
    else:
        target = rule if isinstance(rule, dict) else rule[0]

    quality = {
        "issues": [{"problem": "用户反馈", "severity": "高", "suggestion": feedback}],
        "recommendation": feedback or "根据用户反馈优化规则精度",
    } if feedback else {
        "issues": [{"problem": "通用优化", "severity": "中", "suggestion": "收紧 source/sink 匹配条件，减少通配符使用"}],
        "recommendation": "提高规则精度，降低误报率",
    }

    try:
        optimized = optimize_rule(target, quality, lang=language)
    except Exception as e:
        return f"规则优化失败: {str(e)}"

    if not optimized:
        return "规则优化失败：LLM 未能生成有效优化结果。"

    _last_generated_rules[language] = optimized
    return (
        f"✅ 规则已优化：\n\n```json\n{_json.dumps(optimized, ensure_ascii=False, indent=2)}\n```"
        "\n💡 提示：可用优化后的规则重新扫描项目。"
    )



def tool_build_rule_from_cve(
    cve_id: str,
    rule_set_name: str = "",
    language: str = "python",
) -> str:
    import json as _json
    import os
    import urllib.request
    import ssl

    if not cve_id or not cve_id.strip():
        return "错误：请提供 CVE 编号，如 CVE-2026-45369。"
    cve_id = cve_id.strip().upper()
    if not cve_id.startswith("CVE-"):
        return f"错误：无效的 CVE 编号格式「{cve_id}」，应为 CVE-YYYY-NNNNN。"
    if language not in ("python", "java", "go", "js", "php", "c"):
        return f"错误：不支持的语言 {language}"
    user_id = _current_user_id_ctx.get()
    if not user_id:
        return "错误：未登录，无法创建规则集。请先登录。"

    ghsa_id = None
    cve_detail = None
    github_token = os.environ.get("GITHUB_TOKEN", "")
    try:
        api_url = f"https://api.github.com/advisories?cve_id={cve_id}&per_page=1"
        req = urllib.request.Request(api_url)
        if github_token:
            req.add_header("Authorization", f"token {github_token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "MaYisheng-Agent/2.1")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = _json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                ghsa_id = data[0].get("ghsa_id", "")
                cve_detail = data[0]
    except Exception:
        pass

    if not ghsa_id:
        try:
            from app.services.rule_service import search_github_advisories_sync
            results = search_github_advisories_sync(language=language, keyword=cve_id, count=5, token=github_token)
            if results:
                ghsa_id = results[0].get("ghsa_id", "")
        except Exception:
            pass

    if not ghsa_id:
        return (
            "未找到 " + cve_id + " 对应的 GitHub Advisory。可能原因：\n"
            "1. 该 CVE 较新，GitHub 尚未收录\n"
            "2. 该 CVE 不属于开源软件漏洞\n"
            "3. 网络问题导致查询失败\n"
            "\n替代方案：\n"
            "- 用 enrich_cve " + cve_id + " 查看 NVD 情报\n"
            "- 用 generate_rule 手动描述漏洞特征来生成规则"
        )

    if cve_detail:
        vulns = cve_detail.get("vulnerabilities", [])
        for v in vulns:
            eco = (v.get("package", {}) or {}).get("ecosystem", "").lower()
            eco_map = {"pip": "python", "maven": "java", "npm": "js", "go": "go"}
            if eco in eco_map:
                language = eco_map[eco]
                break

    from app.services.rule_service import create_rule_set, ingest_cves_to_rules
    set_name = rule_set_name or (cve_id + " 规则")
    rs = create_rule_set(
        user_id=user_id, name=set_name, lang=language, scene="full",
        description="从 " + cve_id + " 自动生成的规则集",
    )
    rule_set_id = rs["id"]

    results = ingest_cves_to_rules(
        user_id=user_id, rule_set_id=rule_set_id, ghsa_ids=[ghsa_id],
    )

    if results["generated"] == 0:
        return (
            "GitHub Advisory " + ghsa_id + " 已找到，但规则生成未成功。\n"
            "规则集「" + set_name + "」已创建但为空（ID: " + str(rule_set_id) + "）。\n"
            "请尝试用 generate_rule 手动描述漏洞特征。"
        )

    pkg_name = ""
    if cve_detail:
        vulns = cve_detail.get("vulnerabilities", [])
        if vulns:
            pkg_name = (vulns[0].get("package", {}) or {}).get("name", "")
    severity = (cve_detail or {}).get("severity", "")

    lines = [
        "从 " + cve_id + " 一键生成检测规则完成！",
        "规则集：" + set_name + "（ID: " + str(rule_set_id) + "）",
    ]
    if ghsa_id:
        lines.append("GitHub Advisory: " + ghsa_id)
    if pkg_name:
        lines.append("影响包: " + pkg_name)
    if severity:
        lines.append("严重程度: " + severity)
    lines.append("成功生成 " + str(results["generated"]) + " 条规则")
    if results["failed"]:
        lines.append(str(results["failed"]) + " 个 CVE 处理失败")
    lines.append("")
    lines.append("现在可以用这个规则集扫描项目。请告诉用户规则已生成，询问想扫描哪个项目路径。")
    return "\n".join(lines)

def tool_search_cve(
    language: str = "python",
    vuln_type: str = "",
    keyword: str = "",
    count: int = 10,
) -> str:
    """
    从 GitHub Advisory Database 搜索 CVE 漏洞。当用户提到想检测某类漏洞、想知道某类漏洞的最新 CVE，或者想构建针对特定漏洞类型的规则时，先用这个工具搜索现有的 CVE 情报。
    language: 编程语言，python/java/go/js/php/c
    vuln_type: 漏洞类型。支持 sql injection, command injection, code injection, ssrf,
              path traversal, xss, deserialization, xxe, open redirect,
              template injection, file inclusion, csrf, prototype pollution,
              redos, information disclosure, authentication bypass,
              authorization bypass, log injection, unrestricted file upload,
              denial of service, insecure randomness, memory corruption,
              certificate validation, http request smuggling 等
    keyword: 额外搜索关键词，可以是具体的库名、函数名等
    count: 返回数量，默认 10
    返回匹配的 CVE 列表（含 ghsa_id、描述、严重级别等），供后续 build_rules_from_cves 使用。
    """
    import json as _json
    from app.services.rule_service import search_github_advisories_sync

    if language not in ("python", "java", "go", "js", "php", "c"):
        return f"错误：不支持的语言 {language}"

    results = search_github_advisories_sync(
        language=language, vuln_type=vuln_type,
        count=count, keyword=keyword,
    )

    if not results:
        return f"未找到关于 {language} {vuln_type or keyword} 的 CVE 漏洞信息。可以尝试换关键词或扩大搜索范围。"

    lines = [f"找到 {len(results)} 个相关 CVE/Advisory：\n"]
    for i, r in enumerate(results):
        lines.append(
            f"{i + 1}. [{r['severity'].upper()}] {r['ghsa_id']} {r.get('cve_id', '')}\n"
            f"   {r['summary'][:120]}\n"
            f"   {r['html_url']}"
        )
    lines.append("\n💡 告诉用户你找到了这些漏洞，确认用户想为哪些漏洞生成检测规则。然后调用 build_rules_from_cves，传入用户选中的 ghsa_id 列表。")
    return "\n\n".join(lines)


def tool_build_rules_from_cves(
    ghsa_ids: str = "",
    rule_set_name: str = "",
    language: str = "python",
) -> str:
    """
    根据选中的 CVE (ghsa_id) 自动生成 YASA 检测规则并保存到用户的个人规则库。
    调用前必须先通过 search_cve 找到相关的 CVE 列表并与用户确认。
    ghsa_ids: 逗号分隔的 GitHub Advisory ID 列表，如 "GHSA-xxxx,GHSA-yyyy"
    rule_set_name: 新建的规则集名称，如 "我的 SSRF 规则"。留空则自动命名。
    language: 目标语言
    返回生成结果摘要（生成了多少规则，保存在哪个规则集等）。
    """
    import json as _json

    ghsa_list = [g.strip() for g in ghsa_ids.split(",") if g.strip()]
    if not ghsa_list:
        return "错误：请提供至少一个 ghsa_id（用逗号分隔），这些 id 可以从 search_cve 的返回结果中获取。"

    if language not in ("python", "java", "go", "js", "php", "c"):
        return f"错误：不支持的语言 {language}"

    user_id = _current_user_id_ctx.get()
    if not user_id:
        return "错误：未登录，无法创建规则集。请先登录。"

    # Create a new rule set
    from app.services.rule_service import create_rule_set, ingest_cves_to_rules

    set_name = rule_set_name or f"CVE 规则 {ghsa_list[0][:20]}"
    rs = create_rule_set(
        user_id=user_id,
        name=set_name,
        lang=language,
        scene="full",
        description=f"从 {len(ghsa_list)} 个 CVE 自动生成的规则集",
    )
    rule_set_id = rs["id"]

    # Run the ingest pipeline
    results = ingest_cves_to_rules(
        user_id=user_id,
        rule_set_id=rule_set_id,
        ghsa_ids=ghsa_list,
    )

    if results["generated"] == 0:
        return (
            f"⚠️ 规则生成未成功。{results['failed']} 个 CVE 处理失败。\n"
            + f"规则集「{set_name}」已创建但为空（ID: {rule_set_id}）。"
            + "\n请尝试搜索其他 CVE 或手动描述漏洞模式。"
        )

    return (
        f"✅ 规则构建完成！\n"
        + f"📦 规则集：{set_name}（ID: {rule_set_id}）\n"
        + f"📊 成功生成 {results['generated']} 条规则\n"
        + (f"❌ {results['failed']} 个 CVE 处理失败\n" if results["failed"] else "")
        + "\n💡 现在可以用这个规则集扫描项目了。用户可以选择要扫描的具体项目路径。"
        + "\n请告诉用户规则已生成，询问用户想扫描哪个项目（需要明确路径）。"
    )




# 当前 Agent 调用的用户上下文（contextvars 保证并发安全）
import contextvars
_current_user_id_ctx: contextvars.ContextVar[int] = contextvars.ContextVar("current_user_id", default=0)


def set_agent_user_context(user_id: int):
    """设置当前 Agent 调用的用户上下文（API 层在调用 Agent 前设置）"""
    _current_user_id_ctx.set(user_id)


from cve_intel import tool_enrich_cve, tool_search_nvd_cve, tool_check_kev, tool_query_osv, tool_cve_prioritize
from git_tools import tool_git_clone, tool_git_log, tool_git_show, tool_git_diff, tool_git_list_files
def create_tools_for_langchain():
    """返回供 LangChain 使用的 tool 列表"""
    from langchain_core.tools import StructuredTool

    tools = [
        StructuredTool.from_function(
            func=tool_scan_project,
            name="scan_project",
            description="对指定路径执行代码漏洞扫描。scan_path 为项目路径（必填，需要明确指定项目路径），language 为 python/java/go/js/php/c，mode 为 minimal 或 full。engine 为 yasa（污点分析，深但慢）或 semgrep（模式匹配，快但浅），用户不指定默认 yasa。favorite: 用户说「收藏」「要收藏」「永久保存」时传 True。",
        ),
        StructuredTool.from_function(
            func=tool_favorite_last_report,
            name="favorite_last_report",
            description="将最近一次扫描的报告标记为收藏（永久保留）。用户说「收藏」「收藏本次报告」时调用。",
        ),
        StructuredTool.from_function(
            func=tool_get_scan_report,
            name="get_scan_report",
            description="获取最近一次扫描的完整结果，用于回答用户关于扫描结果的问题。",
        ),
        StructuredTool.from_function(
            func=tool_list_reports,
            name="list_scan_reports",
            description="列出最近的扫描报告。limit 为数量，project_filter 为项目名过滤。用户问「有哪些报告」「报告列表」时调用。",
        ),
        StructuredTool.from_function(
            func=tool_get_report_content,
            name="get_report_by_index",
            description="获取指定报告的内容。report_index 为列表中的序号（1 开始）。用户说「查看第 N 个报告」时调用。",
        ),
        StructuredTool.from_function(
            func=tool_web_search,
            name="web_search",
            description="搜索互联网获取最新信息。当需要了解某个工具（如 YASA）的用法、最新漏洞情报、开源项目文档等自身训练数据中没有的内容时，先搜索再回答。query 为搜索关键词。",
        ),
        StructuredTool.from_function(
            func=tool_github_search,
            name="github_search",
            description="直接搜索 GitHub 上的仓库、代码或议题。当用户想找某个开源项目、GitHub 上的 CVE PoC、代码示例时，用这个比 web_search 更精准。query 为搜索关键词（支持 GitHub 搜索语法如 lang:python），search_type 为 repositories/code/issues。",
        ),
        StructuredTool.from_function(
            func=tool_generate_rule,
            name="generate_rule",
            description="根据用户手写描述的漏洞特征生成 YASA 规则。仅在用户自行描述漏洞模式（source入口、sink危险函数、触发条件）且未提及具体 CVE ID 时使用。如果用户提到了 CVE ID，必须用 enrich_cve + build_rule_from_cve。vuln_description 必填，language 默认 python。用户说「保存规则」时 save_to_rules=True。",
        ),
        StructuredTool.from_function(
            func=tool_optimize_rule,
            name="optimize_rule",
            description="根据用户反馈优化已生成的规则，收紧匹配条件、减少误报或补充漏报。用户说「优化规则」「这条规则误报太多」「没扫到某类漏洞」时调用。",
        ),
        StructuredTool.from_function(
            func=tool_search_cve,
            name="search_cve",
            description="从 GitHub Advisory Database 按漏洞类型/语言浏览和搜索 CVE 漏洞。适用于用户想了解某类漏洞有哪些最新 CVE 的场景。如果用户已提供具体 CVE ID（如CVE-2026-xxx），直接用 enrich_cve，不要用此工具。返回 ghsa_id 列表，后续可调用 build_rules_from_cves 批量生成规则。",
        ),
        StructuredTool.from_function(
            func=tool_build_rules_from_cves,
            name="build_rules_from_cves",
            description="根据选中的 ghsa_id 自动生成 YASA 检测规则并保存到个人规则库。ghsa_ids 为逗号分隔的 GitHub Advisory ID，rule_set_name 为规则集名称。通常与 search_cve 配合使用。如果用户直接提供了 CVE ID，优先使用 build_rule_from_cve。",
        ),

        StructuredTool.from_function(
            func=tool_build_rule_from_cve,
            name="build_rule_from_cve",
            description="输入一个 CVE ID，自动完成：查 GitHub Advisory → 提取漏洞特征 → LLM生成规则 → 自检优化 → 保存到个人规则库。一步完成，无需先搜 CVE。当用户说「CVE-2026-xxx 生成规则」时优先使用。cve_id 为 CVE 编号，rule_set_name 可选，language 默认 python。",
        ),
        StructuredTool.from_function(
            func=tool_enrich_cve,
            name="enrich_cve",
            description="查询完整 CVE 情报：NVD详情 + CVSS评分 + EPSS利用概率 + CISA KEV + 综合风险评分。当用户提到具体 CVE ID（如CVE-2026-xxx）时，这是第一步必调工具。获取情报后可继续调 build_rule_from_cve 生成检测规则。",
        ),
        StructuredTool.from_function(
            func=tool_search_nvd_cve,
            name="search_nvd",
            description="在 NVD 中搜索 CVE 漏洞，返回 CVSS 评分。比 search_cve（GitHub Advisory）覆盖更广，包含非开源软件漏洞。",
        ),
        StructuredTool.from_function(
            func=tool_check_kev,
            name="check_kev",
            description="检查 CVE 是否在 CISA 已知被利用漏洞目录（KEV）中。KEV 中的漏洞正在被真实攻击者利用，需立即修复。",
        ),
        StructuredTool.from_function(
            func=tool_query_osv,
            name="query_osv",
            description="查询 OSV（Open Source Vulnerabilities）数据库，检查某个依赖包/版本是否存在已知漏洞。package_name 为包名，version 为版本号（可选），ecosystem 为 PyPI/npm/Maven/Go 等。",
        ),
        StructuredTool.from_function(
            func=tool_cve_prioritize,
            name="prioritize_cves",
            description="按真实利用风险对 CVE 列表排序（CVSS × EPSS × KEV）。cve_ids 为逗号分隔的 CVE ID。用户有多个 CVE 需要排序优先级时调用。",
        ),
        StructuredTool.from_function(
            func=tool_git_clone,
            name="git_clone",
            description="克隆一个 Git 仓库到服务器临时目录进行分析。当用户提供了 GitHub/GitLab 仓库链接，或搜索到了 PoC 项目的 URL 想查看代码时调用。repo_url 为完整仓库 URL。",
        ),
        StructuredTool.from_function(
            func=tool_git_log,
            name="git_log",
            description="查看已克隆仓库的最近提交历史。repo_path 为本地克隆路径，max_count 为显示数量。用户说「查看提交记录」「最近改了什么」时调用。",
        ),
        StructuredTool.from_function(
            func=tool_git_show,
            name="git_show",
            description="查看某次提交的详细 diff。用于分析具体提交改了什么代码，找安全漏洞。repo_path 为仓库路径，commit 为提交哈希。",
        ),
        StructuredTool.from_function(
            func=tool_git_diff,
            name="git_diff",
            description="对比两个提交/分支/标签之间的差异。用于分析版本间的代码变更，追踪漏洞修复。repo_path 为仓库路径。",
        ),
        StructuredTool.from_function(
            func=tool_git_list_files,
            name="git_list_files",
            description="列出已克隆仓库的目录结构。用于了解项目文件布局。repo_path 为仓库路径，path 为子目录（可选）。",
        ),
    ]
    return tools
