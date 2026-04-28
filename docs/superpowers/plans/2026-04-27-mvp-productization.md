# SOC Triage AI MVP Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand SOC Triage AI from a CodePath final project into a portfolio-grade MVP with deterministic observable extraction, evidence traceability, enriched case packaging, uncertainty classification, evaluation dashboard, analyst overrides, retrieval debugging, and exports.

**Architecture:** Module-per-concern. Three new Python modules (`extractors.py`, `case_package.py`, `evaluation.py`) plus one surgical addition to `triage.py` (`triage_with_context()`). `app.py` is rewritten into a three-tab Streamlit dashboard (Triage / Evaluation / System). All retrieval, prompting, and corpus code remains frozen.

**Tech Stack:** Python 3.12, Streamlit, Anthropic SDK, sentence-transformers (already pinned). No new dependencies — observables use stdlib `re`; case packaging uses stdlib `uuid`/`datetime`/`json`.

**Frozen files (do not modify):** `rag/corpus.py`, `rag/retriever.py`, `data/threat_intel/*`, `tests/test_harness.py`, `model_card.md`.

---

## Task 1: extractors.py — observable extraction module

**Files:**
- Create: `extractors.py`
- Create: `tests/test_extractors.py`

- [ ] **Step 1.1: Write failing tests for IPv4 extraction**

Create `tests/test_extractors.py`:

```python
"""Tests for deterministic observable extraction."""
from extractors import extract_observables


def test_ipv4_basic():
    text = "Connection from 185.220.101.45 to internal host."
    result = extract_observables(text)
    assert result["ipv4"] == ["185.220.101.45"]


def test_ipv4_rejects_invalid_octet():
    text = "Bogus IP 999.999.999.999 in log."
    result = extract_observables(text)
    assert result["ipv4"] == []


def test_ipv4_dedupes():
    text = "Saw 10.0.0.1 then 10.0.0.1 again."
    result = extract_observables(text)
    assert result["ipv4"] == ["10.0.0.1"]
```

- [ ] **Step 1.2: Run tests, confirm they fail**

Run: `pytest tests/test_extractors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extractors'`

- [ ] **Step 1.3: Implement minimal extractors.py for IPv4**

Create `extractors.py`:

```python
"""Deterministic regex extraction of security observables from alert text.

Pure-function module. No state, no LLM calls, no network. Used as the first
stage of the triage pipeline so analysts get observable highlighting before
the LLM call returns.
"""
import re
from typing import Dict, List

OBSERVABLE_KEYS = [
    "ipv4", "email", "url", "domain", "md5", "sha1", "sha256",
    "registry_path", "process", "filename", "hostname", "username",
]

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _extract_ipv4(text: str) -> List[str]:
    out = []
    for m in _IPV4_RE.findall(text):
        octets = m.split(".")
        if all(0 <= int(o) <= 255 for o in octets):
            out.append(m)
    return out


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_observables(text: str) -> Dict[str, List[str]]:
    """Extract security observables from free-form alert text.

    Returns a dict with one key per observable type. Empty lists for
    unmatched types. All values deduplicated, order preserved.
    """
    if not text:
        return {k: [] for k in OBSERVABLE_KEYS}

    return {
        "ipv4": _dedupe(_extract_ipv4(text)),
        "email": [],
        "url": [],
        "domain": [],
        "md5": [],
        "sha1": [],
        "sha256": [],
        "registry_path": [],
        "process": [],
        "filename": [],
        "hostname": [],
        "username": [],
    }
```

- [ ] **Step 1.4: Run tests, confirm IPv4 tests pass**

Run: `pytest tests/test_extractors.py -v`
Expected: 3 passed.

- [ ] **Step 1.5: Add tests for emails, URLs, domains**

Append to `tests/test_extractors.py`:

```python
def test_email_basic():
    text = "Phish from ceo@anthrop1c.com requesting wire transfer."
    result = extract_observables(text)
    assert result["email"] == ["ceo@anthrop1c.com"]


def test_url_basic():
    text = "User clicked https://evil.com/login before reporting."
    result = extract_observables(text)
    assert result["url"] == ["https://evil.com/login"]


def test_url_strips_trailing_punctuation():
    text = "Visit https://example.com/page."
    result = extract_observables(text)
    assert result["url"] == ["https://example.com/page"]


def test_domain_excludes_email_and_url_domains():
    text = "Email from user@anthrop1c.com and click https://evil.com/x. Also seen: badguy.net."
    result = extract_observables(text)
    assert "anthrop1c.com" not in result["domain"]
    assert "evil.com" not in result["domain"]
    assert "badguy.net" in result["domain"]
```

- [ ] **Step 1.6: Run tests, confirm new tests fail**

Run: `pytest tests/test_extractors.py -v`
Expected: 3 pass, 4 fail.

- [ ] **Step 1.7: Implement email, URL, domain extractors**

Replace the placeholder body of `extract_observables` and add helpers. Update `extractors.py`:

```python
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b")
_TRAILING_PUNCT = ".,;:!?)]}"


def _extract_email(text: str) -> List[str]:
    return _EMAIL_RE.findall(text)


def _extract_url(text: str) -> List[str]:
    return [u.rstrip(_TRAILING_PUNCT) for u in _URL_RE.findall(text)]


def _extract_domain(text: str, exclude: set) -> List[str]:
    out = []
    for m in _DOMAIN_RE.findall(text):
        bare = m.rstrip(_TRAILING_PUNCT)
        if bare in exclude:
            continue
        if _IPV4_RE.fullmatch(bare):
            continue
        out.append(bare)
    return out
```

Then rewrite `extract_observables`:

```python
def extract_observables(text: str) -> Dict[str, List[str]]:
    if not text:
        return {k: [] for k in OBSERVABLE_KEYS}

    ipv4 = _dedupe(_extract_ipv4(text))
    emails = _dedupe(_extract_email(text))
    urls = _dedupe(_extract_url(text))

    domain_exclude = set()
    for e in emails:
        domain_exclude.add(e.split("@", 1)[1])
    for u in urls:
        m = re.match(r"https?://([^/]+)", u)
        if m:
            domain_exclude.add(m.group(1))

    domains = _dedupe(_extract_domain(text, domain_exclude))

    return {
        "ipv4": ipv4,
        "email": emails,
        "url": urls,
        "domain": domains,
        "md5": [],
        "sha1": [],
        "sha256": [],
        "registry_path": [],
        "process": [],
        "filename": [],
        "hostname": [],
        "username": [],
    }
```

- [ ] **Step 1.8: Run tests, confirm pass**

Run: `pytest tests/test_extractors.py -v`
Expected: 7 passed.

- [ ] **Step 1.9: Add tests for hashes, registry, process, filename**

Append:

