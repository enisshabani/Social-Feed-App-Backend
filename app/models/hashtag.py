"""
KaPak - Hashtag Models
SQLAlchemy models for Hashtag and ContentHashtag (many-to-many join).
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Hashtag(Base):
    __tablename__ = "hashtags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    post_count = Column(Integer, default=0, nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    posts = relationship("ContentHashtag", backref="hashtag", cascade="all, delete-orphan")


class ContentHashtag(Base):
    __tablename__ = "content_hashtags"

    id = Column(Integer, primary_key=True, index=True)
    hashtag_id = Column(Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "post_id IS NOT NULL OR comment_id IS NOT NULL",
            name="ck_content_hashtag_has_target"
        ),
    )
