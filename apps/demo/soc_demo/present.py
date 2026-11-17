"""Presentation rules shared by the demo pages (Streamlit locally and in the Docker image, Gradio on the Space).

Kept in one place so the pages label cases, match recordings and flag documented misses the same way.
"""
from __future__ import annotations

# Quick picks by harness case id. A page shows one only if GET /samples lists it, which in cached mode means
# the serving machine verified that it replays or refuses.
FEATURED = {
    "T2_ransomware_active": "Active ransomware",
    "T3_credential_dumping_lsass": "LSASS credential dump",
    "T4_brute_force_ssh": "SSH brute force (Tor exit)",
    "INJ-001": "Prompt injection inside the alert",
    "BEN-001": "Benign lookalike (backup job)",
    "OOC-004": "Out of scope (refusal)",
}
OUTCOME = {"replay": "recorded answer", "refusal": "refused at retrieval", "live": "live"}

CACHED_INTRO = ("Public demo in recorded mode: the model step replays the responses Claude gave in the project's "
                "100-case harness run, so this page makes no model calls and costs nothing. Observable extraction, "
                "retrieval, the refusal guardrail and schema validation run live on every request. Pick a recorded "
                "alert. Do not paste real alert data.")
LIVE_INTRO = ("RAG-grounded alert triage. Public demo: do not paste real alert data. Requests are rate limited "
              "and total model usage is capped per day.")
EXACT_TEXT_NOTE = ("Recordings match on the exact text. An edited alert still runs retrieval and the guardrail, "
                   "but gets no model response.")
NOT_RECORDED = ("No recorded model response matches this exact text, so the model step did not run. Retrieval "
                "found matching context, so the refusal guardrail did not fire either. Pick a recorded alert for a "
                "full triage, or run the project with your own key (see the README).")
KNOWN_MISS = ("Known guardrail miss, documented in model_card.md: the harness expects a refusal for this "
              "out-of-corpus alert, but its retrieval score cleared the threshold, so it reached the model.")


def option_label(sample: dict) -> str:
    miss = (" (known miss: the harness expects a refusal)"
            if sample.get("expects_refusal") and sample["kind"] == "replay" else "")
    return f"{sample['id']}: {sample['label']}; {OUTCOME.get(sample['kind'], sample['kind'])}{miss}"


def canonical_alert(alert: str, samples: list[dict]) -> str:
    """Recordings match on every byte, and each recorded alert ends in a newline. An alert that differs from a
    recorded one only in leading or trailing whitespace maps back to it, so pressing Enter does not lose it."""
    return {s["alert"].strip(): s["alert"] for s in samples}.get(alert.strip(), alert)


def is_known_miss(sample: dict | None, envelope: dict) -> bool:
    return bool(sample and sample.get("expects_refusal") and not envelope["guardrail_triggered"])


def download_name(envelope: dict, replay_case: str | None) -> str:
    # the body has no replay field (the contract has none yet), so the file name carries the provenance
    return f"{envelope['case_id']}_replay-{replay_case}.json" if replay_case else f"{envelope['case_id']}.json"