```python
def test_md5_extracted():
    text = "Hash d41d8cd98f00b204e9800998ecf8427e seen in payload."
    result = extract_observables(text)
    assert result["md5"] == ["d41d8cd98f00b204e9800998ecf8427e"]


def test_sha1_extracted():
    text = "Sha1 da39a3ee5e6b4b0d3255bfef95601890afd80709 in IOC list."
    result = extract_observables(text)
    assert result["sha1"] == ["da39a3ee5e6b4b0d3255bfef95601890afd80709"]


def test_sha256_extracted():
    text = "Sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 logged."
    result = extract_observables(text)
    assert result["sha256"] == ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"]


def test_registry_path():
    text = r"Persistence at HKLM\Software\Microsoft\Windows\CurrentVersion\Run"
    result = extract_observables(text)
    assert any("HKLM" in p for p in result["registry_path"])


def test_process_priority_over_filename():
    text = "rundll32.exe loaded comsvcs.dll"
    result = extract_observables(text)
    assert "rundll32.exe" in result["process"]
    assert "comsvcs.dll" in result["process"]
    assert "rundll32.exe" not in result["filename"]


def test_filename_doc_extension():
    text = "Ransom note README.txt appeared."
    result = extract_observables(text)
    assert "README.txt" in result["filename"]
```

- [ ] **Step 1.10: Run tests, confirm new tests fail**

Run: `pytest tests/test_extractors.py -v`
Expected: 7 pass, 6 fail.

- [ ] **Step 1.11: Implement hash, registry, process, filename extractors**

Add to `extractors.py`:

```python
_MD5_RE = re.compile(r"\b[a-fA-F0-9]{32}\b")
_SHA1_RE = re.compile(r"\b[a-fA-F0-9]{40}\b")
_SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
_REGISTRY_RE = re.compile(r"HK(?:LM|CU|U|CR|CC)\\[A-Za-z0-9\\_\-\.]+")
_PROCESS_RE = re.compile(r"\b[A-Za-z0-9_\-]+\.(?:exe|dll|sys)\b", re.IGNORECASE)
_FILENAME_EXTS = ("txt", "pdf", "docx", "xlsx", "zip", "rar",
                  "iso", "img", "vhd", "lnk", "html")
_FILENAME_RE = re.compile(
    r"\b[A-Za-z0-9_\-\.]+\.(?:" + "|".join(_FILENAME_EXTS) + r")\b",
    re.IGNORECASE,
)


def _extract_md5(text: str) -> List[str]:
    out = []
    for m in _MD5_RE.findall(text):
        # Reject 32-char substrings of longer hex (sha1/sha256)
        if len(m) == 32:
            out.append(m)
    return out
```

Note: because `\b` boundaries in `_MD5_RE` won't match inside a longer hex run (no boundary between hex chars), but `re.findall` over a sha256 string would not produce a 32-char match anyway. Add a guard:

```python
def _extract_hashes(text: str):
    sha256s = _SHA256_RE.findall(text)
    sha1s = [h for h in _SHA1_RE.findall(text) if h not in "".join(sha256s)]
    md5s = [h for h in _MD5_RE.findall(text)
            if h not in "".join(sha256s) and h not in "".join(sha1s)]
    return md5s, sha1s, sha256s


def _extract_registry(text: str) -> List[str]:
    return _REGISTRY_RE.findall(text)


def _extract_process_and_filename(text: str):
    processes = _PROCESS_RE.findall(text)
    proc_set = {p.lower() for p in processes}
    filenames = [
        f for f in _FILENAME_RE.findall(text)
        if f.lower() not in proc_set
    ]
    return processes, filenames
```

Update `extract_observables` to call these and populate the dict:

```python
def extract_observables(text: str) -> Dict[str, List[str]]:
    if not text:
        return {k: [] for k in OBSERVABLE_KEYS}

    ipv4 = _dedupe(_extract_ipv4(text))
    emails = _dedupe(_extract_email(text))
    urls = _dedupe(_extract_url(text))

    domain_exclude = set()
    for e in emails:
        domain_exclude.add(e.split("@", 1)[1])
    for u in urls:
        m = re.match(r"https?://([^/]+)", u)
        if m:
            domain_exclude.add(m.group(1))

    domains = _dedupe(_extract_domain(text, domain_exclude))
    md5s, sha1s, sha256s = _extract_hashes(text)
    processes, filenames = _extract_process_and_filename(text)

    return {
        "ipv4": ipv4,
        "email": emails,
        "url": urls,
        "domain": domains,
        "md5": _dedupe(md5s),
        "sha1": _dedupe(sha1s),
        "sha256": _dedupe(sha256s),
        "registry_path": _dedupe(_extract_registry(text)),
        "process": _dedupe(processes),
        "filename": _dedupe(filenames),
        "hostname": [],
        "username": [],
    }
```

- [ ] **Step 1.12: Run tests, confirm pass**

Run: `pytest tests/test_extractors.py -v`
Expected: 13 passed.

- [ ] **Step 1.13: Add tests for hostname and username**

Append:

```python
def test_hostname_workstation_pattern():
    text = "Alert on workstation WKSTN-042 from user jsmith."
    result = extract_observables(text)
    assert "WKSTN-042" in result["hostname"]


def test_hostname_server_pattern():
    text = "Connections to srv-bastion-01 from external."
    result = extract_observables(text)
    assert "srv-bastion-01" in result["hostname"]


def test_username_after_context_word():
    text = "Employee jdoe downloaded 15GB of customer data."
    result = extract_observables(text)
    assert "jdoe" in result["username"]


def test_username_after_user_keyword():
    text = "User account is jsmith on the host."
    result = extract_observables(text)
    assert "jsmith" in result["username"]
```

- [ ] **Step 1.14: Run tests, confirm new tests fail**

Run: `pytest tests/test_extractors.py -v`
Expected: 13 pass, 4 fail.

- [ ] **Step 1.15: Implement hostname and username extractors**

Add to `extractors.py`:

```python
_HOSTNAME_RES = [
    re.compile(r"\bWKSTN-[A-Za-z0-9\-]+\b"),
    re.compile(r"\bsrv-[A-Za-z0-9\-]+\b"),
    re.compile(r"\bDC-[A-Za-z0-9\-]+\b"),
]
_USERNAME_RE = re.compile(
    r"(?:user(?:\s+account)?|account|employee|login)\s+(?:is\s+)?([A-Za-z][A-Za-z0-9_\-\.]{1,30})",
    re.IGNORECASE,
)


def _extract_hostname(text: str) -> List[str]:
    out = []
    for r in _HOSTNAME_RES:
        out.extend(r.findall(text))
    return out


def _extract_username(text: str) -> List[str]:
    return _USERNAME_RE.findall(text)
```

Update `extract_observables` to call them:

```python
        "hostname": _dedupe(_extract_hostname(text)),
        "username": _dedupe(_extract_username(text)),
```

- [ ] **Step 1.16: Run tests, confirm all pass**

Run: `pytest tests/test_extractors.py -v`
Expected: 17 passed.

- [ ] **Step 1.17: Smoke test on a real harness alert**

Run:
```bash
python -c "from extractors import extract_observables; import json; \
print(json.dumps(extract_observables('EDR detected suspicious access to LSASS process memory by rundll32.exe with comsvcs.dll on workstation WKSTN-042. User account is jsmith. Process tree: cmd.exe -> rundll32.exe.'), indent=2))"
```
Expected: `process` contains `rundll32.exe`, `comsvcs.dll`, `cmd.exe`; `hostname` contains `WKSTN-042`; `username` contains `jsmith`.

- [ ] **Step 1.18: Commit**

```bash
git add extractors.py tests/test_extractors.py
git commit -m "Add deterministic observable extraction module"
```

---

