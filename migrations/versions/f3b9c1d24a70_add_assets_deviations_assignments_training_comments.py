"""add assets, deviations, assignments, training_records, comments

Revision ID: f3b9c1d24a70
Revises: a37479d1fb5d
Create Date: 2026-09-07 00:00:00.000000

Adds the tables introduced with the asset library, CAPA/deviations,
scheduling, competency, and comments features. Production runs with
AUTO_CREATE_TABLES disabled, so these must exist as a migration.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b9c1d24a70'
down_revision = 'a37479d1fb5d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('asset_tag', sa.String(length=100), nullable=True),
        sa.Column('qr_slug', sa.String(length=40), nullable=False),
        sa.Column('location', sa.String(length=300), nullable=True),
        sa.Column('manufacturer', sa.String(length=200), nullable=True),
        sa.Column('model', sa.String(length=200), nullable=True),
        sa.Column('hazard_class', sa.String(length=200), nullable=True),
        sa.Column('energy_sources_json', sa.Text(), nullable=True),
        sa.Column('protocol_ids_json', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_assets_qr_slug', 'assets', ['qr_slug'], unique=True)

    op.create_table(
        'training_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('protocol_id', sa.Integer(), nullable=False),
        sa.Column('protocol_title', sa.String(length=500), nullable=True),
        sa.Column('protocol_version', sa.Integer(), nullable=True),
        sa.Column('trainee', sa.String(length=255), nullable=True),
        sa.Column('trainee_user_id', sa.Integer(), nullable=True),
        sa.Column('assigned_by', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('acknowledgement', sa.String(length=300), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['protocol_id'], ['protocols.id'], ),
        sa.ForeignKeyConstraint(['trainee_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('protocol_id', sa.Integer(), nullable=False),
        sa.Column('step_id', sa.Integer(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('author_user_id', sa.Integer(), nullable=True),
        sa.Column('is_pinned', sa.Boolean(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True),
        sa.Column('resolved_by', sa.String(length=255), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['protocol_id'], ['protocols.id'], ),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('protocol_id', sa.Integer(), nullable=False),
        sa.Column('protocol_title', sa.String(length=500), nullable=True),
        sa.Column('assigned_to', sa.String(length=255), nullable=True),
        sa.Column('assigned_by', sa.String(length=255), nullable=True),
        sa.Column('due_date', sa.String(length=30), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('recurrence', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['protocol_id'], ['protocols.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'deviations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('protocol_id', sa.Integer(), nullable=True),
        sa.Column('run_id', sa.Integer(), nullable=True),
        sa.Column('run_step_id', sa.Integer(), nullable=True),
        sa.Column('step_title', sa.String(length=500), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('corrective_action', sa.Text(), nullable=True),
        sa.Column('reported_by', sa.String(length=255), nullable=True),
        sa.Column('reported_by_user_id', sa.Integer(), nullable=True),
        sa.Column('assigned_to', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['protocol_id'], ['protocols.id'], ),
        sa.ForeignKeyConstraint(['run_id'], ['protocol_runs.id'], ),
        sa.ForeignKeyConstraint(['reported_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('deviations')
    op.drop_table('assignments')
    op.drop_table('comments')
    op.drop_table('training_records')
    op.drop_index('ix_assets_qr_slug', table_name='assets')
    op.drop_table('assets')
