"""How often a technique ID is visible in the retrieved context, and how that relates to the answer.

Uses the committed retrieval scores (top-10 chunk ids per query), the corpus text, and the
committed live results. No model and no API call.

  python -m tests.harness.technique_coverage [--snapshot PATH]

"Visible before" means an expected technique ID appears in the text of a top-4 chunk, which is what
the prompt contained before the section-technique note. "Visible after" adds the IDs
`section_technique_ids` attaches. The pass-rate split uses the live run's `techniques_match` check,
so it describes the run whose results file is committed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage_engine.rag.corpus import TECH_ID, load_corpus, section_technique_ids
from triage_engine.triage import CORPUS_DIR
from tests.harness.loader import load_cases

HERE = Path(__file__).parent
TOP_K = 4


def _hit(ids: set[str], expected: list[str]) -> bool:
    return any(e in ids or any(x.startswith(e) or e.startswith(x) for x in ids) for e in expected)


def coverage(raw: dict, chunks: list[dict], cases, results: dict) -> dict:
    text = {c["id"]: c["text"] for c in chunks}
    section = section_technique_ids(chunks)
    own = {cid: set(TECH_ID.findall(t)) for cid, t in text.items()}
    rows = []
    for c in cases:
        exp = c.expect.techniques_any
        r = results.get(c.id)
        if not exp or not r or r.get("status") != "ok":
            continue
        top = [cid for cid, _ in raw[c.id]]
        before = any(_hit(own[cid], exp) for cid in top[:TOP_K])
        after = any(_hit(own[cid] | set(section[cid]), exp) for cid in top[:TOP_K])
        in_top10 = any(_hit(own[cid], exp) for cid in top[:10])
        rows.append((before, after, in_top10, bool(r["checks"].get("techniques_match"))))

    def split(flag_index: int, value: bool) -> list[int]:
        sub = [r for r in rows if r[flag_index] is value]
        return [sum(1 for r in sub if r[3]), len(sub)]

    return {
        "cases_expecting_techniques": len(rows),
        "visible_before": sum(1 for r in rows if r[0]),
        "visible_after": sum(1 for r in rows if r[1]),
        "not_visible_before_but_in_top10": sum(1 for r in rows if not r[0] and r[2]),
        "not_in_top10_before": sum(1 for r in rows if not r[2]),
        "technique_match_when_visible_before": split(0, True),
        "technique_match_when_not_visible_before": split(0, False),
        "chunks_with_ids_before": sum(1 for v in own.values() if v),
        "chunks_with_ids_after": sum(1 for cid in text if own[cid] | set(section[cid])),
        "chunks_total": len(text),
    }


def compute() -> dict:
    raw = json.loads((HERE / "retrieval_results.json").read_text())["raw"]
    res = {r["id"]: r for r in json.loads((HERE / "harness_results.json").read_text())["results"]}
    return coverage(raw, load_corpus(CORPUS_DIR), load_cases(), res)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path)
    args = ap.parse_args()
    out = compute()
    print(json.dumps(out, indent=2))
    if args.snapshot:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
