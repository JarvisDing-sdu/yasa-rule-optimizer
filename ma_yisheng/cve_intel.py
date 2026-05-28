"""
CVE Intelligence tools for the MaYisheng Agent.
Aggregates NVD, EPSS, CISA KEV, GitHub Advisory, and OSV.
"""
import json
import ssl
import urllib.request
import urllib.parse
import os
from datetime import datetime
from typing import Optional

# ── CISA KEV catalog (cached) ──────────────────────────────────────────
_kev_cache: Optional[list] = None
_kev_cache_time: float = 0

def _get_kev_catalog() -> list:
    global _kev_cache, _kev_cache_time
    import time
    if _kev_cache and time.time() - _kev_cache_time < 3600:
        return _kev_cache

    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "MaYisheng/1.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode())
        _kev_cache = data.get("vulnerabilities", []) if isinstance(data, dict) else []
        _kev_cache_time = time.time()
    except Exception:
        _kev_cache = _kev_cache or []
    return _kev_cache


# ── Helper ─────────────────────────────────────────────────────────────
def _api_get(url: str, timeout: int = 15) -> Optional[dict]:
    ctx = ssl.create_default_context()
    headers = {
        "Accept": "application/json",
        "User-Agent": "MaYisheng-CVE-Intel/1.0",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


# ── NVD ────────────────────────────────────────────────────────────────
def search_nvd(keyword: str, limit: int = 10) -> list:
    """Search NVD for CVEs by keyword. Returns list of CVEs with CVSS scores."""
    params = urllib.parse.urlencode({
        "keywordSearch": keyword,
        "pageSize": min(limit, 20),
    })
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?{params}"
    data = _api_get(url)
    if not data:
        return []
    results = []
    for vuln in data.get("vulnerabilities", [])[:limit]:
        cve = vuln.get("cve", {})
        metrics = cve.get("metrics", {})
        cvss_v31 = metrics.get("cvssMetricV31", [{}])[0].get("cvssData", {})
        cvss_v30 = metrics.get("cvssMetricV30", [{}])[0].get("cvssData", {})
        cvss = cvss_v31 or cvss_v30
        results.append({
            "cve_id": cve.get("id", ""),
            "description": (cve.get("descriptions", [{}])[0].get("value", ""))[:300],
            "cvss_score": cvss.get("baseScore", "N/A"),
            "severity": cvss.get("baseSeverity", "N/A"),
            "published": cve.get("published", ""),
        })
    return results


def get_nvd_detail(cve_id: str) -> Optional[dict]:
    """Get full NVD detail for a CVE (CVSS vector, CWE, CPE)."""
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    data = _api_get(url)
    if not data:
        return None
    vulns = data.get("vulnerabilities", [])
    if not vulns:
        return None
    cve = vulns[0].get("cve", {})
    metrics = cve.get("metrics", {})
    cvss_v31 = metrics.get("cvssMetricV31", [{}])[0].get("cvssData", {})
    cvss_v30 = metrics.get("cvssMetricV30", [{}])[0].get("cvssData", {})
    cvss = cvss_v31 or cvss_v30
    weaknesses = cve.get("weaknesses", [{}])[0].get("description", [{}])[0].get("value", "")
    return {
        "cve_id": cve.get("id", ""),
        "description": (cve.get("descriptions", [{}])[0].get("value", ""))[:1000],
        "cvss_score": cvss.get("baseScore"),
        "severity": cvss.get("baseSeverity"),
        "vector": cvss.get("vectorString", ""),
        "cwe": weaknesses,
        "published": cve.get("published", ""),
    }


# ── EPSS ───────────────────────────────────────────────────────────────
def get_epss(cve_ids: list[str]) -> list:
    """Get EPSS exploitation probability scores for CVEs."""
    params = urllib.parse.urlencode({"cve": ",".join(cve_ids[:50])})
    url = f"https://api.first.org/data/v1/epss?{params}"
    data = _api_get(url)
    if not data:
        return []
    results = []
    for item in data.get("data", []):
        results.append({
            "cve_id": item.get("cve", ""),
            "epss": f"{float(item.get('epss', '0')) * 100:.1f}%",
            "percentile": f"{float(item.get('percentile', '0')) * 100:.1f}%",
        })
    return results


# ── CISA KEV ───────────────────────────────────────────────────────────
def check_kev(cve_id: str) -> Optional[dict]:
    """Check if CVE is in CISA Known Exploited Vulnerabilities catalog."""
    catalog = _get_kev_catalog()
    for v in catalog:
        if v.get("cveID", "").upper() == cve_id.upper():
            return {
                "cve_id": v.get("cveID"),
                "product": v.get("product", ""),
                "vendor": v.get("vendorProject", ""),
                "vulnerability_name": v.get("vulnerabilityName", ""),
                "date_added": v.get("dateAdded", ""),
                "due_date": v.get("dueDate", ""),
                "required_action": v.get("requiredAction", ""),
                "in_kev": True,
            }
    return {"cve_id": cve_id, "in_kev": False}


def search_kev(keyword: str, limit: int = 10) -> list:
    """Search CISA KEV by keyword (vendor/product)."""
    catalog = _get_kev_catalog()
    kw = keyword.lower()
    results = []
    for v in catalog:
        if kw in v.get("vendorProject", "").lower() or kw in v.get("product", "").lower() or kw in v.get("vulnerabilityName", "").lower():
            results.append({
                "cve_id": v.get("cveID"),
                "product": f"{v.get('vendorProject', '')} {v.get('product', '')}",
                "date_added": v.get("dateAdded", ""),
                "due_date": v.get("dueDate", ""),
            })
        if len(results) >= limit:
            break
    return results


# ── OSV ────────────────────────────────────────────────────────────────
def query_osv(package_name: str, version: str = "", ecosystem: str = "PyPI") -> list:
    """Query OSV.dev for vulnerabilities in a package version."""
    body = {
        "package": {"name": package_name, "ecosystem": ecosystem},
    }
    if version:
        body["version"] = version
    req = urllib.request.Request(
        "https://api.osv.dev/v1/query",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "MaYisheng/1.0"},
    )
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []
    results = []
    for vuln in data.get("vulns", []):
        results.append({
            "id": vuln.get("id", ""),
            "summary": (vuln.get("summary", ""))[:200] if vuln.get("summary") else "",
            "aliases": vuln.get("aliases", [])[:5],
            "fixed": vuln.get("fixed", ""),
            "modified": vuln.get("modified", ""),
            "database": vuln.get("database_specific", {}).get("severity", ""),
        })
    return results