## Task 2: case_package.py — case envelope and uncertainty modes

**Files:**
- Create: `case_package.py`
- Create: `tests/test_case_package.py`

- [ ] **Step 2.1: Write failing tests for case_id, schema shape, version block**

Create `tests/test_case_package.py`:

```python
"""Tests for case package envelope builder."""
import re
from case_package import build_case_package, derive_uncertainty_mode


def _triage_stub(severity="high", confidence="high"):
    return {
        "severity": severity,
        "confidence": confidence,
        "mitre_techniques": ["T1078"],
        "summary": "stub",
        "recommended_actions": ["a"],
        "escalate": True,
        "reasoning": "r",
        "sources": ["insider_threat.md"],
        "retrieval_score": 0.5,
    }


def test_case_id_format():
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), [], False)
    assert re.match(r"^SOC-\d{8}-[a-f0-9]{4}$", pkg["case_id"])


def test_top_level_keys_present():
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), [], False)
    expected_keys = {
        "case_id", "timestamp", "alert_raw", "observables", "triage",
        "evidence", "uncertainty_mode", "guardrail_triggered",
        "analyst_overrides", "version",
    }
    assert expected_keys.issubset(pkg.keys())


def test_version_block_fields():
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), [], False)
    v = pkg["version"]
    for key in ["model", "embeddings", "corpus_chunks",
                "prompt_version", "top_k", "min_similarity"]:
        assert key in v


def test_evidence_block_aggregates_chunks():
    hits = [
        ({"id": "ins_1", "source": "insider_threat.md", "text": "x"}, 0.6),
        ({"id": "ins_2", "source": "insider_threat.md", "text": "y"}, 0.4),
    ]
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), hits, False)
    e = pkg["evidence"]
    assert len(e["chunks_retrieved"]) == 2
    assert e["sources_cited"] == ["insider_threat.md"]
    assert abs(e["avg_retrieval_score"] - 0.5) < 1e-6


def test_evidence_marks_cited_chunks():
    triage = _triage_stub()
    triage["sources"] = ["insider_threat.md"]
    hits = [
        ({"id": "ins_1", "source": "insider_threat.md", "text": "x"}, 0.5),
        ({"id": "phi_1", "source": "phishing.md", "text": "y"}, 0.4),
    ]
    pkg = build_case_package("alert", {}, triage, hits, False)
    chunks = pkg["evidence"]["chunks_retrieved"]
    cited_map = {c["chunk_id"]: c["cited"] for c in chunks}
    assert cited_map["ins_1"] is True
    assert cited_map["phi_1"] is False
```

- [ ] **Step 2.2: Run tests, confirm fail**

Run: `pytest tests/test_case_package.py -v`
Expected: ImportError (case_package not found).

- [ ] **Step 2.3: Implement case_package.py minimal skeleton**

Create `case_package.py`:

```python
"""Case envelope builder + uncertainty mode derivation.

Wraps existing triage output, observables, and retrieval metadata into a
complete case package. Pure deterministic logic; no LLM calls.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# Version metadata — single source of truth for the System tab and exports
VERSION_META = {
    "model": "claude-sonnet-4-5",
    "embeddings": "all-MiniLM-L6-v2",
    "corpus_chunks": 109,
    "prompt_version": "1.0",
    "top_k": 4,
    "min_similarity": 0.20,
}


def _new_case_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"SOC-{today}-{uuid.uuid4().hex[:4]}"


def derive_uncertainty_mode(
    triage_result: Dict,
    avg_retrieval_score: float,
    guardrail_triggered: bool,
) -> str:
    """Classify case into one of four uncertainty modes. First match wins."""
    severity = triage_result.get("severity", "informational")
    confidence = triage_result.get("confidence", "low")

    if severity == "informational" and guardrail_triggered:
        return "out_of_scope"
    if avg_retrieval_score < 0.25 and severity != "informational":
        return "insufficient_evidence"
    if confidence == "low" or (
        confidence == "medium" and avg_retrieval_score < 0.35
    ):
        return "needs_more_context"
    return "actionable"


def build_case_package(
    alert_raw: str,
    observables: Dict,
    triage_result: Dict,
    retrieval_hits: List[Tuple[Dict, float]],
    guardrail_triggered: bool,
) -> Dict:
    """Assemble full case package. Pure function, no side effects."""
    if retrieval_hits:
        avg_score = sum(s for _, s in retrieval_hits) / len(retrieval_hits)
    else:
        avg_score = 0.0

    cited_sources = set(triage_result.get("sources", []))
    chunks = [
        {
            "chunk_id": chunk["id"],
            "source": chunk["source"],
            "score": round(score, 3),
            "text": chunk["text"],
            "cited": chunk["source"] in cited_sources,
        }
        for chunk, score in retrieval_hits
    ]

    sources_cited = sorted(cited_sources)

    uncertainty = derive_uncertainty_mode(
        triage_result, avg_score, guardrail_triggered
    )

    return {
        "case_id": _new_case_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "alert_raw": alert_raw,
        "observables": observables,
        "triage": {k: v for k, v in triage_result.items()
                   if k not in ("sources", "retrieval_score")},
        "evidence": {
            "chunks_retrieved": chunks,
            "avg_retrieval_score": round(avg_score, 3),
            "sources_cited": sources_cited,
        },
        "uncertainty_mode": uncertainty,
        "guardrail_triggered": guardrail_triggered,
        "analyst_overrides": [],
        "version": dict(VERSION_META),
    }
```

- [ ] **Step 2.4: Run tests, confirm pass**

Run: `pytest tests/test_case_package.py -v`
Expected: 5 passed.

- [ ] **Step 2.5: Add tests for uncertainty mode derivation**

Append to `tests/test_case_package.py`:

```python
def test_uncertainty_actionable_default():
    t = _triage_stub(severity="high", confidence="high")
    assert derive_uncertainty_mode(t, 0.5, False) == "actionable"


def test_uncertainty_out_of_scope():
    t = _triage_stub(severity="informational", confidence="low")
    assert derive_uncertainty_mode(t, 0.0, True) == "out_of_scope"


def test_uncertainty_insufficient_evidence():
    t = _triage_stub(severity="high", confidence="high")
    assert derive_uncertainty_mode(t, 0.10, False) == "insufficient_evidence"


def test_uncertainty_needs_more_context_low_conf():
    t = _triage_stub(severity="medium", confidence="low")
    assert derive_uncertainty_mode(t, 0.50, False) == "needs_more_context"


def test_uncertainty_needs_more_context_medium_conf_low_score():
    t = _triage_stub(severity="medium", confidence="medium")
    assert derive_uncertainty_mode(t, 0.30, False) == "needs_more_context"


def test_uncertainty_priority_out_of_scope_beats_insufficient():
    t = _triage_stub(severity="informational", confidence="low")
    assert derive_uncertainty_mode(t, 0.10, True) == "out_of_scope"
```

- [ ] **Step 2.6: Run tests, confirm pass**

Run: `pytest tests/test_case_package.py -v`
Expected: 11 passed (no impl changes needed; logic already in place).

If any fail, fix the priority ordering in `derive_uncertainty_mode` and re-run.

- [ ] **Step 2.7: Commit**

