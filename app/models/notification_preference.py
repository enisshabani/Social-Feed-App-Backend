import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
from app.core.database import Base

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Multi-tenancy
    tenant_id = Column(String(36), nullable=False, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    user = relationship("User", backref="notification_preference", foreign_keys=[user_id])

    # Preferences - Manage notifications from...
    filter_not_following = Column(Boolean, default=False, nullable=False)
    filter_not_followed_by = Column(Boolean, default=False, nullable=False)
    filter_new_accounts = Column(Boolean, default=False, nullable=False)
    
    # Preferences - Unread notifications
    highlight_unread = Column(Boolean, default=True, nullable=False)

    # Preferences - Quick filter bar
    display_all_categories = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    __table_args__ = (
        Index("ix_notification_preferences_tenant_user", "tenant_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(user_id={self.user_id})>"
