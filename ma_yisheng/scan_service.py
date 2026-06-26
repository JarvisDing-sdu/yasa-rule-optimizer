"""Background scan service — extracted from api.py."""
import shutil
from typing import Dict, Any, List
from app.deps import _set_task


def run_scan_background(
    task_id: str,
    scan_path: str,
    lang: str,
    scene: str,
    timeout: int,
    favorite: bool,
    temp_dir: str = "",
    user_id: int = None,
    engine: str = "yasa",
    rule_set_ids: list = None,
) -> None:
    try:
        _set_task(task_id, status="running")
        from report import mark_as_favorite, save_report
        from scanner import (
            run_multi_lang_scan, run_yasa_scan, detect_all_languages,
            run_semgrep_scan, run_semgrep_multi_lang_scan,
        )

        MAX_TIMEOUT = 1800
        timeout_arg = timeout if 0 < timeout <= MAX_TIMEOUT else MAX_TIMEOUT

        def on_output(line: str) -> None:
            _set_task(task_id, progress=line.rstrip())

        all_results: List[Dict[str, Any]] = []
        use_semgrep = engine == "semgrep"

        if lang == "auto":
            # Detect languages and scan each one, with per-language rule merging
            langs = detect_all_languages(scan_path)
            if not langs:
                _set_task(task_id, status="failed", result={"error": "未检测到支持的语言"})
                return
            total = len(langs)
            for i, (detected_lang, file_count) in enumerate(langs):
                if use_semgrep:
                    ok, out, err, report_dir = run_semgrep_scan(
                        scan_path, detected_lang, timeout=timeout_arg, silent=True,
                        on_output=on_output, user_id=user_id,
                    )
                else:
                    # Merge rules per-language
                    merged_path = ""
                    if rule_set_ids:
                        from app.services.rule_service import merge_rules_for_scan
                        try:
                            merged_path = merge_rules_for_scan(user_id, detected_lang, rule_set_ids)
                        except Exception:
                            pass
                    on_output(f"\n{'='*50}\n[{i+1}/{total}] 扫描 {detected_lang}（{file_count} 个文件）\n{'='*50}\n")
                    ok, out, err, report_dir = run_yasa_scan(
                        scan_path, detected_lang, scene, timeout=timeout_arg, silent=True,
                        on_output=on_output, user_id=user_id,
                        rule_config_override=merged_path,
                    )
                error_text = err or ("" if ok else "扫描进程异常退出，请打开报告查看原始输出")
                r: Dict[str, Any] = {
                    "lang": detected_lang, "ok": ok, "report_dir": report_dir,
                    "error": error_text, "engine": engine,
                }
                if report_dir:
                    json_path, txt_path = save_report(report_dir, scan_path, detected_lang, out)
                    if favorite:
                        mark_as_favorite(report_dir)
                    r["report_json"] = json_path
                    r["report_txt"] = txt_path
                all_results.append(r)
        else:
            # Merge user-selected rule sets
            merged_rule_path = ""
            if rule_set_ids:
                from app.services.rule_service import merge_rules_for_scan
                try:
                    merged_rule_path = merge_rules_for_scan(user_id, lang, rule_set_ids)
                except Exception:
                    pass

            if use_semgrep:
                ok, out, err, report_dir = run_semgrep_scan(
                    scan_path, lang, timeout=timeout_arg, silent=True,
                    on_output=on_output, user_id=user_id,
                )
            else:
                ok, out, err, report_dir = run_yasa_scan(
                    scan_path, lang, scene, timeout=timeout_arg, silent=True,
                    on_output=on_output, user_id=user_id,
                    rule_config_override=merged_rule_path,
                )
            error_text = err or ("" if ok else "扫描进程异常退出，请打开报告查看原始输出")
            r = {"lang": lang, "ok": ok, "report_dir": report_dir, "error": error_text, "engine": engine}
            if report_dir:
                json_path, txt_path = save_report(report_dir, scan_path, lang, out)
                if favorite:
                    mark_as_favorite(report_dir)
                r["report_json"] = json_path
                r["report_txt"] = txt_path
            all_results.append(r)

        _set_task(task_id, status="done", result={"scans": all_results})
    except Exception as e:
        _set_task(task_id, status="failed", result={"error": str(e)})
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
