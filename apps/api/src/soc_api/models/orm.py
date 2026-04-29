"""SQLAlchemy declarative ORM models for the v2 SOC Triage Copilot schema.

Notes:
- The ``intel_chunks.embedding`` column (``halfvec(384)``) is intentionally
  omitted from the ORM. The migration owns the column DDL and the HNSW index;
  the worker reads/writes ``embedding`` via raw SQL in Phase 4. Keeping it out
  of the ORM avoids pgvector ↔ SQLAlchemy typing footguns and lets reads of
  ``IntelChunk`` ignore the (potentially large) vector by default.
- ``metadata`` is a reserved name on ``DeclarativeBase``. The Python attribute
  is ``metadata_json`` and maps to a DB column of the same name.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from soc_api.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CorpusVersion(Base):
    __tablename__ = "corpus_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="alerts_external_unique"),
    )


class Observable(Base):
    __tablename__ = "observables"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IntelChunk(Base):
    """Threat-intel corpus chunk.

    The ``embedding halfvec(384)`` column exists in Postgres (created by the
    migration) but is intentionally NOT mapped here. Vector reads/writes go
    through raw SQL in the worker; the ORM stays vector-free.
    """

    __tablename__ = "intel_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    corpus_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corpus_versions.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # ``metadata`` is reserved on DeclarativeBase, so the Python attribute and
    # DB column are both ``metadata_json``.
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=False
    )
    envelope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    uncertainty_mode: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    escalate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guardrail_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retrieval_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    corpus_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corpus_versions.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class EvidenceLink(Base):
    __tablename__ = "evidence_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        Text, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intel_chunks.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    cited: Mapped[bool] = mapped_column(Boolean, nullable=False)


class AnalystOverride(Base):
    __tablename__ = "analyst_overrides"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        Text, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    analyst_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    field: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    corpus_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corpus_versions.id"), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    per_case: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    git_sha: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
