import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean, Enum, Index
from app.core.database import Base

class NotificationType(str, enum.Enum):
    FOLLOW = "FOLLOW"
    LIKE = "LIKE"
    REPOST = "REPOST"
    MENTION = "MENTION"
    COMMENT = "COMMENT"

class Notification(Base):
    __tablename__ = "notifications"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Multi-tenancy
    tenant_id = Column(String(36), nullable=False, index=True)

    # Foreign Keys referencing users table (with cascade deletes and indexes)
    recipient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Notification metadata
    type = Column(Enum(NotificationType), nullable=False, index=True)
    entity_id = Column(String(36), nullable=True, index=True)  # ID of the post/comment/etc
    is_read = Column(Boolean, default=False, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Constraints & Table Arguments
    __table_args__ = (
        Index("ix_notifications_tenant_recipient", "tenant_id", "recipient_id"),
        Index("ix_notifications_tenant_unread", "tenant_id", "recipient_id", "is_read"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type}, recipient_id={self.recipient_id}, is_read={self.is_read}, tenant_id={self.tenant_id})>"
