"""GET /eval/latest — load the most recent harness results."""
from fastapi import APIRouter, HTTPException, status

from soc_contracts import EvalCaseResult, EvalMetrics, EvalRunSummary

router = APIRouter(prefix="/eval", tags=["eval"])


@router.get("/latest", response_model=EvalRunSummary)
async def latest_eval() -> EvalRunSummary:
    """Loads tests/harness/harness_results.json. Phase 5+ will read from eval_runs."""
    from triage_engine.evaluation import load_harness_results, compute_eval_metrics

    data = load_harness_results()
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No harness results available. Run python -m tests.harness.test_harness.",
        )
    metrics_dict = compute_eval_metrics(data["results"])
    per_case = [EvalCaseResult.model_validate(r) for r in metrics_dict.pop("per_case")]
    metrics = EvalMetrics(per_case=per_case, **metrics_dict)
    return EvalRunSummary(metrics=metrics)
