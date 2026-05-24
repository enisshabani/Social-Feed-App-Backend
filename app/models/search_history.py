"""
KaPak - SearchHistory Model
Logs user search queries for analytics and personalisation.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class SearchHistory(Base):
    __tablename__ = "search_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(String(500), nullable=False)
    search_type = Column(String(20), nullable=False, default="posts")
    result_count = Column(Integer, default=0)
    tenant_id = Column(String(50), default="default", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
