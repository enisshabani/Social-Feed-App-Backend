"""
KaPak - Hashtag Schemas
Pydantic models for data validation and API payloads.
"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class HashtagCreate(BaseModel):
    name: str


class HashtagResponse(BaseModel):
    id: int
    name: str
    post_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentHashtagResponse(BaseModel):
    id: int
    hashtag_id: int
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
