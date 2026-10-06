"""Pydantic models for harness case files. Single source of case validation."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["critical", "high", "medium", "low", "informational"]
SEVERITY_ORDER = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity_in: list[Severity] = Field(min_length=1)
    techniques_any: list[str] = []
    escalate: bool | None = None
    min_retrieval_score: float = 0.0
    guardrail: bool | None = None
    forbid_in_output: list[str] = []


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    drafted_by: str
    reviewed_by: str | None = None
    reviewed_on: date | None = None


class Adversarial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["injection", "contradiction", "benign_lookalike", "noise"]


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: str
    tags: list[str] = []
    adversarial: Adversarial | None = None
    alert: str
    expect: Expect
    relevant_chunks: list[str] = []
    provenance: Provenance
    notes: str = ""

    @property
    def group(self) -> str:
        return "standard" if self.adversarial is None else f"adversarial:{self.adversarial.type}"

    @property
    def human_reviewed(self) -> bool:
        return bool(self.provenance.reviewed_by)

    def to_legacy(self) -> dict:
        """Dict shape used by the original harness and triage_engine.evaluation."""
        d = {
            "id": self.id,
            "alert": self.alert,
            "expect_severity_in": list(self.expect.severity_in),
            "min_retrieval_score": self.expect.min_retrieval_score,
        }
        if self.expect.techniques_any:
            d["expect_techniques_any"] = list(self.expect.techniques_any)
        if self.expect.escalate is not None:
            d["expect_escalate"] = self.expect.escalate
        if self.expect.guardrail is not None:
            d["expect_guardrail"] = self.expect.guardrail
        if self.expect.forbid_in_output:
            d["forbid_in_output"] = list(self.expect.forbid_in_output)
        return d
