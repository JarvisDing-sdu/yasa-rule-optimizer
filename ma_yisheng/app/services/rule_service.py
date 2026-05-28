"""Rule set management + CVE ingest + scan merge logic."""
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging
from pathlib import Path

from app.database import SessionLocal, engine, Base
from app.models.user_rule import UserRuleSet, UserRule

_log = logging.getLogger("rule_service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Rule set CRUD ──────────────────────────────────────────────────────────

def get_official_rule_sets() -> List[Dict]:
    """Return official rule sets (not user-owned). Read from rules/ directory."""
    rules_dir = Path(__file__).resolve().parent.parent.parent / "rules"
    sets = []
    # One set per lang+scene combo
    for lang in ("python", "java", "go", "js", "php", "c"):
        for scene in ("minimal", "full"):
            fname = f"rule_config_{lang}_{scene}.json"
            fpath = rules_dir / fname
            if fpath.exists():
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                    rule_count = len(data) if isinstance(data, list) else 1
                except Exception as e:
                    _log.warning("Failed to load official rules %s: %s", fname, e)
                    rule_count = 0
                sets.append({
                    "id": f"official_{lang}_{scene}",
                    "name": f"Official {lang.title()} {scene.title()}",
                    "description": f"YASA 官方 {lang} {scene} 规则库",
                    "source_type": "official",
                    "lang": lang,
                    "scene": scene,
                    "rule_count": rule_count,
                    "is_official": True,
                })
    return sets


def list_user_rule_sets(user_id: int) -> List[Dict]:
    db = next(get_db())
    try:
        rows = db.query(UserRuleSet).filter(
            UserRuleSet.user_id == user_id
        ).order_by(UserRuleSet.updated_at.desc()).all()
        return [_rule_set_to_dict(r) for r in rows]
    finally:
        db.close()


def create_rule_set(user_id: int, name: str, lang: str = "python",
                    scene: str = "full", description: str = "") -> Dict:
    db = next(get_db())
    try:
        now = datetime.now(timezone.utc).timestamp()
        rs = UserRuleSet(
            user_id=user_id, name=name, description=description,
            lang=lang, scene=scene, source_type="manual",
            created_at=now, updated_at=now,
        )
        db.add(rs)
        db.commit()
        db.refresh(rs)
        return _rule_set_to_dict(rs)
    finally:
        db.close()



def get_official_rule_set_detail(rule_set_id: str):
    parts = rule_set_id.replace('official_', '').rsplit('_', 1)
    if len(parts) != 2:
        return None
    lang, scene = parts
    import json as _json
    rules_dir = Path(__file__).resolve().parent.parent.parent / 'rules'
    fname = f'rule_config_{lang}_{scene}.json'
    fpath = rules_dir / fname
    if not fpath.exists():
        return None
    try:
        data = _json.loads(fpath.read_text(encoding='utf-8'))
        rules_list = data if isinstance(data, list) else [data]
    except Exception:
        return None
    rules = []
    for i, r in enumerate(rules_list):
        meta = r.get('metadata', {})
        if not meta.get('ruleId'):
            checker_ids = r.get('checkerIds', []) if isinstance(r.get('checkerIds'), list) else []
            ck = checker_ids[0] if checker_ids else f'{lang}_{scene}'
            meta['ruleId'] = f'{ck}_{i+1}'
        if not meta.get('description'):
            sources = r.get('sources', [])
            sinks = r.get('sinks', [])
            if isinstance(sources, list) and isinstance(sinks, list):
                src_names = [s.get('name', '') for s in sources if isinstance(s, dict)]
                sink_names = [s.get('name', '') for s in sinks if isinstance(s, dict)]
                src_str = ', '.join(src_names[:3]) or '?'
                snk_str = ', '.join(sink_names[:3]) or '?'
                meta['description'] = 'sources: ' + src_str + ' -> sinks: ' + snk_str
            else:
                meta['description'] = 'YASA ' + lang + ' ' + scene + ' rule'
        r['metadata'] = meta
        rules.append({
            'id': i + 1,
            'db_id': i + 1,
            'rule_set_id': 0,
            'rule_data': _json.dumps(r, ensure_ascii=False),
            'is_enabled': 1,
            'created_at': '',
        })
    return {
        'id': rule_set_id,
        'name': f'Official {lang.title()} {scene.title()}',
        'description': f'YASA official {lang} {scene} rules',
        'source_type': 'official',
        'lang': lang,
        'scene': scene,
        'rule_count': len(rules_list),
        'is_official': True,
        'rules': rules,
    }

def get_rule_set_detail(user_id: int, rule_set_id: int) -> Optional[Dict]:
    db = next(get_db())
    try:
        rs = db.query(UserRuleSet).filter(
            UserRuleSet.id == rule_set_id,
            UserRuleSet.user_id == user_id,
        ).first()
        if not rs:
            return None
        result = _rule_set_to_dict(rs)
        rules = db.query(UserRule).filter(
            UserRule.rule_set_id == rule_set_id
        ).order_by(UserRule.created_at.desc()).all()
        result["rules"] = [_user_rule_to_dict(r) for r in rules]
        return result
    finally:
        db.close()


def delete_rule_set(user_id: int, rule_set_id: int) -> bool:
    db = next(get_db())
    try:
        rs = db.query(UserRuleSet).filter(
            UserRuleSet.id == rule_set_id,
            UserRuleSet.user_id == user_id,
        ).first()
        if not rs:
            return False
        # cascade deletes user_rules
        db.delete(rs)
        db.commit()
        return True
    finally:
        db.close()


def toggle_rule_in_set(user_id: int, rule_set_id: int, rule_id: int,
                       is_enabled: bool) -> bool:
    db = next(get_db())
    try:
        rs = db.query(UserRuleSet).filter(
            UserRuleSet.id == rule_set_id,
            UserRuleSet.user_id == user_id,
        ).first()
        if not rs:
            return False
        rule = db.query(UserRule).filter(
            UserRule.id == rule_id,
            UserRule.rule_set_id == rule_set_id,
        ).first()
        if not rule:
            return False
        rule.is_enabled = 1 if is_enabled else 0
        db.commit()
        return True
    finally:
        db.close()


def remove_rule_from_set(user_id: int, rule_set_id: int, rule_db_id: int) -> bool:
    db = next(get_db())
    try:
        rs = db.query(UserRuleSet).filter(
            UserRuleSet.id == rule_set_id,
            UserRuleSet.user_id == user_id,
        ).first()
        if not rs:
            return False
        rule = db.query(UserRule).filter(
            UserRule.id == rule_db_id,
            UserRule.rule_set_id == rule_set_id,
        ).first()
        if not rule:
            return False
        db.delete(rule)
        rs.rule_count = db.query(UserRule).filter(
            UserRule.rule_set_id == rule_set_id
        ).count()
        db.commit()
        return True
    finally:
        db.close()


# ── Clone official rules ───────────────────────────────────────────────────

def clone_official_rules(user_id: int, lang: str = "python",
                         scene: str = "full", name: str = "") -> Optional[Dict]:
    """Clone official YASA rules into user's personal rule set."""
    rules_dir = Path(__file__).resolve().parent.parent.parent / "rules"
    fname = f"rule_config_{lang}_{scene}.json"
    fpath = rules_dir / fname
    if not fpath.exists():
        return None

    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        rules_list = data if isinstance(data, list) else [data]
    except Exception as e:
        _log.warning("Failed to clone official rules %s/%s: %s", lang, scene, e)
        return None

    set_name = name or f"Official {lang.title()} {scene.title()} Clone"
    db = next(get_db())
    try:
        now = datetime.now(timezone.utc).timestamp()
        rs = UserRuleSet(
            user_id=user_id, name=set_name,
            description=f"克隆自官方 {lang} {scene} 规则库",
            source_type="official_clone", lang=lang, scene=scene,
            rule_count=len(rules_list), created_at=now, updated_at=now,
        )
        db.add(rs)
        db.flush()

        for rule in rules_list:
            ur = UserRule(
                rule_set_id=rs.id,
                rule_data=json.dumps(rule, ensure_ascii=False),
                rule_id=str((rule.get("metadata") or {}).get("ruleId") or f"cloned_{int(time.time())}"),
                created_at=now,
            )
            db.add(ur)

        db.commit()
        db.refresh(rs)
        return _rule_set_to_dict(rs)
    finally:
        db.close()


# ── Add generated rules to a set ────────────────────────────────────────────

def add_rules_to_set(user_id: int, rule_set_id: int,
                     rules: List[Dict]) -> int:
    """Add generated rules to a rule set. Returns number added."""
    db = next(get_db())
    try:
        rs = db.query(UserRuleSet).filter(
            UserRuleSet.id == rule_set_id,
            UserRuleSet.user_id == user_id,
        ).first()
        if not rs:
            return 0

        now = datetime.now(timezone.utc).timestamp()
        added = 0
        for rule in rules:
            meta = rule.get("metadata") or {}
            rid = str(meta.get("ruleId") or f"generated_{int(time.time())}")
            # skip duplicate rule_id in same set
            existing = db.query(UserRule).filter(
                UserRule.rule_set_id == rule_set_id,
                UserRule.rule_id == rid,
            ).first()
            if existing:
                continue
            ur = UserRule(
                rule_set_id=rule_set_id,
                rule_data=json.dumps(rule, ensure_ascii=False),
                rule_id=rid,
                created_at=now,
            )
            db.add(ur)
            added += 1

        rs.rule_count = db.query(UserRule).filter(
            UserRule.rule_set_id == rule_set_id
        ).count()
        rs.updated_at = now
        rs.source_type = "generated"
        db.commit()
        return added
    finally:
        db.close()


# ── Merge rules for scan ────────────────────────────────────────────────────

def merge_rules_for_scan(user_id: int, lang: str,
                         rule_set_ids: Optional[List] = None) -> str:
    """
    Merge selected rule sets into a temporary rule config file for YASA.
    Returns path to the temp merged file.
    Always includes official rules for the given lang.
    """
    all_rules: List[Dict] = []

    # Always include official rules
    rules_dir = Path(__file__).resolve().parent.parent.parent / "rules"
    for scene in ("full", "minimal"):
        fpath = rules_dir / f"rule_config_{lang}_{scene}.json"
        if fpath.exists():
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                all_rules.extend(data if isinstance(data, list) else [data])
            except Exception as e:
                _log.debug("Failed to load official rule %s: %s", fpath, e)
                pass

    # Add user-selected rule sets
    if rule_set_ids:
        db = next(get_db())
        try:
            for rsid in rule_set_ids:
                if isinstance(rsid, str) and rsid.startswith("official_"):
                    continue  # already included above
                try:
                    rsid_int = int(rsid)
                except (ValueError, TypeError):
                    continue
                rs = db.query(UserRuleSet).filter(
                    UserRuleSet.id == rsid_int
                ).first()
                if not rs:
                    continue
                rules = db.query(UserRule).filter(
                    UserRule.rule_set_id == rsid_int,
                    UserRule.is_enabled == 1,
                ).all()
                for r in rules:
                    try:
                        all_rules.append(json.loads(r.rule_data))
                    except Exception as e:
                        _log.debug("Failed to parse user rule data: %s", e)
                        pass
        finally:
            db.close()

    # Deduplicate by ruleId
    seen = set()
    deduped = []
    for r in all_rules:
        rid = str((r.get("metadata") or {}).get("ruleId") or "")
        if rid and rid in seen:
            continue
        if rid:
            seen.add(rid)
        deduped.append(r)

    # Write temp file
    tmp_dir = Path("/tmp/yasa-merged-rules")
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"user_{user_id}_lang_{lang}_{int(time.time())}.json"
    tmp_path.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(tmp_path)


# ── CVE search ──────────────────────────────────────────────────────────────

def search_github_advisories_sync(language: str, vuln_type: str = "",
                                   count: int = 10, keyword: str = "",
                                   github_token: str = "") -> List[Dict]:
    """Search GitHub Advisory Database for vulnerabilities (sync).

    Fetches up to 500 advisories (5 pages × 100) and filters by vuln_type
    using CWE ID matching (high precision) with keyword fallback.
    """
    import time as _time
    import urllib.request
    import urllib.parse
    import ssl

    ecosystem_map = {"python": "pip", "java": "maven", "javascript": "npm", "js": "npm", "go": "go", "php": "composer"}
    ecosystem = ecosystem_map.get(language.lower(), "")

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MaYisheng-Scanner/1.0",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    else:
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    # ── CWE ID → vuln_type mapping (high-precision matching) ──────────────
    CWE_TO_TYPE = {
        "CWE-89": "sql injection", "CWE-564": "sql injection",
        "CWE-943": "nosql injection",
        "CWE-77": "command injection", "CWE-78": "command injection",
        "CWE-94": "code injection", "CWE-95": "code injection",
        "CWE-918": "ssrf",
        "CWE-22": "path traversal", "CWE-23": "path traversal",
        "CWE-29": "path traversal", "CWE-35": "path traversal",
        "CWE-36": "path traversal", "CWE-37": "path traversal",
        "CWE-79": "xss", "CWE-80": "xss", "CWE-81": "xss",
        "CWE-82": "xss", "CWE-83": "xss", "CWE-84": "xss",
        "CWE-85": "xss", "CWE-86": "xss", "CWE-87": "xss",
        "CWE-502": "deserialization",
        "CWE-611": "xxe", "CWE-776": "xxe",
        "CWE-601": "open redirect",
        "CWE-1336": "template injection",
        "CWE-98": "file inclusion", "CWE-73": "file inclusion",
        "CWE-352": "csrf",
        "CWE-1321": "prototype pollution", "CWE-915": "prototype pollution",
        "CWE-1333": "redos",
        "CWE-200": "information disclosure", "CWE-201": "information disclosure",
        "CWE-287": "authentication bypass", "CWE-288": "authentication bypass",
        "CWE-290": "authentication bypass",
        "CWE-862": "authorization bypass", "CWE-863": "authorization bypass",
        "CWE-269": "privilege escalation",
        "CWE-117": "log injection", "CWE-93": "crlf injection",
        "CWE-434": "unrestricted file upload",
        "CWE-400": "denial of service", "CWE-770": "denial of service",
        "CWE-470": "unsafe reflection",
        "CWE-1236": "csv injection",
        "CWE-917": "expression language injection",
        "CWE-444": "http request smuggling",
        "CWE-338": "insecure randomness", "CWE-330": "insecure randomness",
        "CWE-327": "weak cryptography", "CWE-326": "weak cryptography",
        "CWE-347": "jwt verification bypass",
        "CWE-532": "information disclosure",
        "CWE-295": "certificate validation", "CWE-297": "certificate validation",
        "CWE-787": "memory corruption", "CWE-125": "memory corruption",
        "CWE-416": "use after free",
    }

    # ── Keyword-based matching (fallback when CWE not tagged) ─────────────
    VT_KEYWORDS = {
        "sql injection": [
            "sql injection", "sqli", "blind sql", "nosql injection",
            "sql command injection",
        ],
        "command injection": [
            "command injection", "os command injection", "shell injection",
            "arbitrary command execution", "command execution via",
            "cmd injection", "os command execution",
        ],
        "code injection": [
            "code injection", "arbitrary code execution", "remote code execution",
            "eval injection", "code execution via", "rce via",
            "injection of arbitrary code",
        ],
        "ssrf": [
            "ssrf", "server-side request forgery",
        ],
        "path traversal": [
            "path traversal", "directory traversal", "directory escape",
            "path manipulation", "arbitrary file read", "arbitrary file write",
            "arbitrary file overwrite", "arbitrary file disclosure",
            "file disclosure", "zip slip", "pathname traversal",
            "relative path traversal", "absolute path traversal",
            "path injection",
        ],
        "xss": [
            "xss", "cross-site scripting", "cross site scripting",
            "stored xss", "reflected xss", "dom based xss",
            "dom-based xss", "html injection", "javascript injection",
        ],
        "deserialization": [
            "deserialization", "deserialisation", "insecure deserial",
            "deserialization of untrusted", "untrusted deserialization",
            "deserialize untrusted", "deserializing untrusted",
            "pickle", "unpickle", "yaml.load", "yaml.unsafe_load",
            "marshal.load", "objectinputstream", "readobject",
            "java deserialization", "python deserialization",
            "nodejs deserialization", "php deserialization",
            "object injection", "unsafe deserialization",
            "untrusted data deserial", "serialization vulnerability",
        ],
        "xxe": [
            "xxe", "xml external entity", "xml entity expansion",
            "xml entity injection", "billion laughs",
        ],
        "open redirect": [
            "open redirect", "url redirection", "unvalidated redirect",
            "url redirect vulnerability", "open url redirect",
            "redirect via",
        ],
        "template injection": [
            "template injection", "ssti", "server-side template injection",
            "jinja2 injection", "freemarker injection",
            "velocity template injection", "template engine injection",
        ],
        "file inclusion": [
            "file inclusion", "local file inclusion", "lfi",
            "remote file inclusion", "rfi", "file include vulnerability",
        ],
        "csrf": [
            "csrf", "cross-site request forgery", "cross site request forgery",
            "xsrf",
        ],
        "prototype pollution": [
            "prototype pollution", "__proto__", "constructor.prototype",
            "object prototype pollution",
        ],
        "redos": [
            "redos", "regular expression denial of service",
            "regex denial of service", "regex backtracking",
            "regex dos", "regexp backtracking",
        ],
        "information disclosure": [
            "information disclosure", "information leak", "sensitive data exposure",
            "data leak", "data exposure", "information exposure",
            "sensitive information disclosure", "sensitive data leak",
            "credentials leak", "token leak", "secret leak",
        ],
        "authentication bypass": [
            "authentication bypass", "auth bypass", "bypass authentication",
            "login bypass", "authentication bypass via",
            "bypass auth",
        ],
        "authorization bypass": [
            "authorization bypass", "authz bypass", "privilege escalation",
            "access control bypass", "permission bypass",
            "insufficient authorization", "improper authorization",
            "broken access control",
        ],
        "log injection": [
            "log injection", "log forging", "log manipulation",
            "crlf injection", "log poisoning", "crlf injection",
            "carriage return line feed",
        ],
        "unrestricted file upload": [
            "unrestricted file upload", "arbitrary file upload",
            "file upload vulnerability", "malicious file upload",
            "unrestricted upload",
        ],
        "denial of service": [
            "denial of service", "dos attack", "resource exhaustion",
            "denial of service via", "application crash",
        ],
        "insecure randomness": [
            "insecure randomness", "weak random", "predictable random",
            "insufficient entropy", "insecure prng", "predictable prng",
            "weak prng", "cryptographically weak",
        ],
        "rce": [
            "remote code execution", "rce", "arbitrary code execution",
            "command injection", "code injection",
        ],
        "memory corruption": [
            "memory corruption", "buffer overflow", "heap overflow",
            "stack overflow", "use after free", "double free",
        ],
        "certificate validation": [
            "certificate validation", "ssl verification bypass",
            "tls verification bypass", "improper certificate validation",
            "certificate pinning bypass",
        ],
        "http request smuggling": [
            "http request smuggling", "request smuggling",
            "http splitting",
        ],
    }

    import ssl as _ssl
    ctx = _ssl.create_default_context()

    # ── Pagination: fetch up to 5 pages (500 advisories) ──────────────────
    all_advisories = []
    max_pages = 5
    per_page = 100

    for page in range(1, max_pages + 1):
        params = {
            "per_page": str(per_page),
            "page": str(page),
            "sort": "published",
            "direction": "desc",
            "state": "published",
        }
        if ecosystem:
            params["ecosystem"] = ecosystem
        qs = urllib.parse.urlencode(params)
        url = f"https://api.github.com/advisories?{qs}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            break

        if not isinstance(data, list) or not data:
            break

        for adv in data:
            # Extract CWE IDs from cwes array and identifiers
            cwe_ids = []
            for cwe_obj in (adv.get("cwes") or []):
                if isinstance(cwe_obj, dict):
                    cid = cwe_obj.get("cwe_id", "")
                elif isinstance(cwe_obj, str):
                    cid = cwe_obj
                else:
                    continue
                if cid:
                    cwe_ids.append(cid)
            for identifier in (adv.get("identifiers") or []):
                if isinstance(identifier, dict) and identifier.get("type") == "CWE":
                    val = identifier.get("value", "")
                    if val:
                        cwe_ids.append(val)

            all_advisories.append({
                "ghsa_id": adv.get("ghsa_id", ""),
                "cve_id": adv.get("cve_id", ""),
                "summary": adv.get("summary", ""),
                "description": (adv.get("description") or "")[:500],
                "severity": adv.get("severity", ""),
                "published_at": adv.get("published_at", ""),
                "html_url": adv.get("html_url", ""),
                "ecosystem": ecosystem,
                "cwe_ids": cwe_ids,
            })

        # Stop if last page was partial — no more results
        if len(data) < per_page:
            break

        # Rate-limit: 0.5s gap between pages (GitHub allows ~10 req/min unauthenticated)
        if page < max_pages:
            _time.sleep(0.5)

    # ── Keyword filter (on full advisory text) ────────────────────────────
    results = all_advisories
    if keyword:
        kw = keyword.lower()
        results = [r for r in results
                   if kw in r["summary"].lower()
                   or kw in r["description"].lower()
                   or kw in r.get("cve_id", "").lower()]

    # ── Vuln type filter (CWE first, then keyword fallback) ───────────────
    if vuln_type:
        vt = vuln_type.lower().strip().replace("-", " ")  # 前端用连字符，统一转空格
        # rce 是前端别名，合并 code injection + command injection 的 CWE
        vt_lookup = vt
        if vt == "rce":
            target_cwes = {cwe for cwe, vtype in CWE_TO_TYPE.items()
                           if vtype in ("code injection", "command injection")}
        else:
            target_cwes = {cwe for cwe, vtype in CWE_TO_TYPE.items()
                           if vtype == vt_lookup}

        if target_cwes:
            match_kws = VT_KEYWORDS.get(vt, [vt])

            def _matches_vuln_type(r):
                # CWE match (high precision)
                if set(r.get("cwe_ids", [])) & target_cwes:
                    return True
                # Keyword match (fallback for advisories without CWE tagging)
                text = (r["summary"] + " " + r["description"]).lower()
                if any(kw in text for kw in match_kws):
                    return True
                return False

            results = [r for r in results if _matches_vuln_type(r)]
        else:
            # No CWE mapping for this type — use keyword alone
            match_kws = VT_KEYWORDS.get(vt, [vt])
            results = [r for r in results
                       if any(kw in r["summary"].lower()
                              or kw in r["description"].lower()
                              for kw in match_kws)]

    return results[:count]


def fetch_cve_detail_sync(ghsa_id: str, github_token: str = "") -> Optional[Dict]:
    """Get full advisory detail including patch references (sync)."""
    import urllib.request
    import ssl

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MaYisheng-Scanner/1.0",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    else:
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            f"https://api.github.com/advisories/{ghsa_id}",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            detail = json.loads(resp.read().decode("utf-8", errors="replace"))

        references = detail.get("references") or []
        commit_url = ""
        for ref in references:
            url = ref if isinstance(ref, str) else ref.get("url", "")
            if "/commit/" in url or "/pull/" in url:
                commit_url = url
                break

        return {
            "ghsa_id": detail.get("ghsa_id", ""),
            "cve_id": detail.get("cve_id", ""),
            "summary": detail.get("summary", ""),
            "description": (detail.get("description") or "")[:2000],
            "severity": detail.get("severity", ""),
            "published_at": detail.get("published_at", ""),
            "vulnerabilities": detail.get("vulnerabilities", []),
            "references": references[:10],
            "commit_url": commit_url,
        }
    except Exception as e:
        _log.warning("Failed to fetch CVE detail for %s: %s", ghsa_id, e)
        return None


# async wrappers for FastAPI routes
async def search_github_advisories(language: str, vuln_type: str = "",
                                   count: int = 10, keyword: str = "",
                                   github_token: str = "") -> List[Dict]:
    import asyncio
    return await asyncio.to_thread(
        search_github_advisories_sync, language, vuln_type, count, keyword, github_token
    )


async def fetch_cve_detail(ghsa_id: str, github_token: str = "") -> Optional[Dict]:
    import asyncio
    return await asyncio.to_thread(fetch_cve_detail_sync, ghsa_id, github_token)


# ── 4-stage pipeline integration ────────────────────────────────────────────

def build_rule_pipeline(vuln_case: Dict, provider: str = "deepseek",
                        model: Optional[str] = None,
                        api_key: Optional[str] = None,
                        test_dirs: Optional[List[str]] = None,
                        max_iterations: int = 3,
                        target_f1: float = 0.85,
                        on_progress=None) -> Optional[Dict[str, Any]]:
    """
    运行完整的 4 阶段规则生成管道 + 迭代优化（论文方法）。

    Stages:
      1. 结构化漏洞描述 (LLM)
      2. 生成候选规则 (LLM)
      3. YASA 扫描评估 → TP/FP/FN (真实扫描 + 对比预期)
      4. 基于评估结果优化规则 (LLM)
      迭代: 重复 3→4 直到 F1 达标或达到最大轮次

    Args:
        vuln_case: 漏洞案例字典
        test_dirs: 测试目录列表，用于 Stage 3 评估。不传则跳过扫描评估（降级到 LLM 自评）
        max_iterations: 最大迭代次数
        target_f1: 目标 F1 分数，达到后停止
        on_progress: 回调 on_progress(stage, message)

    Returns:
        { "rules": [...], "best_rule": {...}, "best_f1": float,
          "iterations": [...], "evaluations": [...] }
        失败返回 None
    """
    from llm import generate_rule_from_case, analyze_rule_quality, optimize_rule

    if not api_key:
        from config import LLM_API_KEY
        api_key = LLM_API_KEY
    if not api_key:
        return None

    lang = str(vuln_case.get("language") or "python")
    code_snippet = vuln_case.get("source_code_before") or ""

    # ── Stage 1+2: 生成初始规则 ──────────────────────────────────────────
    if on_progress:
        on_progress("generate", f"Stage 1+2: 生成 {lang} 规则...")
    rules = generate_rule_from_case(
        vuln_description=f"{vuln_case.get('vulnerability_type')}: {vuln_case.get('notes') or vuln_case.get('summary') or ''}",
        lang=lang,
        code_snippet=code_snippet[:2000] if code_snippet else "",
    )
    if not rules:
        return None

    best_rule = rules[0]
    best_f1 = 0.0
    iterations_log = []
    evaluations_log = []

    # ── Stage 3+4 迭代循环 ──────────────────────────────────────────────
    for iteration in range(max_iterations):
        if on_progress:
            on_progress("iterate", f"迭代 {iteration + 1}/{max_iterations}...")

        improved = False
        for i, rule in enumerate(rules):
            # Stage 3: 评估
            evaluation = None
            if test_dirs:
                # 真实 YASA 扫描评估 ✨
                if on_progress:
                    on_progress("eval", f"Stage 3: YASA 扫描评估规则...")
                from rule_evaluator import evaluate_rule_multi_test
                evaluation = evaluate_rule_multi_test(
                    rule, lang, test_dirs,
                    timeout=180,
                    use_cache=False,  # 迭代时不缓存,每次可能规则不同
                    on_progress=on_progress,
                )
                evaluations_log.append({
                    "iteration": iteration, "rule_index": i,
                    "f1": evaluation["f1"], "tp": evaluation["tp"],
                    "fp": evaluation["fp"], "fn": evaluation["fn"],
                })

            # Stage 3: LLM 分析（喂真实评估数据）
            if on_progress:
                on_progress("analyze", f"Stage 3: 分析评估结果...")
            scan_findings = evaluation.get("findings", []) if evaluation else []
            quality = analyze_rule_quality(
                rule, scan_findings,
                evaluation=evaluation,
            )
            if not quality or not quality.get("issues"):
                continue

            # Stage 4: 优化
            if on_progress:
                on_progress("optimize", f"Stage 4: 优化规则...")
            optimized = optimize_rule(rule, quality, lang)
            if optimized and len(optimized) > 0:
                rules[i] = optimized[0] if isinstance(optimized, list) else optimized
                improved = True

            # 检查是否已经足够好（深拷贝避免后续优化覆盖）
            if evaluation and evaluation["f1"] > best_f1:
                best_f1 = evaluation["f1"]
                best_rule = json.loads(json.dumps(rule, ensure_ascii=False))
            elif evaluation is None:
                best_rule = rule  # 无评估时保留最后一次

        iterations_log.append({
            "iteration": iteration,
            "improved": improved,
            "best_f1": best_f1,
        })

        # 提前退出条件
        if best_f1 >= target_f1:
            if on_progress:
                on_progress("done", f"F1={best_f1:.3f} 已达标 (≥{target_f1})，停止迭代")
            break
        if not improved:
            if on_progress:
                on_progress("done", "本轮无改进，停止迭代")
            break

    # ── 添加元数据 ──────────────────────────────────────────────────────
    for rule in rules:
        meta = rule.setdefault("metadata", {})
        meta.setdefault("generatedAt", datetime.now(timezone.utc).isoformat())
        meta.setdefault("generatedBy", "ma_yisheng_rule_workshop")
        meta.setdefault("caseId", vuln_case.get("case_id", ""))
        meta.setdefault("bestF1", best_f1)

    return {
        "rules": rules,
        "best_rule": best_rule,
        "best_f1": best_f1,
        "iterations": iterations_log,
        "evaluations": evaluations_log,
    }


def build_rule_pipeline_simple(vuln_case: Dict, provider: str = "deepseek",
                               model: Optional[str] = None,
                               api_key: Optional[str] = None) -> Optional[List[Dict]]:
    """
    快速模式：仅 Stage 1+2 + LLM 自评，不跑 YASA 扫描。
    用于没有测试集的场景或快速预览。
    """
    result = build_rule_pipeline(
        vuln_case, provider=provider, model=model, api_key=api_key,
        test_dirs=None, max_iterations=1,
    )
    return result["rules"] if result else None


def ingest_cves_to_rules(user_id: int, rule_set_id: int, ghsa_ids: List[str],
                         provider: str = "deepseek",
                         model: Optional[str] = None,
                         api_key: Optional[str] = None,
                         github_token: str = "",
                         on_progress=None) -> Dict[str, Any]:
    """
    Full pipeline: fetch CVE details → build vuln cases → generate rules → add to set.
    Returns summary dict.
    """
    results = {"generated": 0, "failed": 0, "details": []}

    for ghsa_id in ghsa_ids:
        if on_progress:
            on_progress("fetch", f"获取 {ghsa_id} 详情...")

        # Fetch detail (sync)
        detail = fetch_cve_detail_sync(ghsa_id, github_token)
        if not detail:
            results["details"].append({"ghsa_id": ghsa_id, "status": "fetch_failed"})
            results["failed"] += 1
            continue

        # Determine language from ecosystem
        vuln_list = detail.get("vulnerabilities", [])
        package_ecosystem = ""
        for v in vuln_list:
            pkg = v.get("package", {}) or {}
            package_ecosystem = (pkg.get("ecosystem") or "").lower()
            if package_ecosystem:
                break

        eco_lang_map = {"pip": "python", "maven": "java", "npm": "js", "go": "go", "composer": "php"}
        lang = eco_lang_map.get(package_ecosystem, "python")

        # Build vuln case
        vuln_case = {
            "case_id": ghsa_id,
            "language": lang,
            "vulnerability_type": _guess_vuln_type(detail),
            "source_code_before": "",
            "source_code_after": "",
            "source_function_hints": [],
            "sink_function_hints": [],
            "notes": detail.get("summary", ""),
            "summary": detail.get("description", ""),
            "cve_id": detail.get("cve_id", ""),
        }

        if on_progress:
            on_progress("generate", f"为 {ghsa_id} 生成规则...")

        # Run pipeline (快速模式，无测试集评估)
        try:
            result = build_rule_pipeline(vuln_case, provider, model, api_key,
                                         test_dirs=None, max_iterations=1)
            rules = result["rules"] if result else None
        except Exception as e:
            results["details"].append({
                "ghsa_id": ghsa_id, "status": "pipeline_failed",
                "error": str(e),
            })
            results["failed"] += 1
            continue

        if not rules:
            results["details"].append({
                "ghsa_id": ghsa_id, "status": "generation_failed",
            })
            results["failed"] += 1
            continue

        # Add to rule set
        if on_progress:
            on_progress("save", f"保存 {len(rules)} 条规则到规则集...")

        added = add_rules_to_set(user_id, rule_set_id, rules)
        results["details"].append({
            "ghsa_id": ghsa_id, "status": "ok",
            "rules_generated": len(rules), "rules_added": added,
            "cve_id": detail.get("cve_id", ""),
        })
        results["generated"] += added

    return results


def _guess_vuln_type(detail: Dict) -> str:
    """Guess vulnerability type from advisory summary/description/CWE."""
    text = (detail.get("summary", "") + " " + detail.get("description", "")).lower()
    # Also check CWE IDs embedded in the detail
    cwe_ids = []
    for cwe_obj in (detail.get("cwes") or []):
        if isinstance(cwe_obj, dict):
            cwe_ids.append((cwe_obj.get("cwe_id") or "").upper())
        elif isinstance(cwe_obj, str):
            cwe_ids.append(cwe_obj.upper())
    for identifier in (detail.get("identifiers") or []):
        if isinstance(identifier, dict) and identifier.get("type") == "CWE":
            cwe_ids.append((identifier.get("value") or "").upper())

    # CWE → type (high precision)
    cwe_map = {
        "CWE-89": "SQL Injection", "CWE-564": "SQL Injection",
        "CWE-943": "NoSQL Injection",
        "CWE-77": "Command Injection", "CWE-78": "Command Injection",
        "CWE-94": "Code Injection", "CWE-95": "Code Injection",
        "CWE-918": "SSRF",
        "CWE-22": "Path Traversal", "CWE-23": "Path Traversal",
        "CWE-29": "Path Traversal", "CWE-35": "Path Traversal",
        "CWE-36": "Path Traversal",
        "CWE-79": "XSS", "CWE-80": "XSS", "CWE-81": "XSS",
        "CWE-82": "XSS", "CWE-83": "XSS",
        "CWE-502": "Deserialization",
        "CWE-611": "XXE", "CWE-776": "XXE",
        "CWE-601": "Open Redirect",
        "CWE-1336": "Template Injection",
        "CWE-98": "File Inclusion", "CWE-73": "File Inclusion",
        "CWE-352": "CSRF",
        "CWE-1321": "Prototype Pollution", "CWE-915": "Prototype Pollution",
        "CWE-1333": "ReDoS",
        "CWE-200": "Information Disclosure", "CWE-201": "Information Disclosure",
        "CWE-287": "Authentication Bypass", "CWE-288": "Authentication Bypass",
        "CWE-862": "Authorization Bypass", "CWE-269": "Privilege Escalation",
        "CWE-117": "Log Injection", "CWE-93": "CRLF Injection",
        "CWE-434": "Unrestricted File Upload",
        "CWE-400": "Denial of Service", "CWE-770": "Denial of Service",
        "CWE-338": "Insecure Randomness", "CWE-330": "Insecure Randomness",
    }
    for cwe_id in cwe_ids:
        if cwe_id in cwe_map:
            return cwe_map[cwe_id]

    # Keyword fallback
    patterns = [
        ("SQL Injection", ["sql injection", "sqli"]),
        ("Command Injection", ["command injection", "os command injection", "shell injection"]),
        ("Code Injection", ["code injection", "arbitrary code execution", "remote code execution", "eval injection"]),
        ("SSRF", ["ssrf", "server-side request forgery"]),
        ("Path Traversal", ["path traversal", "directory traversal", "directory escape",
                            "arbitrary file read", "arbitrary file write", "zip slip"]),
        ("XSS", ["xss", "cross-site scripting", "cross site scripting"]),
        ("Deserialization", ["deserialization", "insecure deserial", "deserialize untrusted",
                              "pickle.", "unpickle", "yaml.load", "marshal.load", "readObject"]),
        ("XXE", ["xxe", "xml external entity"]),
        ("Open Redirect", ["open redirect", "url redirection"]),
        ("Template Injection", ["template injection", "ssti", "server-side template injection"]),
        ("File Inclusion", ["file inclusion", "lfi", "rfi", "local file inclusion"]),
        ("CSRF", ["csrf", "cross-site request forgery"]),
        ("Information Disclosure", ["information disclosure", "information leak", "data leak"]),
        ("Authentication Bypass", ["authentication bypass", "auth bypass"]),
        ("Authorization Bypass", ["authorization bypass", "privilege escalation"]),
        ("Log Injection", ["log injection", "crlf injection", "log forging"]),
        ("Prototype Pollution", ["prototype pollution", "__proto__"]),
        ("ReDoS", ["redos", "regular expression denial of service", "regex backtracking"]),
        ("Denial of Service", ["denial of service", "dos ", "resource exhaustion"]),
        ("NoSQL Injection", ["nosql injection"]),
        ("Unrestricted File Upload", ["unrestricted file upload", "arbitrary file upload"]),
        ("Insecure Randomness", ["insecure randomness", "weak random", "predictable random"]),
    ]
    for vuln_type, keywords in patterns:
        for kw in keywords:
            if kw in text:
                return vuln_type
    return "Uncategorized"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _rule_set_to_dict(rs: UserRuleSet) -> Dict:
    return {
        "id": rs.id,
        "user_id": rs.user_id,
        "name": rs.name,
        "description": rs.description,
        "source_type": rs.source_type,
        "lang": rs.lang,
        "scene": rs.scene,
        "is_active": bool(rs.is_active),
        "rule_count": rs.rule_count,
        "created_at": rs.created_at,
        "updated_at": rs.updated_at,
    }


def _user_rule_to_dict(ur: UserRule) -> Dict:
    return {
        "id": ur.id,
        "rule_set_id": ur.rule_set_id,
        "rule_id": ur.rule_id,
        "is_enabled": bool(ur.is_enabled),
        "rule_data": ur.rule_data,
        "created_at": ur.created_at,
    }