```bash
git add case_package.py tests/test_case_package.py
git commit -m "Add case envelope builder with uncertainty mode derivation"
```

---

## Task 3: triage.py — add triage_with_context() without breaking harness

**Files:**
- Modify: `triage.py` (add method, refactor shared logic)

- [ ] **Step 3.1: Read current triage() implementation**

Read `triage.py:77-130`. Note that all logic from input validation through guardrail-on-no-hits, retrieval, prompt assembly, LLM call, parse, validate, and error fallback lives in one method.

- [ ] **Step 3.2: Refactor — extract shared core into _run_triage()**

In `triage.py`, replace the `triage()` method (lines 77-130) with:

```python
    def triage(self, alert: str) -> Dict[str, Any]:
        """Triage a security alert. Returns structured JSON dict."""
        result, _, _ = self._run_triage(alert)
        return result

    def triage_with_context(
        self, alert: str
    ) -> tuple[Dict[str, Any], list, bool]:
        """Like triage() but also returns retrieval hits and guardrail flag.

        Used by case_package.py to build full case envelopes. The existing
        triage() return signature is preserved for the reliability harness.
        """
        return self._run_triage(alert)

    def _run_triage(
        self, alert: str
    ) -> tuple[Dict[str, Any], list, bool]:
        """Shared core. Returns (result_dict, retrieval_hits, guardrail_triggered)."""
        if not alert or not alert.strip():
            return (
                self._guardrail_response(
                    "Empty alert input", retrieval_score=0.0, sources=[]
                ),
                [],
                True,
            )

        hits = self.retriever.retrieve(alert, top_k=4)

        if not hits:
            logger.warning(f"No corpus matches for alert: {alert[:100]}")
            return (
                self._guardrail_response(
                    "No matching threat intelligence found. Manual review required.",
                    retrieval_score=0.0,
                    sources=[],
                ),
                [],
                True,
            )

        context = "\n\n".join(
            f"[Source: {chunk['source']} | Similarity: {score:.2f}]\n{chunk['text']}"
            for chunk, score in hits
        )
        avg_score = sum(s for _, s in hits) / len(hits)
        sources = list({chunk["source"] for chunk, _ in hits})

        prompt = TRIAGE_PROMPT.format(context=context, alert=alert)

        raw = ""
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            parsed = self._parse_json(raw)
            self._validate_schema(parsed)
            parsed["sources"] = sources
            parsed["retrieval_score"] = round(avg_score, 3)
            return parsed, hits, False

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}. Raw: {raw[:300]}")
            return (
                self._guardrail_response(
                    "LLM produced malformed JSON",
                    retrieval_score=avg_score,
                    sources=sources,
                ),
                hits,
                True,
            )
        except Exception as e:
            logger.error(f"Triage failed: {type(e).__name__}: {e}")
            return (
                self._guardrail_response(
                    f"System error: {type(e).__name__}",
                    retrieval_score=avg_score,
                    sources=sources,
                ),
                hits,
                True,
            )
```

- [ ] **Step 3.3: Sanity check — import triage in REPL**

Run:
```bash
python -c "from triage import SOCTriage; print('import ok'); t = SOCTriage(); print('init ok')"
```
Expected: `import ok` then `init ok` (corpus indexes, no errors).

- [ ] **Step 3.4: Run reliability harness — must stay 7/7**

Run: `python -m tests.test_harness`
Expected: `Passed: 7/7`. If any test fails, do NOT proceed — investigate the refactor for behavior drift in `triage()`.

- [ ] **Step 3.5: Smoke-test triage_with_context**

Run:
```bash
python -c "
from triage import SOCTriage
t = SOCTriage()
result, hits, guardrail = t.triage_with_context('rundll32.exe accessing LSASS on WKSTN-042')
print('severity:', result['severity'])
print('hits:', len(hits))
print('guardrail:', guardrail)
"
```
Expected: severity is `critical` or `high`, `hits` length > 0, guardrail is `False`.

- [ ] **Step 3.6: Commit**

```bash
git add triage.py
git commit -m "Add triage_with_context() exposing retrieval hits and guardrail flag"
```

---

## Task 4: evaluation.py — harness loader, live runner, metrics

**Files:**
- Create: `evaluation.py`
- Create: `tests/test_evaluation.py`

- [ ] **Step 4.1: Write failing tests for load and metrics**

Create `tests/test_evaluation.py`:

```python
"""Tests for evaluation results loader and metrics derivation."""
import json
from pathlib import Path
import pytest
from evaluation import (
    load_harness_results,
    compute_eval_metrics,
)


def _write_results(tmp_path, payload):
    p = tmp_path / "harness_results.json"
    p.write_text(json.dumps(payload))
    return str(p)


def test_load_returns_none_when_missing():
    assert load_harness_results("does/not/exist.json") is None


def test_load_returns_results_when_present(tmp_path):
    payload = [{"id": "T1", "passed": True}]
    path = _write_results(tmp_path, payload)
    out = load_harness_results(path)
    assert out["results"] == payload


def test_compute_metrics_pass_rate():
    results = [
        {"id": "T1", "passed": True, "checks": {}, "severity": "high",
         "retrieval_score": 0.5, "latency_seconds": 8.0},
        {"id": "T2", "passed": False, "checks": {}, "severity": "low",
         "retrieval_score": 0.3, "latency_seconds": 9.0},
    ]
    m = compute_eval_metrics(results)
    assert m["total"] == 2
    assert m["passed"] == 1
    assert m["pass_rate"] == 0.5
    assert m["avg_retrieval_score"] == 0.4
    assert m["avg_latency"] == 8.5


def test_compute_metrics_per_check_accuracy():
    results = [
        {"id": "T1", "passed": True,
         "checks": {"severity_match": True, "escalate_match": True,
                    "techniques_match": True, "retrieval_score_ok": True}},
        {"id": "T2", "passed": False,
         "checks": {"severity_match": False, "escalate_match": True,
                    "techniques_match": True, "retrieval_score_ok": True}},
    ]
    m = compute_eval_metrics(results)
    assert m["severity_accuracy"] == 0.5
    assert m["escalation_accuracy"] == 1.0
```

- [ ] **Step 4.2: Run tests, confirm they fail**

Run: `pytest tests/test_evaluation.py -v`
Expected: ImportError (evaluation module does not exist).

- [ ] **Step 4.3: Implement evaluation.py**

Create `evaluation.py`:

