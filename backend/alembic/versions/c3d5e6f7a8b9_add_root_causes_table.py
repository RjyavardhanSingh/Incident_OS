"""add root_causes table

Revision ID: c3d5e6f7a8b9
Revises: b2c4d5e6f7a8
Create Date: 2026-08-09 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b2c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('root_causes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('investigation_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=True),
    sa.Column('selection_mode', sa.String(length=16), nullable=False),
    sa.Column('root_cause_type', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('summary', sa.String(length=1024), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('evidence_chain', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('related_services', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('reasoning', sa.String(length=1024), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['root_cause_candidates.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['investigation_id'], ['investigations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('investigation_id', name='uq_root_cause_investigation')
    )
    op.create_index(op.f('ix_root_causes_investigation_id'), 'root_causes', ['investigation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_root_causes_investigation_id'), table_name='root_causes')
    op.drop_table('root_causes')
