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
) -> None:
    try:
        _set_task(task_id, status="running")
        from report import mark_as_favorite, save_report
        from scanner import (
            run_multi_lang_scan, run_yasa_scan,
            run_semgrep_scan, run_semgrep_multi_lang_scan,
        )

        MAX_TIMEOUT = 1800
        timeout_arg = timeout if 0 < timeout <= MAX_TIMEOUT else MAX_TIMEOUT

        def on_output(line: str) -> None:
            _set_task(task_id, progress=line.rstrip())

        all_results: List[Dict[str, Any]] = []
        use_semgrep = engine == "semgrep"

        if lang == "auto":
            if use_semgrep:
                results = run_semgrep_multi_lang_scan(
                    scan_path, timeout=timeout_arg, silent=True,
                    on_output=on_output, user_id=user_id,
                )
            else:
                results = run_multi_lang_scan(
                    scan_path, scene, timeout=timeout_arg, silent=True,
                    on_output=on_output, user_id=user_id,
                )
            for lang_r, ok, out, err, report_dir in results:
                r: Dict[str, Any] = {
                    "lang": lang_r, "ok": ok, "report_dir": report_dir,
                    "error": err, "engine": engine,
                }
                if ok and report_dir:
                    json_path, txt_path = save_report(report_dir, scan_path, lang_r, out)
                    if favorite:
                        mark_as_favorite(report_dir)
                    r["report_json"] = json_path
                    r["report_txt"] = txt_path
                all_results.append(r)
        else:
            if use_semgrep:
                ok, out, err, report_dir = run_semgrep_scan(
                    scan_path, lang, timeout=timeout_arg, silent=True,
                    on_output=on_output, user_id=user_id,
                )
            else:
                ok, out, err, report_dir = run_yasa_scan(
                    scan_path, lang, scene, timeout=timeout_arg, silent=True,
                    on_output=on_output, user_id=user_id,
                )
            r = {"lang": lang, "ok": ok, "report_dir": report_dir, "error": err, "engine": engine}
            if ok and report_dir:
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
