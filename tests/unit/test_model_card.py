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