# ── Enrichment (combines all sources) ───────────────────────────────────
def enrich_cve(cve_id: str) -> dict:
    """Full CVE enrichment: NVD + EPSS + KEV status."""
    nvd = get_nvd_detail(cve_id)
    epss = get_epss([cve_id])
    kev = check_kev(cve_id)

    result = {"cve_id": cve_id}
    if nvd:
        result["description"] = nvd.get("description", "")[:500]
        result["cvss_score"] = nvd.get("cvss_score")
        result["severity"] = nvd.get("severity")
        result["vector"] = nvd.get("vector", "")
        result["cwe"] = nvd.get("cwe", "")
    if epss:
        result["epss"] = epss[0].get("epss", "N/A") if epss else "N/A"
        result["epss_percentile"] = epss[0].get("percentile", "N/A") if epss else "N/A"
    if kev:
        result["in_kev"] = kev.get("in_kev", False)
        if kev.get("in_kev"):
            result["kev_due_date"] = kev.get("due_date", "")
            result["kev_action"] = kev.get("required_action", "")

    # Risk score: CVSS × EPSS × KEV
    cvss_val = nvd.get("cvss_score") or 0 if nvd else 0
    epss_val = float(str(epss[0].get("epss", "0%")).rstrip('%')) / 100 if epss else 0
    kev_mult = 2 if (kev and kev.get("in_kev")) else 1
    result["risk_score"] = round(cvss_val * epss_val * kev_mult, 2)
    return result


