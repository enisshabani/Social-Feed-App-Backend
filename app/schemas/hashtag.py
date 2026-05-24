"""
KaPak - Hashtag Schemas
Pydantic models for data validation and API payloads.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class HashtagCreate(BaseModel):
    name: str


class HashtagResponse(BaseModel):
    id: int
    name: str
    mention_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HashtagHistoryItem(BaseModel):
    day: str
    uses: int
    accounts: int


class HashtagTrendingResponse(HashtagResponse):
    history: list[HashtagHistoryItem] = []


class TrendingPostResponse(BaseModel):
    id: int
    content: str
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    interaction_count: int

    model_config = ConfigDict(from_attributes=True)


class ContentHashtagResponse(BaseModel):
    id: int
    hashtag_id: int
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
