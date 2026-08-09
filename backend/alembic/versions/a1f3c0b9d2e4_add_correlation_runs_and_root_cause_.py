"""add correlation_runs and root_cause_candidates

Revision ID: a1f3c0b9d2e4
Revises: cdff2753017b
Create Date: 2026-08-09 14:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1f3c0b9d2e4'
down_revision: Union[str, Sequence[str], None] = 'cdff2753017b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('correlation_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('investigation_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('failed_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('candidate_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_correlation_runs_investigation_id'), 'correlation_runs', ['investigation_id'], unique=False)
    op.create_table('root_cause_candidates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('investigation_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('root_cause_type', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('summary', sa.String(length=1024), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('evidence_chain', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('related_services', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['correlation_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_root_cause_candidates_investigation_id'), 'root_cause_candidates', ['investigation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_root_cause_candidates_investigation_id'), table_name='root_cause_candidates')
    op.drop_table('root_cause_candidates')
    op.drop_index(op.f('ix_correlation_runs_investigation_id'), table_name='correlation_runs')
    op.drop_table('correlation_runs')
