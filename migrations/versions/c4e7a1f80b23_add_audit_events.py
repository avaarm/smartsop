"""add audit_events

Revision ID: c4e7a1f80b23
Revises: f3b9c1d24a70
Create Date: 2026-09-28 00:00:00.000000

The immutable audit trail (21 CFR Part 11 / ISO 9001 / GxP).
"""
from alembic import op
import sqlalchemy as sa


revision = 'c4e7a1f80b23'
down_revision = 'f3b9c1d24a70'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=60), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('summary', sa.String(length=500), nullable=True),
        sa.Column('detail_json', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=255), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_events_account_id', 'audit_events', ['account_id'])
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'])


def downgrade():
    op.drop_index('ix_audit_events_created_at', table_name='audit_events')
    op.drop_index('ix_audit_events_account_id', table_name='audit_events')
    op.drop_table('audit_events')
