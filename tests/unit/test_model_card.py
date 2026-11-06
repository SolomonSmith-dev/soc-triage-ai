"""The model card must quote the committed harness numbers."""
import json
from pathlib import Path

CARD = Path("model_card.md").read_text()
R = json.loads(Path("tests/harness/retrieval_results.json").read_text())


def test_retrieval_numbers_match_json():
    m = R["metrics"]
    for key in ("hit_at_k", "mrr", "recall_at_k_ceiling"):
        assert f"{m[key]}" in CARD, key
    assert f"{m['recall_at_k']}" in CARD
    assert f"{m['refusal_recall']}" in CARD and f"{m['refusal_tp']} of {m['refusal_tp'] + m['refusal_fn']}" in CARD
    assert str(R["meta"]["source"].split("run ")[1].split(",")[0]) in CARD


def test_sweep_rows_match_json():
    for s in R["sweep"]:
        row = f"| {s['threshold']:.2f} | {s['refusal_precision'] if s['refusal_precision'] is not None else 'n/a'} | {s['refusal_recall']} | {s['refusal_fp']} |"
        assert row in CARD, row


def test_card_claims_no_llm_numbers_without_cassettes():
    has_cassettes = any(Path("tests/harness/cassettes").glob("*.json"))
    if not has_cassettes:
        assert "not yet measured" in CARD.lower()


def test_live_numbers_match_harness_results():
    import json as _j
    doc = _j.loads(Path("tests/harness/harness_results.json").read_text())
    if doc.get("meta", {}).get("mode") != "live":
        return
    m = doc["metrics"]
    pct = lambda x: f"{x * 100:.1f}%"
    for needle in (
        f"{pct(m['pass_rate_standard']['rate'])} ({m['pass_rate_standard']['passed']} of {m['pass_rate_standard']['n']})",
        f"{pct(m['pass_rate_adversarial']['rate'])} ({m['pass_rate_adversarial']['passed']} of {m['pass_rate_adversarial']['n']})",
        pct(m["severity"]["accuracy"]),
        f"{pct(m['mitre']['top1'])} / {pct(m['mitre']['any_match'])}",
        f"{pct(m['escalation']['precision'])} / {pct(m['escalation']['recall'])}",
        pct(m["schema_failure_rate"]),
        f"{m['latency_seconds']['p50']} s / {m['latency_seconds']['p95']} s",
        f"${m['cost_per_triage_usd']}",
        str(m["calibration"]["ece"]),
    ):
        assert needle in CARD, needle
    fails = [r["id"] for r in doc["results"] if not r.get("passed")]
    assert f"The {len(fails)} failures, grouped" in CARD
