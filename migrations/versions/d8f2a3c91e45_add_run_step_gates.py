"""add run-step gate columns (verification + witness)

Revision ID: d8f2a3c91e45
Revises: c4e7a1f80b23
Create Date: 2026-09-28 00:30:00.000000

Run-time enforcement for verification-photo and second-signature steps.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd8f2a3c91e45'
down_revision = 'c4e7a1f80b23'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('protocol_run_steps', sa.Column('verification', sa.Text(), nullable=True))
    op.add_column('protocol_run_steps', sa.Column('witnessed_by', sa.String(length=255), nullable=True))
    op.add_column('protocol_run_steps', sa.Column('witnessed_by_user_id', sa.Integer(), nullable=True))
    op.add_column('protocol_run_steps', sa.Column('witnessed_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('protocol_run_steps', 'witnessed_at')
    op.drop_column('protocol_run_steps', 'witnessed_by_user_id')
    op.drop_column('protocol_run_steps', 'witnessed_by')
    op.drop_column('protocol_run_steps', 'verification')
