"""add protocol template flags (is_template, template_category)

Revision ID: e5a91c7b3f60
Revises: d8f2a3c91e45
Create Date: 2026-09-28 01:00:00.000000

Lets an org save its own documents as reusable, document-type-categorized
templates to start new projects from.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5a91c7b3f60'
down_revision = 'd8f2a3c91e45'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('protocols', sa.Column('is_template', sa.Boolean(), nullable=False,
                                         server_default=sa.false()))
    op.add_column('protocols', sa.Column('template_category', sa.String(length=120), nullable=True))
    op.create_index('ix_protocols_is_template', 'protocols', ['is_template'])


def downgrade():
    op.drop_index('ix_protocols_is_template', table_name='protocols')
    op.drop_column('protocols', 'template_category')
    op.drop_column('protocols', 'is_template')
