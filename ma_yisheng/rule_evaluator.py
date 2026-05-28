# -*- coding: utf-8 -*-
"""规则评估器：拿生成的规则跑 YASA 扫描，对比预期结果，计算 TP/FP/FN。

论文 Stage 3 的核心——不再让 LLM 空想，而是用真实扫描数据驱动分析。
"""

import json
import os
import hashlib
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 扫描结果缓存: rule_hash -> (findings, metrics)
_scan_cache: Dict[str, Tuple[List[Dict], Dict]] = {}


def _rule_hash(rule: Dict[str, Any]) -> str:
    """规则内容哈希，相同规则不重复扫描"""
    raw = json.dumps(rule, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _write_rule_config(rule: Dict[str, Any], lang: str) -> str:
    """将一条规则写入临时 JSON 文件（YASA 可读的 rule_config 格式），返回路径"""
    # YASA 的 rule_config 是一个数组
    if isinstance(rule, list):
        rules = rule
    else:
        rules = [rule]

    fd, path = tempfile.mkstemp(suffix=f"_{lang}.json", prefix="eval_rule_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    return path


def _load_expected(test_dir: str) -> Dict[str, Any]:
    """加载测试用例的预期结果"""
    expected_path = os.path.join(test_dir, "expected.json")
    if os.path.exists(expected_path):
        with open(expected_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _match_finding(finding: Dict, expected: Dict) -> bool:
    """判断一条扫描 finding 是否匹配预期"""
    f_type = finding.get("sink_attribute", "")
    e_type = expected.get("vuln_type", "")
    # 防止空串匹配一切
    if not f_type or not e_type:
        return False
    if e_type.lower() not in f_type.lower() and f_type.lower() not in e_type.lower():
        return False

    f_file = finding.get("file", "")
    e_file = expected.get("file", "")
    if not f_file:
        return False
    if e_file and os.path.basename(e_file) not in f_file and f_file not in e_file:
        return False

    return True


def evaluate_rule(
    rule: Dict[str, Any],
    lang: str,
    test_dir: str,
    timeout: int = 120,
    use_cache: bool = True,
    on_progress=None,
) -> Dict[str, Any]:
    """
    用测试集评估一条规则。

    参数:
        rule: 生成的 YASA 规则（dict，单条或列表）
        lang: 语言（python/java/go/js/php/c）
        test_dir: 测试用例目录（包含源码 + expected.json）
        timeout: 扫描超时秒数
        use_cache: 是否使用扫描缓存
        on_progress: 可选回调 on_progress(stage, message)

    返回:
        {
            "success": bool,
            "tp": int, "fp": int, "fn": int,
            "precision": float, "recall": float, "f1": float,
            "findings": [...],           # 所有扫描发现
            "matched": [...],            # TP（匹配预期的）
            "unmatched": [...],          # FP（未匹配预期的）
            "missed": [...],             # FN（预期但未发现的）
            "report_dir": str,           # SARIF 报告目录
            "scan_time": float,          # 扫描耗时（秒）
            "error": str or None,
        }
    """
    # 缓存检查
    rule_key = _rule_hash(rule) + lang + test_dir
    if use_cache and rule_key in _scan_cache:
        findings, metrics = _scan_cache[rule_key]
        return {**metrics, "findings": findings, "success": True, "error": None}

    # Step 1: 写临时规则文件
    if on_progress:
        on_progress("eval", "写入临时规则文件...")
    rule_path = _write_rule_config(rule, lang)

    try:
        # Step 2: 跑 YASA 扫描
        if on_progress:
            on_progress("eval", f"YASA 扫描 {test_dir} ...")
        t_start = time.time()

        from scanner import run_yasa_scan
        ok, out, err, report_dir = run_yasa_scan(
            scan_path=test_dir,
            lang=lang,
            scene="",
            timeout=timeout,
            silent=True,
            rule_config_override=rule_path,
        )
        scan_time = time.time() - t_start

        if not ok:
            return {
                "success": False,
                "tp": 0, "fp": 0, "fn": 0,
                "precision": 0.0, "recall": 0.0, "f1": 0.0,
                "findings": [], "matched": [], "unmatched": [], "missed": [],
                "report_dir": report_dir, "scan_time": scan_time,
                "error": err or "扫描失败",
            }

        # Step 3: 解析 SARIF
        if on_progress:
            on_progress("eval", "解析扫描结果...")
        from sarif_parser import parse_sarif
        sarif_path = os.path.join(report_dir, "report.sarif") if report_dir else ""
        findings = parse_sarif(sarif_path) if sarif_path else []

        # Step 4: 加载预期结果并对比（支持 min_count）
        expected = _load_expected(test_dir)
        expected_list = expected.get("expected_findings", [])

        matched = []      # TP
        unmatched = []    # FP
        missed = []       # FN
        # 追踪每个预期条目的匹配次数
        match_counts: Dict[int, int] = {i: 0 for i in range(len(expected_list))}

        for f in findings:
            found_match = False
            for i, exp in enumerate(expected_list):
                min_count = exp.get("min_count", 1)
                if match_counts[i] >= min_count:
                    continue  # 该条目已匹配足够次数
                if _match_finding(f, exp):
                    matched.append({"finding": f, "expected": exp})
                    match_counts[i] += 1
                    found_match = True
                    break
            if not found_match:
                unmatched.append({"finding": f, "reason": "未匹配任何预期漏洞类型"})

        # 检查哪些预期条目未匹配足够次数
        for i, exp in enumerate(expected_list):
            min_count = exp.get("min_count", 1)
            shortfall = min_count - match_counts[i]
            if shortfall > 0:
                missed.append({
                    "expected": exp,
                    "reason": f"需要 {min_count} 个匹配，仅找到 {match_counts[i]} 个",
                    "shortfall": shortfall,
                })

        tp = len(matched)
        fp = len(unmatched)
        fn = sum(item.get("shortfall", 1) for item in missed)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics = {
            "success": True,
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "matched": matched,
            "unmatched": unmatched,
            "missed": missed,
            "report_dir": report_dir,
            "scan_time": round(scan_time, 1),
            "error": None,
        }

        # 缓存
        if use_cache:
            _scan_cache[rule_key] = (findings, metrics)

        return {**metrics, "findings": findings}

    finally:
        # 清理临时规则文件
        try:
            os.unlink(rule_path)
        except Exception:
            pass


def evaluate_rule_multi_test(
    rule: Dict[str, Any],
    lang: str,
    test_dirs: List[str],
    timeout: int = 120,
    use_cache: bool = True,
    on_progress=None,
) -> Dict[str, Any]:
    """
    多个测试集评估规则，汇总结果。
    """
    all_tp = all_fp = all_fn = 0
    all_matched = []
    all_unmatched = []
    all_missed = []
    total_time = 0.0
    errors = []

    for test_dir in test_dirs:
        if on_progress:
            on_progress("eval", f"测试 {os.path.basename(test_dir)} ...")
        result = evaluate_rule(
            rule, lang, test_dir, timeout=timeout,
            use_cache=use_cache, on_progress=on_progress,
        )
        if not result["success"]:
            errors.append(f"{os.path.basename(test_dir)}: {result.get('error', 'unknown')}")
            continue

        all_tp += result["tp"]
        all_fp += result["fp"]
        all_fn += result["fn"]
        all_matched.extend(result["matched"])
        all_unmatched.extend(result["unmatched"])
        all_missed.extend(result["missed"])
        total_time += result["scan_time"]

    tp, fp, fn = all_tp, all_fp, all_fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "success": len(errors) == 0,
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "matched": all_matched,
        "unmatched": all_unmatched,
        "missed": all_missed,
        "scan_time": round(total_time, 1),
        "errors": errors,
    }
