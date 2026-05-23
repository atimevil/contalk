"""Initial schema — users, contracts, payments, quotas, special_clause_edits

Revision ID: 001
Revises:
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("nickname", sa.String(), nullable=True),
        sa.Column("profile_image_url", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False, server_default="email"),
        sa.Column("provider_id", sa.String(), nullable=True),
        sa.Column("terms_agreed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("privacy_agreed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("marketing_agreed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("agreed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token_hash", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── contracts ────────────────────────────────────────────────────────────
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("s3_key", sa.String(), nullable=False),
        sa.Column("contract_type", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column("status", sa.String(), nullable=False, server_default="uploaded"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_step", sa.String(), nullable=False, server_default="upload"),
        sa.Column(
            "completed_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("ocr_text", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contracts_user_id", "contracts", ["user_id"])
    op.create_index("ix_contracts_job_id", "contracts", ["job_id"], unique=True)
    op.create_index("ix_contracts_report_id", "contracts", ["report_id"], unique=True)

    # ── payments ─────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id"),
            nullable=True,
        ),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("merchant_uid", sa.String(), nullable=False, unique=True),
        sa.Column("portone_uid", sa.String(), nullable=True, unique=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_merchant_uid", "payments", ["merchant_uid"], unique=True)
    op.create_index("ix_payments_portone_uid", "payments", ["portone_uid"], unique=True)

    # ── user_quotas ──────────────────────────────────────────────────────────
    op.create_table(
        "user_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("quota_type", sa.String(), nullable=False, server_default="none"),
        sa.Column("remaining", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pass_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_user_quotas_user_id", "user_quotas", ["user_id"], unique=True)

    # ── special_clause_edits ─────────────────────────────────────────────────
    op.create_table(
        "special_clause_edits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id"),
            nullable=False,
        ),
        sa.Column("clause_id", sa.String(), nullable=False),
        sa.Column("edited_text", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_special_clause_edits_contract_id", "special_clause_edits", ["contract_id"])


def downgrade() -> None:
    op.drop_table("special_clause_edits")
    op.drop_table("user_quotas")
    op.drop_table("payments")
    op.drop_table("contracts")
    op.drop_table("users")
