# -*- coding: utf-8 -*-
"""YASA / Semgrep 扫描核心逻辑"""

import json
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from collections import Counter

from config import (
    YASA_BUNDLE_PATH,
    YASA_EXECUTABLE,
    SCAN_EXCLUDE_DIRS,
    SEMGREP_RULES_PATH,
    get_rule_config_path,
    get_uast_sdk_path,
    get_reports_dir,
    get_checker_pack_and_analyzer,
)


# 扩展名 -> 语言
EXT_TO_LANG = {
    ".py": "python",
    ".java": "java",
    ".go": "go",
    ".js": "js",
    ".ts": "js",
    ".php": "php",
    ".c": "c",
    ".h": "c",
}


SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode", "target"}

def _count_languages(scan_path: str) -> Counter:
    """统计目录下各语言的文件数量"""
    path = Path(scan_path)
    counter: Counter = Counter()
    if not path.exists() or path.is_file():
        return counter
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = Path(f).suffix.lower()
            lang = EXT_TO_LANG.get(ext)
            if lang:
                counter[lang] += 1
    return counter


def detect_language(scan_path: str) -> str:
    """根据目录下文件扩展名统计，返回主要语言；单文件则按扩展名推断"""
    path = Path(scan_path)
    if not path.exists():
        return ""
    if path.is_file():
        return EXT_TO_LANG.get(path.suffix.lower(), "")
    counter = _count_languages(scan_path)
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def detect_all_languages(scan_path: str) -> list:
    """检测项目中所有使用的语言，按文件数量从多到少排序。返回如 [("python", 120), ("js", 45)]"""
    path = Path(scan_path)
    if not path.exists():
        return []
    if path.is_file():
        lang = EXT_TO_LANG.get(path.suffix.lower(), "")
        return [(lang, 1)] if lang else []
    counter = _count_languages(scan_path)
    return counter.most_common()


def windows_path_to_wsl(win_path: str) -> str:
    """保留兼容：Linux 上直接返回原路径"""
    return str(Path(win_path).resolve())