# ── Agent tool wrappers ─────────────────────────────────────────────────
def tool_enrich_cve(cve_id: str) -> str:
    """Query full CVE intelligence: get CVSS score, EPSS exploitation probability,
    CISA KEV status, and compute a practical risk score. Use when user asks about a specific CVE."""
    result = enrich_cve(cve_id.strip().upper())
    if not result.get("description"):
        return f"CVE {cve_id} 未找到详细信息（NVD 可能暂无数据）"
    lines = [
        f"## {cve_id}",
        f"**描述**: {result.get('description', 'N/A')}",
        f"**CVSS**: {result.get('cvss_score', 'N/A')} ({result.get('severity', 'N/A')})",
        f"**CVSS Vector**: {result.get('vector', 'N/A')}",
        f"**CWE**: {result.get('cwe', 'N/A')}",
        f"**EPSS 利用概率**: {result.get('epss', 'N/A')}（高于 {result.get('epss_percentile', 'N/A')} 百分位的漏洞）",
        f"**CISA KEV**: {'⚠️ 已知被利用！' if result.get('in_kev') else '未列入'}",
    ]
    if result.get("in_kev"):
        lines.append(f"**修复截止**: {result.get('kev_due_date', 'N/A')}")
        lines.append(f"**要求操作**: {result.get('kev_action', 'N/A')}")
    lines.append(f"**综合风险评分**: {result.get('risk_score', 'N/A')}")
    return "\n".join(lines)


def tool_search_nvd_cve(keyword: str, limit: int = 5) -> str:
    """Search NVD for CVEs matching a keyword. Returns CVE IDs with CVSS scores."""
    results = search_nvd(keyword, limit)
    if not results:
        return f"NVD 中未找到与 '{keyword}' 相关的 CVE"
    lines = [f"## NVD 搜索结果：{keyword}"]
    for r in results:
        lines.append(f"- **{r['cve_id']}** (CVSS {r['cvss_score']} {r['severity']}): {r['description'][:150]}")
    return "\n".join(lines)


def tool_check_kev(cve_id: str) -> str:
    """Check if CVE is in CISA Known Exploited Vulnerabilities (actively exploited)."""
    result = check_kev(cve_id.strip().upper())
    if result.get("in_kev"):
        return f"⚠️ **{cve_id}** 在 CISA KEV 中！\n产品: {result['product']}\n添加日期: {result['date_added']}\n修复截止: {result['due_date']}\n要求: {result['required_action']}"
    return f"**{cve_id}** 不在 CISA KEV 中"


def tool_query_osv(package_name: str, version: str = "", ecosystem: str = "PyPI") -> str:
    """Query OSV for vulnerabilities in a package/version. Supports PyPI, npm, Maven, Go, etc."""
    results = query_osv(package_name, version, ecosystem)
    if not results:
        return f"OSV 中未找到 {package_name}" + (f"=={version}" if version else "") + " 的漏洞"
    lines = [f"## OSV 查询：{package_name}" + (f"=={version}" if version else "")]
    for r in results[:10]:
        lines.append(f"- **{r['id']}**: {r['summary'][:150]}")
        if r.get("aliases"):
            lines.append(f"  别名: {', '.join(r['aliases'][:3])}")
        if r.get("fixed"):
            lines.append(f"  修复版本: {r['fixed']}")
    return "\n".join(lines)


def tool_cve_prioritize(cve_ids: str) -> str:
    """Prioritize a list of CVEs by real-world exploitation risk.
    cve_ids: comma-separated CVE IDs like 'CVE-2024-3400,CVE-2021-44228'"""
    ids = [c.strip() for c in cve_ids.split(",") if c.strip()]
    if not ids:
        return "请提供逗号分隔的 CVE ID 列表"
    results = []
    for cid in ids[:10]:
        result = enrich_cve(cid)
        results.append(result)
    results.sort(key=lambda r: r.get("risk_score", 0), reverse=True)
    lines = ["## CVE 风险排序（CVSS × EPSS × KEV）", ""]
    for i, r in enumerate(results, 1):
        kev_flag = " ⚠️KEV" if r.get("in_kev") else ""
        desc = r.get("description", "无描述")[:100]
        lines.append(f"**#{i}** {r['cve_id']} — 风险 {r.get('risk_score', 'N/A')}{kev_flag}")
        lines.append(f"  CVSS {r.get('cvss_score', '?')} | EPSS {r.get('epss', '?')} | {desc}")
        lines.append("")
    return "\n".join(lines)
