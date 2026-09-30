"""add protocol document_number (auto-assigned controlled-doc number)

Controlled-document number auto-assigned from the category (EQ-002, QA-005, …)
per the facility's numbering system (DC-002).

Revision ID: c3e4f5a6b7d8
Revises: b2d3e4f5a6c7
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "c3e4f5a6b7d8"
down_revision = "b2d3e4f5a6c7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("protocols") as batch_op:
        batch_op.add_column(sa.Column("document_number", sa.String(length=40),
                                      server_default="", nullable=True))
        batch_op.create_index("ix_protocols_document_number", ["document_number"])


def downgrade():
    with op.batch_alter_table("protocols") as batch_op:
        batch_op.drop_index("ix_protocols_document_number")
        batch_op.drop_column("document_number")
