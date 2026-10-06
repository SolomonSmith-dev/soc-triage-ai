"""Retrieval metrics over the labeled alert-to-relevant-chunk set.

Raw top-10 scores are stored so every metric and the threshold sweep can be
recomputed offline, without the embedding model.

Definitions
  relevant:       chunk ids listed in a case's `relevant_chunks`
  should refuse:  case has no relevant chunks (nothing in the corpus applies)
  refuse at t:    top-1 cosine score < t (no chunk clears the guardrail)
  recall@k:       |relevant in top-k| / |relevant|, averaged over answerable queries
                  (ceiling: the best possible value, since a query with more than k
                  relevant chunks cannot reach 1.0)
  hit@k:          share of answerable queries with at least one relevant chunk in top-k
  MRR:            mean of 1 / rank of the first relevant chunk in the top-10 (0 if absent)
  refusal P/R:    positive class is "should refuse"
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tests.harness.loader import load_cases

DEPTH = 10
PIPELINE_K = 4
PIPELINE_THRESHOLD = 0.20
SWEEP = [round(0.10 + 0.05 * i, 2) for i in range(7)]  # 0.10 .. 0.40
OUT = Path(__file__).parent / "retrieval_results.json"


def labels_from_cases(cases) -> list[dict]:
    return [{"id": c.id, "query": c.alert, "relevant": list(c.relevant_chunks),
             "should_refuse": not c.relevant_chunks} for c in cases]


def collect_raw(retriever, labels: list[dict]) -> dict:
    raw = {}
    for lab in labels:
        hits = retriever.retrieve(lab["query"], top_k=DEPTH, min_score=-1.0)
        raw[lab["id"]] = [[ch["id"], round(s, 4)] for ch, s in hits]
    return raw


def metrics_from_raw(raw: dict, labels: list[dict], threshold: float = PIPELINE_THRESHOLD,
                     k: int = PIPELINE_K) -> dict:
    ans = [l for l in labels if not l["should_refuse"]]
    neg = [l for l in labels if l["should_refuse"]]
    recalls, hits_k, rrs, rec_thr, ceil = [], [], [], [], []
    for l in ans:
        ranked = raw[l["id"]]
        rel = set(l["relevant"])
        top = [cid for cid, _ in ranked[:k]]
        recalls.append(len(rel & set(top)) / len(rel))
        ceil.append(min(len(rel), k) / len(rel))
        hits_k.append(1.0 if rel & set(top) else 0.0)
        rr = 0.0
        for i, (cid, _) in enumerate(ranked, 1):
            if cid in rel:
                rr = 1.0 / i
                break
        rrs.append(rr)
        top_thr = [cid for cid, s in ranked[:k] if s >= threshold]
        rec_thr.append(len(rel & set(top_thr)) / len(rel))

    def refuses(l):
        return not raw[l["id"]] or raw[l["id"]][0][1] < threshold

    tp = sum(1 for l in neg if refuses(l))
    fp = sum(1 for l in ans if refuses(l))
    fn = len(neg) - tp
    return {
        "threshold": threshold, "k": k,
        "answerable_queries": len(ans), "refusal_queries": len(neg),
        "recall_at_k": round(sum(recalls) / len(recalls), 3) if recalls else None,
        "recall_at_k_ceiling": round(sum(ceil) / len(ceil), 3) if ceil else None,
        "recall_at_k_after_threshold": round(sum(rec_thr) / len(rec_thr), 3) if rec_thr else None,
        "hit_at_k": round(sum(hits_k) / len(hits_k), 3) if hits_k else None,
        "mrr": round(sum(rrs) / len(rrs), 3) if rrs else None,
        "refusal_precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "refusal_recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "refusal_tp": tp, "refusal_fp": fp, "refusal_fn": fn,
    }


def sweep_from_raw(raw: dict, labels: list[dict]) -> list[dict]:
    return [metrics_from_raw(raw, labels, t) for t in SWEEP]


def build_report(raw: dict, labels: list[dict], meta: dict) -> dict:
    return {"meta": meta, "metrics": metrics_from_raw(raw, labels), "sweep": sweep_from_raw(raw, labels), "raw": raw}


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None, help="write the report here")
    ap.add_argument("--check", type=Path, default=None, help="recompute and compare against a committed report")
    ap.add_argument("--print-json", action="store_true", help="print the report between markers (for CI logs)")
    ap.add_argument("--tolerance", type=float, default=0.01)
    args = ap.parse_args(argv)

    from tests.harness.runner import build_retriever
    labels = labels_from_cases(load_cases())
    retriever = build_retriever()
    raw = collect_raw(retriever, labels)
    meta = {"model": retriever.model_name, "corpus_chunks": len(retriever.chunks), "queries": len(labels),
            "git_sha": _git_sha(), "pipeline_threshold": PIPELINE_THRESHOLD, "pipeline_top_k": PIPELINE_K}
    report = build_report(raw, labels, meta)
    if args.out:
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if args.print_json:
        print("RETRIEVAL_JSON_BEGIN")
        print(json.dumps(report, separators=(",", ":")))
        print("RETRIEVAL_JSON_END")
    print(json.dumps({"metrics": report["metrics"], "sweep": report["sweep"]}, indent=1))
    if args.check:
        old = json.loads(args.check.read_text())
        bad = [f"{k}: committed {old['metrics'][k]} vs now {report['metrics'][k]}"
               for k in ("recall_at_k", "hit_at_k", "mrr", "refusal_precision", "refusal_recall")
               if abs((old["metrics"][k] or 0) - (report["metrics"][k] or 0)) > args.tolerance]
        if bad:
            print("retrieval results drifted:\n" + "\n".join(bad))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