```python
"""Bridge between the CLI test harness and the Streamlit evaluation tab.

Two modes:
  - load_harness_results: read existing tests/harness_results.json
  - run_harness_live: execute all TEST_CASES against a live triage engine

Metrics derivation is shared between both paths.
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from tests.test_harness import TEST_CASES, evaluate_case


def load_harness_results(
    path: str = "tests/harness_results.json",
) -> Optional[Dict]:
    """Load and parse harness results from disk.

    Returns dict {"results": [...]} or None if file missing/empty.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    if not data:
        return None
    return {"results": data}


def run_harness_live(triage_engine) -> Dict:
    """Execute all TEST_CASES against a live triage engine.

    Returns the same shape as load_harness_results: {"results": [...]}.
    Does not write to disk.
    """
    results: List[Dict] = []
    for case in TEST_CASES:
        case_start = time.time()
        try:
            result = triage_engine.triage(case["alert"])
            evaluation = evaluate_case(result, case)
            elapsed = time.time() - case_start
            results.append({
                "id": case["id"],
                "alert_excerpt": case["alert"][:100],
                "severity": result["severity"],
                "confidence": result["confidence"],
                "escalate": result["escalate"],
                "techniques": result.get("mitre_techniques", []),
                "retrieval_score": result.get("retrieval_score"),
                "sources": result.get("sources", []),
                "passed": evaluation["passed"],
                "checks": evaluation["checks"],
                "latency_seconds": round(elapsed, 2),
            })
        except Exception as e:
            results.append({
                "id": case["id"],
                "passed": False,
                "error": f"{type(e).__name__}: {e}",
            })
    return {"results": results}


def compute_eval_metrics(results: List[Dict]) -> Dict:
    """Derive dashboard metrics from raw results."""
    total = len(results)
    if total == 0:
        return {"total": 0, "passed": 0, "pass_rate": 0.0}

    passed = sum(1 for r in results if r.get("passed"))

    def _check_rate(key: str) -> Optional[float]:
        applicable = [r for r in results if "checks" in r and key in r["checks"]]
        if not applicable:
            return None
        hits = sum(1 for r in applicable if r["checks"][key])
        return round(hits / len(applicable), 3)

    scores = [r.get("retrieval_score") for r in results
              if r.get("retrieval_score") is not None]
    latencies = [r.get("latency_seconds") for r in results
                 if r.get("latency_seconds") is not None]

    metrics = {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3),
        "severity_accuracy": _check_rate("severity_match"),
        "escalation_accuracy": _check_rate("escalate_match"),
        "techniques_accuracy": _check_rate("techniques_match"),
        "retrieval_threshold_rate": _check_rate("retrieval_score_ok"),
        "avg_retrieval_score": (
            round(sum(scores) / len(scores), 3) if scores else 0.0
        ),
        "avg_latency": (
            round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        ),
        "per_case": results,
    }
    return metrics
```

- [ ] **Step 4.4: Run tests, confirm pass**

Run: `pytest tests/test_evaluation.py -v`
Expected: 4 passed.

- [ ] **Step 4.5: Verify load on real harness output**

Run:
```bash
python -c "
from evaluation import load_harness_results, compute_eval_metrics
data = load_harness_results()
m = compute_eval_metrics(data['results'])
print('total:', m['total'], 'passed:', m['passed'], 'pass_rate:', m['pass_rate'])
print('severity_acc:', m['severity_accuracy'])
print('avg_latency:', m['avg_latency'])
"
```
Expected: total 7, passed 7, pass_rate 1.0, severity_accuracy 1.0.

- [ ] **Step 4.6: Commit**

```bash
git add evaluation.py tests/test_evaluation.py
git commit -m "Add evaluation module: harness loader, live runner, metrics"
```

---

## Task 5: app.py — three-tab Streamlit rewrite

**Files:**
- Modify: `app.py` (full rewrite, preserve CSS + sample alerts)

- [ ] **Step 5.1: Read existing app.py CSS block (lines 18-106) — preserve verbatim**

The existing dark dashboard CSS is good. Reuse it as the foundation. New CSS rules for observable pills, uncertainty badges, override indicators, and cited markers extend (not replace) it.

- [ ] **Step 5.2: Plan session state and helper layout**

The new app.py is structured as:
1. Imports + page config
2. CSS block (existing + extensions)
3. `@st.cache_resource` engine loader
4. SAMPLES dict (existing)
5. Helper functions: `sev_badge`, `tech_pills`, `src_pills`, `obs_pills`, `uncertainty_badge`
6. Session state init
7. Sidebar render
8. Tab dispatch — `st.tabs(["Triage", "Evaluation", "System"])`
9. `render_triage_tab(engine)`
10. `render_evaluation_tab(engine)`
11. `render_system_tab(engine)`

- [ ] **Step 5.3: Rewrite app.py header, CSS, helpers**

Replace the entire contents of `app.py`:

