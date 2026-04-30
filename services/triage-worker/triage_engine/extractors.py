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
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b")
_TRAILING_PUNCT = ".,;:!?)]}"

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

_HOSTNAME_RES = [
    re.compile(r"\bWKSTN-[A-Za-z0-9\-]+\b"),
    re.compile(r"\bsrv-[A-Za-z0-9\-]+\b"),
    re.compile(r"\bDC-[A-Za-z0-9\-]+\b"),
]
_USERNAME_RE = re.compile(
    r"(?:user(?:\s+account)?|account|employee|login)\s+(?:is\s+)?([A-Za-z][A-Za-z0-9_\-\.]{1,30})",
    re.IGNORECASE,
)
_USERNAME_TRAILING_STRIP = ".,;:!?"


def _extract_ipv4(text: str) -> List[str]:
    out = []
    for m in _IPV4_RE.findall(text):
        octets = m.split(".")
        if all(0 <= int(o) <= 255 for o in octets):
            out.append(m)
    return out


def _extract_email(text: str) -> List[str]:
    return _EMAIL_RE.findall(text)


def _extract_url(text: str) -> List[str]:
    return [u.rstrip(_TRAILING_PUNCT) for u in _URL_RE.findall(text)]


def _extract_domain(text: str, exclude: set) -> List[str]:
    exclude_lower = {e.lower() for e in exclude}
    out = []
    for m in _DOMAIN_RE.findall(text):
        bare = m.rstrip(_TRAILING_PUNCT)
        if bare.lower() in exclude_lower:
            continue
        if _IPV4_RE.fullmatch(bare):
            continue
        out.append(bare)
    return out


def _extract_hashes(text: str):
    sha256s = _SHA256_RE.findall(text)
    sha256_blob = "".join(sha256s)
    sha1s = [h for h in _SHA1_RE.findall(text) if h not in sha256_blob]
    sha1_blob = "".join(sha1s)
    md5s = [h for h in _MD5_RE.findall(text)
            if h not in sha256_blob and h not in sha1_blob]
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


def _extract_hostname(text: str) -> List[str]:
    out = []
    for r in _HOSTNAME_RES:
        out.extend(r.findall(text))
    return out


def _extract_username(text: str) -> List[str]:
    return [m.rstrip(_USERNAME_TRAILING_STRIP) for m in _USERNAME_RE.findall(text)]


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

    emails = _dedupe(_extract_email(text))
    urls = _dedupe(_extract_url(text))
    processes, filenames = _extract_process_and_filename(text)

    domain_exclude = set()
    for e in emails:
        if "@" in e:
            domain_exclude.add(e.split("@", 1)[1])
    for u in urls:
        # strip scheme then take host portion
        no_scheme = re.sub(r"^https?://", "", u)
        host = no_scheme.split("/", 1)[0].split(":", 1)[0]
        domain_exclude.add(host)
    domain_exclude.update(processes)
    domain_exclude.update(filenames)

    md5s, sha1s, sha256s = _extract_hashes(text)

    return {
        "ipv4": _dedupe(_extract_ipv4(text)),
        "email": emails,
        "url": urls,
        "domain": _dedupe(_extract_domain(text, domain_exclude)),
        "md5": _dedupe(md5s),
        "sha1": _dedupe(sha1s),
        "sha256": _dedupe(sha256s),
        "registry_path": _dedupe(_extract_registry(text)),
        "process": _dedupe(processes),
        "filename": _dedupe(filenames),
        "hostname": _dedupe(_extract_hostname(text)),
        "username": _dedupe(_extract_username(text)),
    }
