"""Case envelope contract — mirrors triage_engine.case_package.build_case_package output."""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UncertaintyMode(str, Enum):
    actionable = "actionable"
    needs_more_context = "needs_more_context"
    insufficient_evidence = "insufficient_evidence"
    out_of_scope = "out_of_scope"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    informational = "informational"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Observables(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ipv4: list[str] = []
    email: list[str] = []
    url: list[str] = []
    domain: list[str] = []
    md5: list[str] = []
    sha1: list[str] = []
    sha256: list[str] = []
    registry_path: list[str] = []
    process: list[str] = []
    filename: list[str] = []
    hostname: list[str] = []
    username: list[str] = []


class TriageResult(BaseModel):
    """The LLM-produced triage. Mirrors triage.py output (minus sources/retrieval_score, which moved to evidence)."""
    model_config = ConfigDict(extra="forbid")
    severity: Severity
    confidence: Confidence
    mitre_techniques: list[str]
    summary: str
    recommended_actions: list[str]
    escalate: bool
    reasoning: str


class EvidenceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    source: str
    score: float
    text: str
    cited: bool


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunks_retrieved: list[EvidenceChunk]
    avg_retrieval_score: float
    sources_cited: list[str]


class VersionMeta(BaseModel):
    """Pinned at the moment of triage — model, embeddings, corpus, prompt."""
    model_config = ConfigDict(extra="forbid")
    model: str
    embeddings: str
    corpus_chunks: int
    prompt_version: str
    top_k: int
    min_similarity: float


class OverrideRecord(BaseModel):
    """An analyst override applied post-triage. Append-only."""
    model_config = ConfigDict(extra="forbid")
    field: str
    original: Any
    override: Any
    rationale: str
    timestamp: datetime


class CaseEnvelope(BaseModel):
    """Full case envelope persisted as cases.envelope JSONB. Immutable after triage."""
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(pattern=r"^SOC-\d{8}-[a-f0-9]{4}$")
    timestamp: datetime
    alert_raw: str
    observables: Observables
    triage: TriageResult
    evidence: Evidence
    uncertainty_mode: UncertaintyMode
    guardrail_triggered: bool
    analyst_overrides: list[OverrideRecord] = []
    version: VersionMeta


class CaseSummary(BaseModel):
    """Slim case representation for the dashboard table."""
    model_config = ConfigDict(extra="forbid")
    case_id: str
    severity: Severity
    escalate: bool
    uncertainty_mode: UncertaintyMode
    summary: str
    created_at: datetime
    retrieval_score: float | None


class OverrideRequest(BaseModel):
    """Request body for POST /cases/{id}/override."""
    model_config = ConfigDict(extra="forbid")
    field: str = Field(pattern=r"^(severity|escalate|mitre_techniques|notes)$")
    new_value: Any
    rationale: str = Field(min_length=1)
