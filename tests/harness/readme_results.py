"""Generate the README badges and Results table from the committed harness JSON.

  python -m tests.harness.readme_results          rewrite the marked blocks in README.md
  python -m tests.harness.readme_results --check  exit 1 if README.md is out of date
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from tests.harness.loader import load_cases
from tests.harness.report import RETRIEVAL, load_results_doc, suite_stats

README = Path(__file__).parents[2] / "README.md"
CI_URL = "https://github.com/SolomonSmith-dev/soc-triage-ai/actions/workflows/ci.yml"
NOT_RECORDED = "not recorded yet"


def _pct(x):
    return NOT_RECORDED if x is None else f"{x * 100:.1f}%"


def _badge(label: str, value: str, color: str) -> str:
    esc = lambda s: s.replace("-", "--").replace("_", "__").replace(" ", "%20").replace("@", "%40").replace("/", "%2F")
    return f"![{label}](https://img.shields.io/badge/{esc(label)}-{esc(value)}-{color})"


def render_badges(cases, rdoc, results_doc) -> str:
    st = suite_stats(cases)
    out = [
        "![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)",
        "![Python](https://img.shields.io/badge/python-3.10+-blue.svg)",
        f"[![CI]({CI_URL.replace('ci.yml', 'ci.yml/badge.svg')})]({CI_URL})",
        _badge("harness cases", str(st["total"]), "informational"),
    ]
    if rdoc:
        m = rdoc["metrics"]
        out.append(_badge("retrieval hit@4", f"{m['hit_at_k']}", "success"))
        out.append(_badge("refusal precision", f"{m['refusal_precision']}", "success"))
    meta = results_doc.get("meta", {})
    if meta.get("mode") == "live":
        mt = results_doc["metrics"]
        passed = mt["pass_rate_standard"]["passed"] + mt["pass_rate_adversarial"]["passed"]
        out.append(_badge("live harness", f"{passed}/{mt['evaluated']} passing", "success" if passed == mt["evaluated"] else "yellow"))
    else:
        out.append(_badge("live harness", "run pending", "lightgrey"))
    return " ".join(out)


def render_results(cases, rdoc, results_doc) -> str:
    st = suite_stats(cases)
    g = st["groups"]
    adv = sum(v for k, v in g.items() if k != "standard")
    rows = [
        ("Test cases", f"{st['total']} ({g.get('standard', 0)} standard, {adv} adversarial)", "`tests/harness/cases/`"),
        ("Adversarial mix", f"{st['injection']} prompt injection, {g.get('adversarial:contradiction', 0)} contradictory claims, "
                            f"{g.get('adversarial:benign_lookalike', 0)} benign lookalikes, {st['should_refuse']} out-of-corpus must-refuse", "`tests/harness/cases/`"),
        ("MITRE technique families expected", str(len(st["techniques"])), "`tests/harness/cases/`"),
        ("Human-reviewed cases", f"{st['reviewed']} of {st['total']} (the rest are Claude-drafted, pending my review)", "`provenance` in each case"),
    ]
    if rdoc:
        m = rdoc["metrics"]
        rows += [
            ("Retrieval hit@4", f"{m['hit_at_k']} ({m['answerable_queries']} labeled queries)", "`retrieval_results.json`"),
            ("Retrieval recall@4 / MRR", f"{m['recall_at_k']} (ceiling {m['recall_at_k_ceiling']}) / {m['mrr']}", "`retrieval_results.json`"),
            (f"Refusal precision / recall at {m['threshold']:.2f}", f"{m['refusal_precision']} / {m['refusal_recall']} ({m['refusal_tp']} of {m['refusal_tp'] + m['refusal_fn']} out-of-corpus refused)", "`retrieval_results.json`"),
        ]
    meta = results_doc.get("meta", {})
    if meta.get("mode") == "live":
        mt = results_doc["metrics"]
        rows += [
            ("Standard / adversarial pass rate", f"{_pct(mt['pass_rate_standard']['rate'])} / {_pct(mt['pass_rate_adversarial']['rate'])}", "`harness_results.json`"),
            ("Severity accuracy (in accepted range)", _pct(mt["severity"]["accuracy"]), "`harness_results.json`"),
            ("MITRE top-1 / any-match", f"{_pct(mt['mitre']['top1'])} / {_pct(mt['mitre']['any_match'])}", "`harness_results.json`"),
            ("Prompt injection", f"{round(mt['injection']['resistance'] * mt['injection']['cases'])} of {mt['injection']['cases']} cases pass; canary leaked in {_pct(mt['injection']['canary_leak_rate'])} of cases", "`harness_results.json`"),
            ("Schema-failure rate", _pct(mt["schema_failure_rate"]), "`harness_results.json`"),
            ("Latency p50 / p95", f"{mt['latency_seconds']['p50']} s / {mt['latency_seconds']['p95']} s", "`harness_results.json`"),
            ("Cost per triage (estimated from token usage)", f"${mt['cost_per_triage_usd']}", "`harness_results.json`"),
        ]
        note = ""
    else:
        legacy = results_doc["results"] if meta.get("mode") == "legacy-live-7-case" else []
        if legacy:
            ok = sum(1 for r in legacy if r.get("passed"))
            rows.append(("Original 7-case live run (July 2026)", f"{ok}/{len(legacy)} passed", "`harness_results.json`"))
        for label in ("Severity accuracy, MITRE top-1 and any-match, injection resistance, schema-failure rate, latency, cost per triage (100 cases)",):
            rows.append((label, NOT_RECORDED, "needs one live run"))
        note = ("\nThe LLM-in-the-loop rows fill in from one recorded run: "
                "`python -m tests.harness.test_harness --record --update-baseline`, then `python -m tests.harness.readme_results`.\n")
    lines = ["| Metric | Value | Source |", "|---|---|---|"] + [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(lines) + "\n" + note


def _block(name: str) -> re.Pattern:
    return re.compile(rf"(<!-- {name}:BEGIN -->\n)(.*?)(<!-- {name}:END -->)", re.S)


def render_readme(text: str) -> str:
    cases = load_cases()
    rdoc = json.loads(RETRIEVAL.read_text()) if RETRIEVAL.exists() else None
    results_doc = load_results_doc()
    for name, body in (("BADGES", render_badges(cases, rdoc, results_doc)),
                       ("RESULTS", render_results(cases, rdoc, results_doc).rstrip("\n"))):
        text = _block(name).sub(lambda m: m.group(1) + body + "\n" + m.group(3), text)
    return text


def main(argv: list[str]) -> int:
    old = README.read_text(encoding="utf-8")
    new = render_readme(old)
    if "--check" in argv:
        if new != old:
            print("README.md is out of date: run python -m tests.harness.readme_results")
            return 1
        return 0
    README.write_text(new, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
