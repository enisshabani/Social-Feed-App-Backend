"""
KaPak - Posts & Feed Schemas
Pydantic models for data validation and API payloads.
"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

# ==========================================
# POST SCHEMAS
# ==========================================
class PostBase(BaseModel):
    content: str

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    content: Optional[str] = None

class PostResponse(PostBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# COMMENT SCHEMAS
# ==========================================
class CommentBase(BaseModel):
    content: str
    post_id: int

class CommentCreate(CommentBase):
    pass

class CommentResponse(CommentBase):
    id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# LIKE SCHEMAS
# ==========================================
class LikeCreate(BaseModel):
    post_id: Optional[int] = None
    comment_id: Optional[int] = None

class LikeResponse(BaseModel):
    id: int
    user_id: int
    post_id: Optional[int]
    comment_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# REPOST SCHEMAS
# ==========================================
class RepostCreate(BaseModel):
    original_post_id: int

class RepostResponse(BaseModel):
    id: int
    user_id: int
    original_post_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