```python
"""SOC Triage AI — Streamlit dashboard. Three tabs: Triage / Evaluation / System."""
import json
import os
os.environ["TQDM_DISABLE"] = "1"

from datetime import datetime, timezone

import streamlit as st

from triage import SOCTriage
from extractors import extract_observables
from case_package import build_case_package, VERSION_META
from evaluation import (
    load_harness_results,
    run_harness_live,
    compute_eval_metrics,
)
from rag.corpus import load_corpus

st.set_page_config(
    page_title="SOC Triage AI",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}

    .title {font-size: 1.5rem; font-weight: 700; color: #e2e8f0;
            letter-spacing: -0.01em; margin-bottom: 0.1rem;}
    .subtitle {font-size: 0.82rem; color: #64748b; margin-bottom: 1.2rem;}

    .sev {padding: 0.25rem 0.65rem; border-radius: 3px; font-weight: 700;
          font-size: 0.78rem; letter-spacing: 0.5px; display: inline-block;
          text-transform: uppercase;}
    .sev-critical    {background:#991b1b; color:#fecaca;}
    .sev-high        {background:#9a3412; color:#fed7aa;}
    .sev-medium      {background:#854d0e; color:#fef08a;}
    .sev-low         {background:#166534; color:#bbf7d0;}
    .sev-informational {background:#334155; color:#cbd5e1;}

    .m-card {background: #0f172a; border: 1px solid #1e293b; border-radius: 6px;
             padding: 0.65rem 0.85rem;}
    .m-card .lbl {font-size: 0.65rem; color: #475569; text-transform: uppercase;
                  letter-spacing: 0.8px; margin-bottom: 0.3rem;}
    .m-card .val {font-size: 1.05rem; font-weight: 600; color: #e2e8f0;}

    .tt {background: #172554; color: #93c5fd; padding: 0.18rem 0.5rem;
         border-radius: 3px; font-family: 'SF Mono','Fira Code',monospace;
         font-size: 0.8rem; font-weight: 500; margin: 0 0.3rem 0.3rem 0;
         display: inline-block;}
    .st {background: #0f172a; border: 1px solid #1e293b; color: #94a3b8;
         padding: 0.15rem 0.4rem; border-radius: 3px; font-family: monospace;
         font-size: 0.75rem; margin: 0 0.25rem 0.25rem 0; display: inline-block;}

    /* observable pills, color-coded by group */
    .obs {padding: 0.18rem 0.5rem; border-radius: 3px;
          font-family: 'SF Mono', monospace; font-size: 0.75rem;
          margin: 0 0.25rem 0.25rem 0; display: inline-block; font-weight: 500;}
    .obs-net  {background: #064e3b; color: #6ee7b7;}
    .obs-host {background: #1e3a8a; color: #93c5fd;}
    .obs-hash {background: #581c87; color: #d8b4fe;}
    .obs-id   {background: #78350f; color: #fcd34d;}

    /* uncertainty mode badges */
    .uncert {padding: 0.22rem 0.55rem; border-radius: 3px; font-weight: 600;
             font-size: 0.72rem; letter-spacing: 0.5px; display: inline-block;
             text-transform: uppercase;}
    .uncert-actionable           {background:#166534; color:#bbf7d0;}
    .uncert-needs_more_context   {background:#854d0e; color:#fef08a;}
    .uncert-insufficient_evidence{background:#9a3412; color:#fed7aa;}
    .uncert-out_of_scope         {background:#334155; color:#cbd5e1;}

    .cited {color: #34d399; font-weight: 700;}
    .uncited {color: #475569;}

    .reasoning {background: #0f172a; border-left: 3px solid #2563eb;
                color: #cbd5e1; padding: 0.85rem 1rem; border-radius: 0 4px 4px 0;
                font-size: 0.88rem; line-height: 1.55;}

    .sec {font-size: 0.68rem; font-weight: 600; color: #475569;
          text-transform: uppercase; letter-spacing: 0.8px;
          margin: 1rem 0 0.4rem 0;}

    .esc-yes {color: #ef4444; font-weight: 700; font-size: 1.05rem;}
    .esc-no  {color: #475569; font-weight: 500; font-size: 1.05rem;}

    .empty {background: #0f172a; border: 1px dashed #1e293b; color: #334155;
            padding: 2.5rem; border-radius: 6px; text-align: center;
            font-size: 0.85rem;}

    .sb-title {font-size: 1rem; font-weight: 700; color: #e2e8f0;}
    .sb-meta {font-size: 0.72rem; color: #475569; line-height: 1.7;}

    .stTextArea textarea {font-family: 'SF Mono','Fira Code',monospace;
                          font-size: 0.88rem;}

    .override {background: #1e293b; color: #fde68a; padding: 0.15rem 0.4rem;
               border-radius: 3px; font-size: 0.7rem; font-weight: 600;
               margin-left: 0.4rem; text-transform: uppercase;
               letter-spacing: 0.5px;}
</style>
""", unsafe_allow_html=True)


# --- Engine -----------------------------------------------------------------
@st.cache_resource
def load_triage():
    return SOCTriage()


@st.cache_resource
def cached_corpus():
    return load_corpus()


# --- Static content ---------------------------------------------------------
SAMPLES = {
    "Active ransomware": (
        "Multiple file servers showing thousands of file modifications per minute. "
        "Files renamed with .lockbit extension. README.txt ransom notes appearing "
        "in every directory. Volume Shadow Copies deleted via vssadmin 30 minutes ago."
    ),
    "LSASS credential dump": (
        "EDR detected suspicious access to LSASS process memory by rundll32.exe "
        "with comsvcs.dll on workstation WKSTN-042. User account is jsmith. "
        "Process tree: cmd.exe -> rundll32.exe."
    ),
    "Phishing + credential entry": (
        "User reported email from ceo@anthrop1c.com (note typo) requesting "
        "urgent wire transfer to new vendor. User clicked link and entered "
        "credentials before reporting. Email contained urgency language."
    ),
    "SSH brute force (Tor exit)": (
        "5000 failed SSH authentication attempts in last 10 minutes against "
        "host srv-bastion-01 from source IP 185.220.101.45 (known Tor exit). "
        "No successful authentications observed yet."
    ),
    "Insider data exfiltration": (
        "Employee jdoe (resignation notice given last week) downloaded 15GB of "
        "customer data from CRM in last 24 hours. Login from new device "
        "fingerprint. Email forwarding rule created to personal Gmail yesterday."
    ),
    "Gibberish (guardrail test)": (
        "asdfqwerzxcv 1234567890 lorem ipsum dolor sit amet"
    ),
}

OBS_GROUPS = {
    "ipv4": "obs-net", "url": "obs-net", "domain": "obs-net", "email": "obs-net",
    "hostname": "obs-host", "process": "obs-host", "filename": "obs-host",
    "registry_path": "obs-host",
    "md5": "obs-hash", "sha1": "obs-hash", "sha256": "obs-hash",
    "username": "obs-id",
}


# --- Helpers ----------------------------------------------------------------
def sev_badge(s):
    return f'<span class="sev sev-{s}">{s}</span>'


def tech_pills(ts):
    if not ts:
        return '<span style="color:#475569;font-size:0.82rem;">None identified</span>'
    return "".join(f'<span class="tt">{t}</span>' for t in ts)


def src_pills(ss):
    if not ss:
        return '<span style="color:#475569;font-size:0.82rem;">N/A</span>'
    return "".join(f'<span class="st">{s}</span>' for s in ss)


def obs_pills(observables):
    parts = []
    for k in ["ipv4", "url", "domain", "email", "hostname",
              "process", "filename", "registry_path",
              "md5", "sha1", "sha256", "username"]:
        for v in observables.get(k, []):
            cls = OBS_GROUPS.get(k, "obs-host")
            parts.append(
                f'<span class="obs {cls}" title="{k}">{v}</span>'
            )
    if not parts:
        return '<span style="color:#475569;font-size:0.82rem;">No observables extracted</span>'
    return "".join(parts)


def uncertainty_badge(mode):
    return f'<span class="uncert uncert-{mode}">{mode.replace("_", " ")}</span>'


def case_to_markdown(case):
    """Render case package as analyst-readable markdown."""
    t = case["triage"]
    lines = [
        f"# SOC Triage Case: {case['case_id']}",
        f"_Generated: {case['timestamp']}_",
        "",
        f"**Severity:** {t['severity'].upper()} &nbsp; "
        f"**Confidence:** {t['confidence'].upper()} &nbsp; "
        f"**Escalate:** {'YES' if t['escalate'] else 'NO'} &nbsp; "
        f"**Mode:** {case['uncertainty_mode']}",
        "",
        "## Alert",
        "```",
        case["alert_raw"],
        "```",
        "",
        "## Summary",
        t["summary"],
        "",
        "## MITRE ATT&CK Techniques",
    ]
    lines.extend(f"- {tech}" for tech in t["mitre_techniques"]) if t["mitre_techniques"] \
        else lines.append("_None identified_")
    lines.extend(["", "## Recommended Actions"])
    lines.extend(f"{i}. {a}" for i, a in enumerate(t["recommended_actions"], 1))
    lines.extend(["", "## Reasoning", t["reasoning"], "", "## Observables"])
    for k, vals in case["observables"].items():
        if vals:
            lines.append(f"- **{k}:** {', '.join(vals)}")
    lines.extend(["", "## Evidence",
                  f"- Avg retrieval score: {case['evidence']['avg_retrieval_score']}",
                  f"- Sources cited: {', '.join(case['evidence']['sources_cited']) or 'None'}"])
    if case["analyst_overrides"]:
        lines.extend(["", "## Analyst Overrides"])
        for o in case["analyst_overrides"]:
            lines.append(f"- **{o['field']}**: {o['original']} → {o['override']} ({o['rationale']})")
    return "\n".join(lines)
