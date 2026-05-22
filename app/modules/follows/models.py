import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, ForeignKey, DateTime, UniqueConstraint, Index
from app.core.database import Base

class Follow(Base):
    __tablename__ = "follows"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Multi-tenancy
    tenant_id = Column(String(36), nullable=False, index=True)

    # Foreign Keys referencing users table (with cascade deletes and indexes)
    follower_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    followee_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Constraints & Table Arguments
    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", "tenant_id", name="uq_follow_tenant"),
        Index("ix_follows_tenant_follower", "tenant_id", "follower_id"),
        Index("ix_follows_tenant_followee", "tenant_id", "followee_id"),
    )

    def __repr__(self) -> str:
        return f"<Follow(id={self.id}, follower_id={self.follower_id}, followee_id={self.followee_id}, tenant_id={self.tenant_id})>"
