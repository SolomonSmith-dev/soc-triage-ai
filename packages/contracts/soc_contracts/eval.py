"""Evaluation / harness result contracts."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvalCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    severity: str | None = None
    escalate: bool | None = None
    techniques: list[str] = []
    retrieval_score: float | None = None
    latency_seconds: float | None = None
    passed: bool
    error: str | None = None


class EvalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    passed: int
    pass_rate: float
    severity_accuracy: float | None = None
    escalation_accuracy: float | None = None
    techniques_accuracy: float | None = None
    retrieval_threshold_rate: float | None = None
    avg_retrieval_score: float
    avg_latency: float
    per_case: list[EvalCaseResult]


class EvalRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metrics: EvalMetrics
    triggered_by: str | None = None
    git_sha: str | None = None
    created_at: datetime | None = None