def _create_filtered_source(source_path: str, exclude_dirs: list) -> str:
    """创建过滤后的源码副本，排除无关目录。返回临时目录路径。"""
    import uuid
    temp_name = f"yasa-scan-{uuid.uuid4().hex[:8]}"
    temp_dir = f"/tmp/{temp_name}"
    try:
        os.makedirs(temp_dir, exist_ok=True)
        # 用参数列表避免 shell 注入，每个 exclude 单独传
        tar_cmd = ["tar", "-C", source_path]
        for d in exclude_dirs:
            tar_cmd += [f"--exclude={d}"]
        tar_cmd += ["-cf", "-", "."]
        untar_cmd = ["tar", "-C", temp_dir, "-xf", "-"]
        p1 = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(untar_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p1.stdout.close()
        p2.wait(timeout=120)
        p1.wait(timeout=10)
    except Exception:
        return ""
    return temp_dir


def _cleanup_filtered_source(temp_dir: str):
    """清理临时扫描目录"""
    if not temp_dir or not temp_dir.startswith("/tmp/yasa-scan-"):
        return
    try:
        subprocess.run(["rm", "-rf", temp_dir], capture_output=True, timeout=30)
    except Exception:
        pass


def _build_child_env() -> dict:
    """Return a clean environment for external scanner binaries."""
    env = os.environ.copy()
    for key in (
        "ELECTRON_RUN_AS_NODE",
        "ELECTRON_NO_ATTACH_CONSOLE",
        "ELECTRON_ENABLE_LOGGING",
        "NODE_OPTIONS",
        "NODE_PATH",
        "npm_config_prefix",
        "npm_lifecycle_event",
        "npm_lifecycle_script",
    ):
        env.pop(key, None)
    return env


def _has_excludable_dirs(scan_path: str, exclude_dirs: list) -> bool:
    """检查项目中是否存在需要排除的目录"""
    p = Path(scan_path)
    if not p.is_dir():
        return False
    try:
        for item in p.iterdir():
            if item.is_dir() and item.name in set(exclude_dirs):
                return True
    except Exception:
        pass
    return False


def run_yasa_scan(
    scan_path: str,
    lang: str,
    scene: str = "",
    timeout: int = None,
    silent: bool = False,
    cancel_check=None,
    exclude_dirs: list = None,
    on_output=None,
    user_id: int = None,
    rule_config_override: str = "",
) -> Tuple[bool, str, str, str]:
    """
    执行 YASA 扫描。
    返回 (成功, stdout, stderr, report_dir)
    timeout: 秒数，None 或 0 表示无超时限制。
    cancel_check: 可调用对象，返回 True 时中止扫描。
    exclude_dirs: 排除的目录列表，None 则用配置默认值。
    on_output: 实时输出回调，每行调用一次 on_output(line)。
    rule_config_override: 可选，自定义规则文件路径（用于合并多规则集扫描）。
    """
    rule_path = rule_config_override or get_rule_config_path(lang, scene)
    uast_path = get_uast_sdk_path(lang)

    if not rule_path:
        return False, "", f"未找到语言 {lang} 的规则配置", ""

    if exclude_dirs is None:
        exclude_dirs = SCAN_EXCLUDE_DIRS

    # 报告目录
    project_name = Path(scan_path).resolve().name or "unknown"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if user_id:
        report_dir = get_reports_dir() / str(user_id) / project_name / f"{project_name}_{lang}_{ts}"
    else:
        report_dir = get_reports_dir() / project_name / f"{project_name}_{lang}_{ts}"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_wsl = windows_path_to_wsl(str(report_dir))

    # 扫描路径：若为 Windows 路径则转 WSL
    target = scan_path
    if ":" in scan_path or scan_path.startswith("\\\\"):
        target = windows_path_to_wsl(scan_path)

    # 过滤：如果项目中存在需要排除的目录，创建过滤后的副本
    filtered_dir = ""
    use_filtered = False
    if Path(scan_path).is_dir() and exclude_dirs and _has_excludable_dirs(scan_path, exclude_dirs):
        if on_output:
            on_output(f"正在过滤无关目录（排除 {', '.join(exclude_dirs[:5])}{'...' if len(exclude_dirs) > 5 else ''}）...\n")
        filtered_dir = _create_filtered_source(target, exclude_dirs)
        if filtered_dir:
            target = filtered_dir
            use_filtered = True
            if on_output:
                on_output("过滤完成，开始扫描...\n")

    lang_arg = {"python": "python", "java": "java", "go": "golang", "js": "javascript", "php": "php", "c": "c"}.get(lang.lower(), lang)
    yasa_bin = f"{YASA_BUNDLE_PATH.rstrip('/')}/{YASA_EXECUTABLE}"
    cmd = [
        yasa_bin,
        "--ruleConfigFile", rule_path,
        "--sourcePath", target,
        "--language", lang_arg,
        "--entrypointMode", "BOTH",
        "--report", report_wsl,
    ]

    checker_pack, analyzer = get_checker_pack_and_analyzer(lang, scene)
    if checker_pack and analyzer:
        if lang.lower() == "c":
            checker_id = checker_pack if checker_pack.startswith("taint_flow_") else "taint_flow_c_input"
            cmd.extend(["--checkerIds", checker_id, "--analyzer", analyzer])
        else:
            cmd.extend(["--checkerPackIds", checker_pack, "--analyzer", analyzer])
    if uast_path:
        cmd.extend(["--uastSDKPath", uast_path])

    popen_kw = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_build_child_env(),
    )

    try:
        proc = subprocess.Popen(cmd, **popen_kw)
        stdout_lines = []

        def read_output():
            try:
                for line in proc.stdout:
                    if not silent:
                        try:
                            print(line, end="")
                        except (UnicodeEncodeError, UnicodeDecodeError):
                            pass
                    stdout_lines.append(line)
                    if on_output:
                        try:
                            on_output(line)
                        except Exception:
                            pass
            except Exception:
                pass

        t = threading.Thread(target=read_output)
        t.start()

        wait_chunk = 1
        elapsed = 0
        while True:
            if cancel_check and callable(cancel_check) and cancel_check():
                proc.kill()
                t.join(timeout=2)
                out = "".join(stdout_lines)
                if use_filtered:
                    _cleanup_filtered_source(filtered_dir)
                return False, out, "用户取消扫描", ""
            try:
                if timeout is not None and timeout > 0:
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        proc.kill()
                        if use_filtered:
                            _cleanup_filtered_source(filtered_dir)
                        return False, "", f"扫描超时（{timeout} 秒），可尝试缩小扫描范围", ""
                    wait_time = min(wait_chunk, remaining)
                else:
                    wait_time = wait_chunk
                proc.wait(timeout=wait_time)
                break
            except subprocess.TimeoutExpired:
                elapsed += wait_time

        t.join(timeout=2)
        out = "".join(stdout_lines)
        if use_filtered:
            _cleanup_filtered_source(filtered_dir)
        err = "" if proc.returncode == 0 else f"YASA 退出码 {proc.returncode}"
        return proc.returncode == 0, out, err, str(report_dir)
    except subprocess.TimeoutExpired:
        proc.kill()
        if use_filtered:
            _cleanup_filtered_source(filtered_dir)
        return False, "", f"扫描超时（{timeout} 秒），可尝试缩小扫描范围", ""
    except Exception as e:
        if use_filtered:
            _cleanup_filtered_source(filtered_dir)
        return False, "", str(e), ""


