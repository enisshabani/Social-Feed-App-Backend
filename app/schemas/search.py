"""
KaPak - Search Schemas
Pydantic models for search request/response payloads.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from app.schemas.post import PostResponse
from app.schemas.user import UserPublicResponse
from app.schemas.hashtag import HashtagResponse


class SearchPostsResult(BaseModel):
    items: List[PostResponse] = []
    total: int = 0
    offset: int = 0
    limit: int = 20


class SearchUsersResult(BaseModel):
    items: List[UserPublicResponse] = []
    total: int = 0
    offset: int = 0
    limit: int = 20


class SearchHashtagsResult(BaseModel):
    items: List[HashtagResponse] = []
    total: int = 0
    offset: int = 0
    limit: int = 20
