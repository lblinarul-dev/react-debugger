"""Initial migration - create rss_sources, posts, and post_categories tables.

Revision ID: initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create rss_sources table
    op.create_table(
        'rss_sources',
        sa.Column('rss_id', sa.Integer(), nullable=False),
        sa.Column('rss_title', sa.String(length=255), nullable=False),
        sa.Column('rss_link', sa.String(length=1024), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('rss_id'),
        sa.UniqueConstraint('rss_link')
    )
    op.create_index(op.f('ix_rss_sources_rss_id'), 'rss_sources', ['rss_id'], unique=False)

    # Create posts table
    op.create_table(
        'posts',
        sa.Column('post_id', sa.String(length=512), nullable=False),
        sa.Column('rss_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('image_id', sa.String(length=512), nullable=True),
        sa.Column('telegram_channel_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['rss_id'], ['rss_sources.rss_id'], ),
        sa.PrimaryKeyConstraint('post_id')
    )

    # Create post_categories table
    op.create_table(
        'post_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.String(length=512), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'category_id', name='uq_post_category'),
        sa.ForeignKeyConstraint(['post_id'], ['posts.post_id'], )
    )
    op.create_index(op.f('ix_post_categories_id'), 'post_categories', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_post_categories_id'), table_name='post_categories')
    op.drop_table('post_categories')
    op.drop_table('posts')
    op.drop_index(op.f('ix_rss_sources_rss_id'), table_name='rss_sources')
    op.drop_table('rss_sources')
