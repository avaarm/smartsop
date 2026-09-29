"""add protocol facility document taxonomy fields

Mirror a real GMP facility's filing structure:
  - doc_category: the controlled-document category code (EQ, QA, TM, VP, BR, …)
  - product_code: protocol / part number that groups batch records (e.g. B090)

Revision ID: b2d3e4f5a6c7
Revises: a1c2d3e4f5b6
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "b2d3e4f5a6c7"
down_revision = "a1c2d3e4f5b6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("protocols") as batch_op:
        batch_op.add_column(sa.Column("doc_category", sa.String(length=10),
                                      server_default="", nullable=True))
        batch_op.add_column(sa.Column("product_code", sa.String(length=60),
                                      server_default="", nullable=True))
        batch_op.create_index("ix_protocols_doc_category", ["doc_category"])


def downgrade():
    with op.batch_alter_table("protocols") as batch_op:
        batch_op.drop_index("ix_protocols_doc_category")
        batch_op.drop_column("product_code")
        batch_op.drop_column("doc_category")
