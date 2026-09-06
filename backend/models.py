"""
SQLAlchemy models for the news aggregation application.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class RSSSource(Base):
    """Model for RSS feed sources."""
    __tablename__ = "rss_sources"

    rss_id = Column(Integer, primary_key=True, index=True)
    rss_title = Column(String(255), nullable=False)
    rss_link = Column(String(1024), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    posts = relationship("Post", back_populates="rss_source")


class Post(Base):
    """Model for news posts."""
    __tablename__ = "posts"

    post_id = Column(String(512), primary_key=True)
    rss_id = Column(Integer, ForeignKey("rss_sources.rss_id"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    image_id = Column(String(512), nullable=True)
    telegram_channel_id = Column(Integer, nullable=True)  # 1=child, 2=women, 3=man

    rss_source = relationship("RSSSource", back_populates="posts")


class PostCategory(Base):
    """Model for post category relationships (classification history)."""
    __tablename__ = "post_categories"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(512), ForeignKey("posts.post_id"), nullable=False)
    category_id = Column(Integer, nullable=False)  # Same as telegram_channel_id
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('post_id', 'category_id', name='uq_post_category'),
    )