def run_multi_lang_scan(
    scan_path: str,
    scene: str = "",
    timeout: int = None,
    silent: bool = False,
    cancel_check=None,
    exclude_dirs: list = None,
    on_output=None,
    user_id: int = None,
    rule_config_override: str = "",
) -> list:
    """
    自动检测项目中所有语言并依次扫描。
    返回 [(lang, ok, out, err, report_dir), ...] 每种语言一个结果。
    """
    langs = detect_all_languages(scan_path)
    if not langs:
        return [("unknown", False, "", "未检测到支持的语言（Python/Java/Go/JS/PHP/C）", "")]

    results = []
    total = len(langs)
    for i, (lang, file_count) in enumerate(langs):
        if cancel_check and callable(cancel_check) and cancel_check():
            results.append((lang, False, "", "用户取消扫描", ""))
            break
        if on_output:
            on_output(f"\n{'='*50}\n[{i+1}/{total}] 扫描 {lang}（{file_count} 个文件）\n{'='*50}\n")
        ok, out, err, report_dir = run_yasa_scan(
            scan_path, lang, scene,
            timeout=timeout, silent=silent,
            cancel_check=cancel_check,
            exclude_dirs=exclude_dirs,
            on_output=on_output,
            user_id=user_id,
            rule_config_override=rule_config_override,
        )
        results.append((lang, ok, out, err, report_dir))
        if on_output:
            status = "完成" if ok else f"失败: {err}"
            on_output(f"[{lang}] {status}\n")
    return results


# ── Semgrep 扫描 ──────────────────────────────────────────────────────────

# 语言 -> 在线规则集（联网时使用）
SEMGREP_RULESETS = {
    "python": ["p/python", "p/owasp-top-ten", "p/secrets"],
    "java":   ["p/java", "p/owasp-top-ten", "p/secrets"],
    "go":     ["p/golang", "p/owasp-top-ten", "p/secrets"],
    "js":     ["p/javascript", "p/typescript", "p/owasp-top-ten", "p/secrets"],
    "php":    ["p/php", "p/owasp-top-ten", "p/secrets"],
    "c":      ["p/c", "p/owasp-top-ten", "p/secrets"],
}

# 语言 -> 离线规则子目录（相对于 SEMGREP_RULES_PATH）
SEMGREP_OFFLINE_DIRS = {
    "python": ["python", "generic/secrets"],
    "java":   ["java", "generic/secrets"],
    "go":     ["go", "generic/secrets"],
    "js":     ["javascript", "typescript", "generic/secrets"],
    "php":    ["php", "generic/secrets"],
    "c":      ["c", "generic/secrets"],
}


def _get_semgrep_config_args(lang: str) -> list:
    """
    返回 semgrep --config 参数列表。
    优先使用 SEMGREP_RULES_PATH 本地规则目录；未配置或目录不存在则降级到在线规则集。
    """
    from pathlib import Path as _Path
    rules_base = SEMGREP_RULES_PATH.strip() if SEMGREP_RULES_PATH else ""

    if rules_base:
        base = _Path(rules_base)
        subdirs = SEMGREP_OFFLINE_DIRS.get(lang.lower(), [])
        # 只加入实际存在的子目录
        existing = [str(base / d) for d in subdirs if (base / d).exists()]
        if existing:
            args = []
            for p in existing:
                args += ["--config", p]
            return args
        # 配置了路径但子目录不存在，尝试直接用根目录
        if base.exists():
            return ["--config", str(base)]

    # 降级：在线规则集
    rulesets = SEMGREP_RULESETS.get(lang.lower(), [])
    args = []
    for rs in rulesets:
        args += ["--config", rs]
    return args


