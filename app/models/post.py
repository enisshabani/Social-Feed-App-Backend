"""
KaPak - Posts & Feed Models
SQLAlchemy models for Posts, Comments, Likes, Reposts,
Media, Tags, Drafts, Saved Posts, Edit History, and Timeline.
"""

import enum

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base, TenantMixin

# ==========================================
# ENUMS
# ==========================================

class PostVisibility(str, enum.Enum):
    """Post visibility options."""
    PUBLIC = "public"
    UNLISTED = "unlisted"
    FOLLOWERS = "followers"
    DIRECT = "direct"


class MediaType(str, enum.Enum):
    """Supported media types for post attachments."""
    IMAGE = "image"
    VIDEO = "video"


# ==========================================
# CORE POST MODEL
# ==========================================

class Post(TenantMixin, Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    content_html = Column(Text, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    visibility = Column(SQLEnum(PostVisibility), default=PostVisibility.PUBLIC, nullable=False)

    # Reply support
    reply_to_post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)

    # Repost support
    is_repost = Column(Boolean, default=False)
    original_post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)

    # Denormalized counters for performance
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    repost_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    author = relationship("User", backref="posts")
    comments = relationship("Comment", backref="post", cascade="all, delete-orphan",
                            foreign_keys="Comment.post_id")
    likes = relationship("PostLike", backref="post", cascade="all, delete-orphan")
    reposts = relationship("PostRepost", backref="original_post", cascade="all, delete-orphan")
    media = relationship("Media", backref="post", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary="post_tags", backref="posts")
    edit_history = relationship("PostEditHistory", backref="post", cascade="all, delete-orphan")
    attachments = relationship("PostAttachment", backref="post", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Post(id={self.id}, author_id={self.author_id})>"


# ==========================================
# COMMENT MODEL
# ==========================================

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    author = relationship("User", backref="comments")

    def __repr__(self):
        return f"<Comment(id={self.id}, post_id={self.post_id})>"


# ==========================================
# LIKE MODEL (renamed from Like to PostLike)
# ==========================================

class PostLike(Base):
    __tablename__ = "post_likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="post_likes")

    def __repr__(self):
        return f"<PostLike(user_id={self.user_id}, post_id={self.post_id})>"


# ==========================================
# REPOST MODEL (renamed from Repost to PostRepost)
# ==========================================

class PostRepost(Base):
    __tablename__ = "post_reposts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="post_reposts")

    def __repr__(self):
        return f"<PostRepost(user_id={self.user_id}, post_id={self.original_post_id})>"


# ==========================================
# MEDIA MODEL
# ==========================================

class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    media_type = Column(SQLEnum(MediaType), default=MediaType.IMAGE, nullable=False)
    meta = Column(JSON, nullable=True)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Media(id={self.id}, type={self.media_type})>"


# ==========================================
# TAG / HASHTAG MODEL
# ==========================================

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Tag(name={self.name})>"


# ==========================================
# POST-TAG MANY-TO-MANY
# ==========================================

class PostTag(Base):
    __tablename__ = "post_tags"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)


# ==========================================
# DRAFT MODEL
# ==========================================

class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    author = relationship("User", backref="drafts")

    def __repr__(self):
        return f"<Draft(id={self.id}, author_id={self.author_id})>"


# ==========================================
# SAVED POST (BOOKMARKS)
# ==========================================

class SavedPost(Base):
    __tablename__ = "saved_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="saved_posts")
    post = relationship("Post", backref="saved_by")

    def __repr__(self):
        return f"<SavedPost(user_id={self.user_id}, post_id={self.post_id})>"


# ==========================================
# POST EDIT HISTORY
# ==========================================

class PostEditHistory(Base):
    __tablename__ = "post_edit_history"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    old_content = Column(Text, nullable=False)
    new_content = Column(Text, nullable=False)
    edited_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PostEditHistory(post_id={self.post_id})>"


# ==========================================
# HASHTAG STATS (for trending)
# ==========================================

class HashtagStats(Base):
    __tablename__ = "hashtag_stats"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    usage_count = Column(Integer, default=0)
    period = Column(String(20), default="daily")

    tenant_id = Column(String(50), default="default", index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tag = relationship("Tag", backref="stats")

    def __repr__(self):
        return f"<HashtagStats(tag_id={self.tag_id}, count={self.usage_count})>"


# ==========================================
# TIMELINE ITEM (for fan-out feed)
# ==========================================

class TimelineItem(Base):
    __tablename__ = "timeline_items"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    originator_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("Post", backref="timeline_entries")

    def __repr__(self):
        return f"<TimelineItem(owner={self.owner_user_id}, post={self.post_id})>"


# ==========================================
# POST ATTACHMENT
# ==========================================

class PostAttachment(Base):
    __tablename__ = "post_attachments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)

    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PostAttachment(id={self.id}, post_id={self.post_id})>"
