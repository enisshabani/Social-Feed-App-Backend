"""
KaPak - Posts & Feed Schemas
Pydantic models for data validation and API request/response payloads.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublicResponse

# ==========================================
# MEDIA SCHEMAS
# ==========================================

class MediaCreate(BaseModel):
    url: str
    media_type: str = "image"
    meta: Optional[dict] = None

class MediaResponse(BaseModel):
    id: int
    post_id: int
    url: str
    media_type: str
    meta: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# POLL SCHEMAS
# ==========================================

class PollCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=280)
    options: List[str] = Field(..., min_length=2, max_length=4)

class PollOptionResponse(BaseModel):
    id: int
    poll_id: int
    text: str
    vote_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class PollResponse(BaseModel):
    id: int
    post_id: int
    question: str
    options: List[PollOptionResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PollVoteRequest(BaseModel):
    option_id: int


# ==========================================
# TAG SCHEMAS
# ==========================================

class TagResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# COMMENT SCHEMAS
# ==========================================

class CommentCreate(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: int
    content: str
    post_id: int
    author_id: int
    author: Optional[UserPublicResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# LIKE SCHEMAS
# ==========================================

class LikeResponse(BaseModel):
    id: int
    user_id: int
    post_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# REPOST SCHEMAS
# ==========================================

class RepostResponse(BaseModel):
    id: int
    user_id: int
    original_post_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# POST SCHEMAS
# ==========================================

class PostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    visibility: str = "public"
    reply_to_post_id: Optional[int] = None
    media: List[MediaCreate] = []
    poll: Optional[PollCreate] = None

class PostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    visibility: Optional[str] = None
    media: Optional[List[MediaCreate]] = None

class PostResponse(BaseModel):
    id: int
    content: str
    content_html: Optional[str] = None
    author_id: int
    author: Optional[UserPublicResponse] = None
    visibility: str
    reply_to_post_id: Optional[int] = None
    is_repost: bool = False
    original_post_id: Optional[int] = None
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    tenant_id: str = "default"
    created_at: datetime
    updated_at: Optional[datetime] = None

    comments: List[CommentResponse] = []
    likes: List[LikeResponse] = []
    reposts: List[RepostResponse] = []
    media: List[MediaResponse] = []
    tags: List[TagResponse] = []
    poll: Optional[PollResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PostBriefResponse(BaseModel):
    """Lighter version of PostResponse for feed listings."""
    id: int
    content: str
    content_html: Optional[str] = None
    author_id: int
    author: Optional[UserPublicResponse] = None
    visibility: str
    is_repost: bool = False
    original_post_id: Optional[int] = None
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    created_at: datetime
    likes: List[LikeResponse] = []
    reposts: List[RepostResponse] = []
    media: List[MediaResponse] = []
    tags: List[TagResponse] = []
    poll: Optional[PollResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# DRAFT SCHEMAS
# ==========================================

class DraftCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

class DraftUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=5000)

class DraftResponse(BaseModel):
    id: int
    content: str
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# SAVED POST (BOOKMARK) SCHEMAS
# ==========================================

class SavedPostResponse(BaseModel):
    id: int
    user_id: int
    post_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# POST EDIT HISTORY SCHEMAS
# ==========================================

class PostEditHistoryResponse(BaseModel):
    id: int
    post_id: int
    old_content: str
    new_content: str
    edited_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# HASHTAG STATS SCHEMAS
# ==========================================

class HashtagStatsResponse(BaseModel):
    id: int
    tag_id: int
    tag: Optional[TagResponse] = None
    usage_count: int
    period: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# FEED / TIMELINE SCHEMAS
# ==========================================

class FeedResponse(BaseModel):
    """Paginated feed response with cursor support."""
    items: List[PostBriefResponse] = []
    next_cursor: Optional[str] = None
    has_more: bool = False


# ==========================================
# SEARCH SCHEMAS
# ==========================================

class SearchRequest(BaseModel):
    q: Optional[str] = None
    tags: Optional[str] = None
    author_id: Optional[int] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


# ==========================================
# AI REFINEMENT SCHEMAS
# ==========================================

class AIRefineRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    style: str = "casual"

class AIRefineResponse(BaseModel):
    refined_content: str

