"""add verification_runs and verification_results

Revision ID: b2c4d5e6f7a8
Revises: a1f3c0b9d2e4
Create Date: 2026-08-09 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a1f3c0b9d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('verification_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('investigation_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('candidate_count', sa.Integer(), nullable=False),
    sa.Column('verified_count', sa.Integer(), nullable=False),
    sa.Column('contradicted_count', sa.Integer(), nullable=False),
    sa.Column('unverified_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_runs_investigation_id'), 'verification_runs', ['investigation_id'], unique=False)
    op.create_table('verification_results',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('investigation_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('checks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['root_cause_candidates.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['verification_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_results_investigation_id'), 'verification_results', ['investigation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_verification_results_investigation_id'), table_name='verification_results')
    op.drop_table('verification_results')
    op.drop_index(op.f('ix_verification_runs_investigation_id'), table_name='verification_runs')
    op.drop_table('verification_runs')