def run_semgrep_scan(
    scan_path: str,
    lang: str,
    timeout: int = None,
    silent: bool = False,
    cancel_check=None,
    on_output=None,
    user_id: int = None,
) -> Tuple[bool, str, str, str]:
    """
    执行 Semgrep 扫描，输出 SARIF 格式报告。
    返回 (成功, stdout_text, stderr_text, report_dir)
    """
    config_args = _get_semgrep_config_args(lang)
    if not config_args:
        return False, "", f"Semgrep 不支持语言: {lang}", ""

    project_name = Path(scan_path).resolve().name or "unknown"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if user_id:
        report_dir = get_reports_dir() / str(user_id) / project_name / f"{project_name}_{lang}_{ts}_semgrep"
    else:
        report_dir = get_reports_dir() / project_name / f"{project_name}_{lang}_{ts}_semgrep"
    report_dir.mkdir(parents=True, exist_ok=True)

    sarif_path = report_dir / "report.sarif"

    lang_map = {"python": "python", "java": "java", "go": "go", "js": "js", "php": "php", "c": "c"}
    semgrep_lang = lang_map.get(lang.lower(), lang)

    cmd = [
        "semgrep",
        "--sarif",
        "--output", str(sarif_path),
        "--lang", semgrep_lang,
        "--jobs", "4",
        "--timeout", str(timeout) if timeout and timeout > 0 else "300",
        "--no-git-ignore",
    ] + config_args + [scan_path]

    # 离线模式不需要登录验证
    if SEMGREP_RULES_PATH:
        cmd.append("--no-rewrite-rule-ids")

    mode_desc = f"离线规则: {SEMGREP_RULES_PATH}" if SEMGREP_RULES_PATH else f"在线规则集: {', '.join(SEMGREP_RULESETS.get(lang.lower(), []))}"
    if on_output:
        on_output(f"[semgrep] 开始扫描 {lang}，{mode_desc}\n")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_build_child_env(),
        )
        stdout_lines = []

        def read_output():
            try:
                for line in proc.stdout:
                    if not silent:
                        try:
                            print(line, end="")
                        except (UnicodeEncodeError, UnicodeDecodeError):
                            pass
                    stdout_lines.append(line)
                    if on_output:
                        try:
                            on_output(line)
                        except Exception:
                            pass
            except Exception:
                pass

        t = threading.Thread(target=read_output)
        t.start()

        wait_chunk = 1
        elapsed = 0
        effective_timeout = timeout if (timeout and timeout > 0) else None
        while True:
            if cancel_check and callable(cancel_check) and cancel_check():
                proc.kill()
                t.join(timeout=2)
                return False, "".join(stdout_lines), "用户取消扫描", ""
            try:
                if effective_timeout:
                    remaining = effective_timeout - elapsed
                    if remaining <= 0:
                        proc.kill()
                        return False, "", f"Semgrep 扫描超时（{effective_timeout} 秒）", ""
                    proc.wait(timeout=min(wait_chunk, remaining))
                else:
                    proc.wait(timeout=wait_chunk)
                break
            except subprocess.TimeoutExpired:
                elapsed += wait_chunk

        t.join(timeout=2)
        out = "".join(stdout_lines)

        # semgrep 退出码 1 表示发现漏洞（正常），0 表示无发现，其他为错误
        if proc.returncode not in (0, 1):
            return False, out, f"Semgrep 异常退出（code={proc.returncode}）", ""

        if on_output:
            on_output(f"[semgrep] {lang} 扫描完成，报告: {sarif_path}\n")

        return True, out, "", str(report_dir)

    except FileNotFoundError:
        return False, "", "未找到 semgrep 命令，请先安装: pip install semgrep", ""
    except Exception as e:
        return False, "", str(e), ""


def run_semgrep_multi_lang_scan(
    scan_path: str,
    timeout: int = None,
    silent: bool = False,
    cancel_check=None,
    on_output=None,
    user_id: int = None,
) -> List[Tuple[str, bool, str, str, str]]:
    """
    自动检测语言并依次用 Semgrep 扫描。
    返回 [(lang, ok, out, err, report_dir), ...]
    """
    langs = detect_all_languages(scan_path)
    if not langs:
        return [("unknown", False, "", "未检测到支持的语言（Python/Java/Go/JS/PHP/C）", "")]

    results = []
    total = len(langs)
    for i, (lang, file_count) in enumerate(langs):
        if cancel_check and callable(cancel_check) and cancel_check():
            results.append((lang, False, "", "用户取消扫描", ""))
            break
        if lang not in SEMGREP_RULESETS:
            continue
        if on_output:
            on_output(f"\n{'='*50}\n[{i+1}/{total}] Semgrep 扫描 {lang}（{file_count} 个文件）\n{'='*50}\n")
        ok, out, err, report_dir = run_semgrep_scan(
            scan_path, lang,
            timeout=timeout, silent=silent,
            cancel_check=cancel_check,
            on_output=on_output,
            user_id=user_id,
        )
        results.append((lang, ok, out, err, report_dir))
        if on_output:
            status = "完成" if ok else f"失败: {err}"
            on_output(f"[semgrep/{lang}] {status}\n")
    return results
