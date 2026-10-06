"""Initial v2 schema with pgvector.

Revision ID: 0001
Revises:
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key_hash", sa.Text, nullable=False, unique=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("scopes", sa.ARRAY(sa.Text), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
    )

    # corpus_versions
    op.create_table(
        "corpus_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("embedding_model", sa.Text, nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("manifest", JSONB, nullable=False),
    )
    op.execute(
        "CREATE UNIQUE INDEX corpus_one_active ON corpus_versions (is_active) WHERE is_active = TRUE"
    )

    # alerts
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="alerts_external_unique"),
    )
    op.create_index("alerts_received_at_idx", "alerts", [sa.text("received_at DESC")])

    # observables
    op.create_table(
        "observables",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("alert_id", UUID(as_uuid=True), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("observables_alert_idx", "observables", ["alert_id"])
    op.create_index("observables_kind_value_idx", "observables", ["kind", "value"])

    # intel_chunks (embedding column added via raw SQL because halfvec is
    # not introspectable by SQLAlchemy's standard type system)
    op.create_table(
        "intel_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("corpus_version_id", UUID(as_uuid=True), sa.ForeignKey("corpus_versions.id"), nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute("ALTER TABLE intel_chunks ADD COLUMN embedding halfvec(384) NOT NULL")
    op.execute("CREATE INDEX intel_chunks_hnsw ON intel_chunks USING hnsw (embedding halfvec_cosine_ops)")
    op.create_index("intel_chunks_version_idx", "intel_chunks", ["corpus_version_id"])

    # cases
    op.create_table(
        "cases",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("alert_id", UUID(as_uuid=True), sa.ForeignKey("alerts.id"), nullable=False),
        sa.Column("envelope", JSONB, nullable=False),
        sa.Column("uncertainty_mode", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("escalate", sa.Boolean, nullable=False),
        sa.Column("guardrail_triggered", sa.Boolean, nullable=False),
        sa.Column("retrieval_score", sa.Numeric(4, 3)),
        sa.Column("corpus_version_id", UUID(as_uuid=True), sa.ForeignKey("corpus_versions.id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
    )
    op.create_index("cases_severity_created_idx", "cases", ["severity", sa.text("created_at DESC")])
    op.create_index("cases_escalate_idx", "cases", ["escalate"], postgresql_where=sa.text("escalate = TRUE"))
    op.execute("CREATE INDEX cases_envelope_gin ON cases USING GIN (envelope jsonb_path_ops)")

    # evidence_links
    op.create_table(
        "evidence_links",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Text, sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("intel_chunks.id"), nullable=False),
        sa.Column("score", sa.Numeric(4, 3), nullable=False),
        sa.Column("cited", sa.Boolean, nullable=False),
    )
    op.create_index("evidence_case_idx", "evidence_links", ["case_id"])

    # analyst_overrides
    op.create_table(
        "analyst_overrides",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Text, sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analyst_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("field", sa.Text, nullable=False),
        sa.Column("old_value", JSONB),
        sa.Column("new_value", JSONB, nullable=False),
        sa.Column("rationale", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("overrides_case_idx", "analyst_overrides", ["case_id", "created_at"])

    # eval_runs
    op.create_table(
        "eval_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("corpus_version_id", UUID(as_uuid=True), sa.ForeignKey("corpus_versions.id"), nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("passed", sa.Integer, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("metrics", JSONB, nullable=False),
        sa.Column("per_case", JSONB, nullable=False),
        sa.Column("triggered_by", sa.Text, nullable=False),
        sa.Column("git_sha", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("eval_runs_created_idx", "eval_runs", [sa.text("created_at DESC")])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("actor_id", UUID(as_uuid=True)),
        sa.Column("actor_type", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("resource", sa.Text, nullable=False),
        sa.Column("payload", JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("audit_actor_time", "audit_logs", ["actor_id", sa.text("created_at DESC")])
    op.create_index("audit_resource_time", "audit_logs", ["resource", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("eval_runs")
    op.drop_table("analyst_overrides")
    op.drop_table("evidence_links")
    op.drop_table("cases")
    op.drop_table("intel_chunks")
    op.drop_table("observables")
    op.drop_table("alerts")
    op.drop_table("corpus_versions")
    op.drop_table("api_keys")
    op.drop_table("users")
