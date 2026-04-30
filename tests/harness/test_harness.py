"""Reliability harness: runs predefined alerts, validates triage output, prints summary.

This is the required reliability/evaluation feature for the project. It serves
as both an evaluation tool and a regression suite to detect drift in retrieval
or LLM output quality.
"""
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

from triage_engine.triage import SOCTriage  # v2 monorepo path; was: from triage import SOCTriage

logging.basicConfig(level=logging.WARNING)


TEST_CASES: List[Dict[str, Any]] = [
    {
        "id": "T1_phishing_credential_entry",
        "alert": (
            "User reported email from ceo@anthrop1c.com (note typo) requesting "
            "urgent wire transfer to new vendor. User clicked link and entered "
            "credentials before reporting. Email contained urgency language."
        ),
        "expect_severity_in": ["high", "critical"],
        "expect_techniques_any": ["T1566"],
        "expect_escalate": True,
        "min_retrieval_score": 0.25,
    },
    {
        "id": "T2_ransomware_active",
        "alert": (
            "Multiple file servers showing thousands of file modifications per minute. "
            "Files renamed with .lockbit extension. README.txt ransom notes appearing "
            "in every directory. Volume Shadow Copies deleted via vssadmin 30 minutes ago."
        ),
        "expect_severity_in": ["critical"],
        "expect_techniques_any": ["T1486", "T1490"],
        "expect_escalate": True,
        "min_retrieval_score": 0.30,
    },
    {
        "id": "T3_credential_dumping_lsass",
        "alert": (
            "EDR detected suspicious access to LSASS process memory by rundll32.exe "
            "with comsvcs.dll on workstation WKSTN-042. User account is jsmith. "
            "Process tree: cmd.exe -> rundll32.exe."
        ),
        "expect_severity_in": ["critical", "high"],
        "expect_techniques_any": ["T1003"],
        "expect_escalate": True,
        "min_retrieval_score": 0.30,
    },
    {
        "id": "T4_brute_force_ssh",
        "alert": (
            "5000 failed SSH authentication attempts in last 10 minutes against "
            "host srv-bastion-01 from source IP 185.220.101.45 (known Tor exit). "
            "No successful authentications observed yet."
        ),
        "expect_severity_in": ["high", "medium"],
        "expect_techniques_any": ["T1110"],
        "expect_escalate": True,
        "min_retrieval_score": 0.25,
    },
    {
        "id": "T5_log4shell_unverified_patch_claim",
        "alert": (
            "WAF detected JNDI string in HTTP User-Agent header to internal Java "
            "application: jndi:ldap://attacker-domain.com/exploit. Source IP "
            "is external. Application server is patched against CVE-2021-44228."
        ),
        "expect_severity_in": ["high", "medium", "low"],
        "expect_techniques_any": ["T1190"],
        "expect_escalate": True,
        "min_retrieval_score": 0.25,
    },
    {
        "id": "T6_gibberish_guardrail",
        "alert": "asdfqwerzxcv 1234567890 lorem ipsum dolor sit amet",
        "expect_severity_in": ["informational", "low"],
        "expect_escalate": False,
        "min_retrieval_score": 0.0,
    },
    {
        "id": "T7_insider_exfil_departing",
        "alert": (
            "Employee jdoe (resignation notice given last week) downloaded 15GB of "
            "customer data from CRM in last 24 hours. Login from new device "
            "fingerprint. Email forwarding rule created to personal Gmail yesterday."
        ),
        "expect_severity_in": ["high", "critical"],
        "expect_escalate": True,
        "min_retrieval_score": 0.25,
    },
]


def evaluate_case(result: Dict, case: Dict) -> Dict:
    """Check a triage result against expected case criteria."""
    checks = {}

    checks["severity_match"] = result["severity"] in case["expect_severity_in"]

    if "expect_escalate" in case:
        checks["escalate_match"] = result["escalate"] == case["expect_escalate"]

    if "expect_techniques_any" in case:
        result_techs = set(result.get("mitre_techniques", []))
        expected = set(case["expect_techniques_any"])
        match = any(
            any(rt.startswith(et) or et.startswith(rt) for rt in result_techs)
            for et in expected
        )
        checks["techniques_match"] = match if result_techs else False

    checks["retrieval_score_ok"] = (
        result.get("retrieval_score", 0) >= case["min_retrieval_score"]
    )

    passed = all(checks.values())
    return {"passed": passed, "checks": checks}


def run_harness():
    print("\n" + "=" * 70)
    print("SOC TRIAGE AI: RELIABILITY HARNESS")
    print("=" * 70)
    print("Initializing system (loading corpus, indexing embeddings)...\n")

    start = time.time()
    triage = SOCTriage()
    init_time = time.time() - start
    print(f"System ready in {init_time:.1f}s\n")

    results = []

    for case in TEST_CASES:
        print(f"Running {case['id']}...")
        case_start = time.time()
        try:
            result = triage.triage(case["alert"])
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
            status = "PASS" if evaluation["passed"] else "FAIL"
            print(f"  [{status}] severity={result['severity']} "
                  f"techs={result.get('mitre_techniques', [])} "
                  f"score={result.get('retrieval_score')} "
                  f"({elapsed:.1f}s)\n")
        except Exception as e:
            results.append({
                "id": case["id"],
                "passed": False,
                "error": str(e),
            })
            print(f"  [ERROR] {type(e).__name__}: {e}\n")

    # Summary
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    avg_score = sum((r.get("retrieval_score") or 0) for r in results) / total
    avg_latency = sum(r.get("latency_seconds", 0) for r in results) / total

    print("=" * 70)
    print("HARNESS SUMMARY")
    print("=" * 70)
    print(f"Passed:           {passed}/{total}")
    print(f"Pass rate:        {100*passed/total:.0f}%")
    print(f"Avg retrieval:    {avg_score:.3f}")
    print(f"Avg latency:      {avg_latency:.1f}s")
    print("=" * 70)

    print("\nFailed cases (if any):")
    failed = [r for r in results if not r.get("passed")]
    if not failed:
        print("  None")
    for r in failed:
        print(f"\n  [{r['id']}]")
        if "error" in r:
            print(f"    Error: {r['error']}")
        else:
            print(f"    Severity: {r.get('severity')} | Escalate: {r.get('escalate')}")
            print(f"    Techniques: {r.get('techniques')}")
            print(f"    Failed checks: {r.get('checks')}")

    Path("tests/harness/harness_results.json").write_text(json.dumps(results, indent=2))
    print(f"\nFull results: tests/harness/harness_results.json")

    return passed, total


if __name__ == "__main__":
    run_harness()
