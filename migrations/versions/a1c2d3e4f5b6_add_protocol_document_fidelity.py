"""add protocol document-fidelity fields

Preserve uploaded controlled documents (batch records, CMC sections, forms)
1-to-1 as structured blocks instead of flattening them into steps:
  - doc_format: "steps" (procedure) | "document" (rich controlled doc)
  - body_json: ordered blocks (headings, paragraphs, tables, checkboxes)
  - original_filename / original_file: the raw upload, for byte-faithful export

Revision ID: a1c2d3e4f5b6
Revises: e5a91c7b3f60
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "a1c2d3e4f5b6"
down_revision = "e5a91c7b3f60"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("protocols") as batch_op:
        batch_op.add_column(sa.Column("doc_format", sa.String(length=20),
                                      server_default="steps", nullable=True))
        batch_op.add_column(sa.Column("body_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("original_filename", sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column("original_file", sa.LargeBinary(), nullable=True))


def downgrade():
    with op.batch_alter_table("protocols") as batch_op:
        batch_op.drop_column("original_file")
        batch_op.drop_column("original_filename")
        batch_op.drop_column("body_json")
        batch_op.drop_column("doc_format")
