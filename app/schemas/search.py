"""
KaPak - Search Schemas
Pydantic models for search request/response payloads.
"""

from typing import List, Optional

from pydantic import BaseModel

from app.schemas.hashtag import HashtagResponse
from app.schemas.post import PostResponse
from app.schemas.user import UserPublicResponse


class MatchedComment(BaseModel):
    id: int
    snippet: str
    author: UserPublicResponse


class MatchContext(BaseModel):
    post_match: bool = False
    matched_comments: List[MatchedComment] = []


class SearchPostItem(PostResponse):
    match_context: Optional[MatchContext] = None


class SearchPostsResult(BaseModel):
    items: List[SearchPostItem] = []
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
