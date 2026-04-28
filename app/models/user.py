"""
KaPak - User Model
SQLAlchemy model for the users table.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Enum as SQLEnum
)
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    """User roles for role-based authorization."""
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class User(Base):
    """User model - core entity for authentication and profiles."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Profile info
    display_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    location = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)

    # Role-based authorization
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Multi-tenancy support
    tenant_id = Column(String(50), default="default", nullable=False, index=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