```

- [ ] **Step 5.4: Add session state init and sidebar**

Append to `app.py`:

```python
# --- Session state ----------------------------------------------------------
for key, default in [
    ("alert_input", ""),
    ("current_case", None),
    ("analyst_overrides", []),
    ("eval_data", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# --- Sidebar ----------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sb-title">SOC Triage AI</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown('<div class="sec">Sample alerts</div>', unsafe_allow_html=True)
    for label, text in SAMPLES.items():
        if st.button(label, use_container_width=True, key=f"s_{label}"):
            st.session_state.alert_input = text
            st.session_state.current_case = None
            st.session_state.analyst_overrides = []
            st.rerun()
    st.divider()
    st.markdown(
        '<div class="sb-meta">'
        f"Model &nbsp;{VERSION_META['model']}<br>"
        f"Embeddings &nbsp;{VERSION_META['embeddings']}<br>"
        f"Corpus &nbsp;{VERSION_META['corpus_chunks']} chunks<br>"
        f"Top-k &nbsp;{VERSION_META['top_k']} &nbsp;|&nbsp; "
        f"Min sim &nbsp;{VERSION_META['min_similarity']}"
        "</div>",
        unsafe_allow_html=True,
    )


# --- Header -----------------------------------------------------------------
st.markdown('<div class="title">SOC Triage AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Tier-1 alert triage &middot; MITRE ATT&CK grounded</div>',
    unsafe_allow_html=True,
)

with st.spinner("Indexing corpus..."):
    engine = load_triage()
```

- [ ] **Step 5.5: Add Triage tab renderer**

Append to `app.py`:

```python
# --- Triage tab -------------------------------------------------------------
def render_triage_tab(engine):
    alert_text = st.text_area(
        "Alert input",
        height=120,
        placeholder="Paste a raw alert from your SIEM, EDR, or SOAR platform...",
        label_visibility="collapsed",
        key="alert_input",
    )

    col_btn, _ = st.columns([1, 5])
    with col_btn:
        run = st.button(
            "Run Triage", type="primary", use_container_width=True,
            disabled=not alert_text.strip(),
        )

    if alert_text.strip():
        observables = extract_observables(alert_text)
        st.markdown('<div class="sec">Observables extracted (deterministic)</div>',
                    unsafe_allow_html=True)
        st.markdown(obs_pills(observables), unsafe_allow_html=True)

    if run and alert_text.strip():
        with st.spinner("Analyzing..."):
            triage_result, hits, guardrail = engine.triage_with_context(alert_text)
        case = build_case_package(
            alert_text, observables, triage_result, hits, guardrail,
        )
        st.session_state.current_case = case
        st.session_state.analyst_overrides = []

    case = st.session_state.current_case
    if case is None:
        st.markdown(
            '<div class="empty">Paste an alert or pick a sample from the sidebar.</div>',
            unsafe_allow_html=True,
        )
        return

    t = case["triage"]
    overrides = st.session_state.analyst_overrides
    override_field = {o["field"]: o for o in overrides}

    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ovr_sev = override_field.get("severity")
        sev_html = sev_badge(ovr_sev["override"]) if ovr_sev else sev_badge(t["severity"])
        suffix = '<span class="override">override</span>' if ovr_sev else ""
        st.markdown(
            f'<div class="m-card"><div class="lbl">Severity</div>{sev_html}{suffix}</div>',
            unsafe_allow_html=True,
        )
    with c2:
        ovr_esc = override_field.get("escalate")
        esc_val = ovr_esc["override"] if ovr_esc else t["escalate"]
        cls = "esc-yes" if esc_val else "esc-no"
        txt = "YES — escalate" if esc_val else "NO"
        suffix = '<span class="override">override</span>' if ovr_esc else ""
        st.markdown(
            f'<div class="m-card"><div class="lbl">Escalate</div>'
            f'<div class="{cls}">{txt}</div>{suffix}</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="m-card"><div class="lbl">Confidence</div>'
            f'<div class="val">{t["confidence"].upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="m-card"><div class="lbl">Uncertainty</div>'
            f'{uncertainty_badge(case["uncertainty_mode"])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sec">Summary</div>', unsafe_allow_html=True)
    st.info(t["summary"])

    left, right = st.columns([3, 2])
    with left:
        st.markdown('<div class="sec">Recommended actions</div>', unsafe_allow_html=True)
        for i, a in enumerate(t["recommended_actions"], 1):
            st.markdown(f"{i}. {a}")
        st.markdown('<div class="sec">Reasoning</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="reasoning">{t["reasoning"]}</div>',
                    unsafe_allow_html=True)
    with right:
        st.markdown('<div class="sec">MITRE ATT&CK</div>', unsafe_allow_html=True)
        st.markdown(tech_pills(t["mitre_techniques"]), unsafe_allow_html=True)
        st.markdown('<div class="sec">Sources</div>', unsafe_allow_html=True)
        st.markdown(src_pills(case["evidence"]["sources_cited"]),
                    unsafe_allow_html=True)
        st.markdown(
            f'<div class="sec">Avg retrieval &nbsp; '
            f'<span class="val">{case["evidence"]["avg_retrieval_score"]}</span></div>',
            unsafe_allow_html=True,
        )

    # Evidence traceability
    with st.expander("Evidence — retrieved chunks"):
        for c in case["evidence"]["chunks_retrieved"]:
            cited = '<span class="cited">cited</span>' if c["cited"] \
                else '<span class="uncited">not cited</span>'
            st.markdown(
                f"**{c['chunk_id']}** &middot; `{c['source']}` &middot; "
                f"score `{c['score']:.3f}` &middot; {cited}",
                unsafe_allow_html=True,
            )
            st.code(c["text"][:600], language="text")

    # Analyst overrides
    with st.expander("Analyst override"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            new_sev = st.selectbox(
                "Override severity",
                ["(no override)", "critical", "high", "medium", "low", "informational"],
                key="ovr_sev_select",
            )
        with col_b:
            new_esc = st.selectbox(
                "Override escalation",
                ["(no override)", "True", "False"],
                key="ovr_esc_select",
            )
        with col_c:
            rationale = st.text_input("Rationale", key="ovr_rationale")

        if st.button("Apply override"):
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if new_sev != "(no override)" and new_sev != t["severity"]:
                st.session_state.analyst_overrides.append({
                    "field": "severity",
                    "original": t["severity"],
                    "override": new_sev,
                    "rationale": rationale or "(no rationale)",
                    "timestamp": ts,
                })
            if new_esc != "(no override)":
                bool_val = new_esc == "True"
                if bool_val != t["escalate"]:
                    st.session_state.analyst_overrides.append({
                        "field": "escalate",
                        "original": t["escalate"],
                        "override": bool_val,
                        "rationale": rationale or "(no rationale)",
                        "timestamp": ts,
                    })
            st.rerun()

    # Export
    case_with_overrides = dict(case)
    case_with_overrides["analyst_overrides"] = list(st.session_state.analyst_overrides)
    json_blob = json.dumps(case_with_overrides, indent=2)
    md_blob = case_to_markdown(case_with_overrides)
    cdl, cdr = st.columns(2)
    with cdl:
        st.download_button(
            "Download JSON", data=json_blob,
            file_name=f"{case['case_id']}.json", mime="application/json",
            use_container_width=True,
        )
    with cdr:
        st.download_button(
            "Download Markdown", data=md_blob,
            file_name=f"{case['case_id']}.md", mime="text/markdown",
            use_container_width=True,
        )

    with st.expander("Raw case package JSON"):
        st.code(json_blob, language="json")
```

- [ ] **Step 5.6: Add Evaluation tab renderer**

Append to `app.py`:

```python
# --- Evaluation tab ---------------------------------------------------------
def render_evaluation_tab(engine):
    if st.session_state.eval_data is None:
        st.session_state.eval_data = load_harness_results()

    col_l, col_r = st.columns([4, 1])
    with col_l:
        st.markdown('<div class="sec">Reliability harness — 7 canonical alerts</div>',
                    unsafe_allow_html=True)
    with col_r:
        if st.button("Run live (7 API calls)", use_container_width=True):
            with st.spinner("Running harness against live engine..."):
                st.session_state.eval_data = run_harness_live(engine)

    data = st.session_state.eval_data
    if data is None:
        st.markdown(
            '<div class="empty">No harness results found. '
            'Run <code>python -m tests.test_harness</code> from the CLI '
            'or click "Run live" above.</div>',
            unsafe_allow_html=True,
        )
        return

    metrics = compute_eval_metrics(data["results"])
    cols = st.columns(5)
    cards = [
        ("Pass rate", f"{metrics['pass_rate']*100:.0f}% ({metrics['passed']}/{metrics['total']})"),
        ("Severity accuracy",
         f"{metrics['severity_accuracy']*100:.0f}%" if metrics['severity_accuracy'] is not None else "n/a"),
        ("Escalation accuracy",
         f"{metrics['escalation_accuracy']*100:.0f}%" if metrics['escalation_accuracy'] is not None else "n/a"),
        ("Avg retrieval", f"{metrics['avg_retrieval_score']:.3f}"),
        ("Avg latency", f"{metrics['avg_latency']:.1f}s"),
    ]
    for col, (lbl, val) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div class="m-card"><div class="lbl">{lbl}</div>'
                f'<div class="val">{val}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="sec">Per-case results</div>', unsafe_allow_html=True)
    rows = []
    for r in data["results"]:
        rows.append({
            "Test": r.get("id", "?"),
            "Severity": r.get("severity", "—"),
            "Escalate": r.get("escalate", "—"),
            "Techniques": ", ".join(r.get("techniques", []) or []),
            "Score": r.get("retrieval_score"),
            "Latency": r.get("latency_seconds"),
            "Result": "PASS" if r.get("passed") else "FAIL",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
```

- [ ] **Step 5.7: Add System tab renderer and tab dispatch**

Append to `app.py`:

```python
# --- System tab -------------------------------------------------------------
def render_system_tab(engine):
    st.markdown('<div class="sec">Version metadata</div>', unsafe_allow_html=True)
    rows = [{"Setting": k, "Value": str(v)} for k, v in VERSION_META.items()]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown('<div class="sec">Retrieval debugger</div>', unsafe_allow_html=True)
    q = st.text_input(
        "Query (skips LLM, returns top-k chunks only)",
        key="debug_query",
    )
    if st.button("Debug retrieval", disabled=not q.strip()):
        hits = engine.retriever.retrieve(q, top_k=VERSION_META["top_k"])
        if not hits:
            st.warning("No chunks above min similarity threshold.")
        else:
            for chunk, score in hits:
                passed = score >= VERSION_META["min_similarity"]
                badge = "above threshold" if passed else "below threshold"
                st.markdown(
                    f"**{chunk['id']}** &middot; `{chunk['source']}` &middot; "
                    f"score `{score:.3f}` &middot; {badge}",
                    unsafe_allow_html=True,
                )
                st.code(chunk["text"][:500], language="text")

    st.markdown('<div class="sec">Corpus stats</div>', unsafe_allow_html=True)
    chunks = cached_corpus()
    by_source = {}
    for c in chunks:
        by_source.setdefault(c["source"], 0)
        by_source[c["source"]] += 1
    avg_len = sum(len(c["text"]) for c in chunks) / len(chunks)
    st.markdown(
        f"Total chunks: **{len(chunks)}** &middot; "
        f"Sources: **{len(by_source)}** &middot; "
        f"Avg chunk length: **{avg_len:.0f} chars**"
    )
    st.dataframe(
        [{"Source": s, "Chunks": n} for s, n in sorted(by_source.items())],
        use_container_width=True, hide_index=True,
    )


# --- Tab dispatch -----------------------------------------------------------
tab_triage, tab_eval, tab_sys = st.tabs(["Triage", "Evaluation", "System"])

with tab_triage:
    render_triage_tab(engine)
with tab_eval:
    render_evaluation_tab(engine)
with tab_sys:
    render_system_tab(engine)
```

- [ ] **Step 5.8: Launch the Streamlit app and smoke-test the Triage tab**

Run: `streamlit run app.py`

Verify in browser:
1. Tabs render: "Triage / Evaluation / System".
2. Click "LSASS credential dump" sample. Observable pills appear immediately showing `rundll32.exe`, `comsvcs.dll`, `WKSTN-042`, `jsmith`.
3. Click "Run Triage". Severity card shows critical/high. Uncertainty badge shows `actionable`.
4. Expand "Evidence — retrieved chunks". 4 chunks shown with scores; at least one marked `cited`.
5. Expand "Analyst override". Set severity to `medium`, click "Apply override". Severity card updates and shows `override` badge.
6. Click "Download JSON". File downloads with name `SOC-YYYYMMDD-XXXX.json`.

- [ ] **Step 5.9: Smoke-test the Evaluation tab**

In the running app, click "Evaluation" tab. Static results from `tests/harness_results.json` load. Verify:
- Pass rate card shows `100% (7/7)`.
- Per-case dataframe has 7 rows with `PASS` in result column.

Do NOT click "Run live" (costs 7 API calls; the static load already proves the path).

- [ ] **Step 5.10: Smoke-test the System tab**

Click "System" tab. Verify:
- Version metadata table shows model, embeddings, corpus_chunks, prompt_version, top_k, min_similarity.
- Retrieval debugger: type "powershell encoded command" and click "Debug retrieval". Returns top-k chunks with scores.
- Corpus stats shows total chunks (109) and per-source breakdown.

- [ ] **Step 5.11: Run the harness one more time as final regression check**

Stop the Streamlit app (Ctrl+C). Run:
```bash
python -m tests.test_harness
```
Expected: `Passed: 7/7`.

- [ ] **Step 5.12: Commit**

```bash
git add app.py
git commit -m "Rewrite Streamlit UI: 3-tab dashboard with observables, evidence, overrides, exports"
```

---

## Final Verification

- [ ] **Step 6.1: Full test suite passes**

Run: `pytest tests/ -v`
Expected: all tests pass — extractors (17), case_package (11), evaluation (4), plus the harness if it runs from pytest (the harness is normally run via `python -m`, so absent from pytest is OK).

- [ ] **Step 6.2: Reliability harness still 7/7**

Run: `python -m tests.test_harness`
Expected: `Passed: 7/7`. This is the canonical regression check.

- [ ] **Step 6.3: Manual UI walkthrough end-to-end**

`streamlit run app.py`. Walk through one sample alert from each category (ransomware, LSASS, phishing, brute force, insider, gibberish). For each, confirm:
- Observables extracted before LLM call.
- Severity, confidence, uncertainty mode all populated.
- Evidence chunks visible with cited markers.
- Override + export round-trip works.

- [ ] **Step 6.4: Confirm no frozen files were touched**

Run:
```bash
git diff main -- rag/corpus.py rag/retriever.py data/ tests/test_harness.py model_card.md
```
Expected: empty output (zero diff against main for these paths).

If non-empty, revert those files before merging.
