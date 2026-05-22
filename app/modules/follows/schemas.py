from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class FollowResponse(BaseModel):
    id: str = Field(..., examples=["123e4567-e89b-12d3-a456-426614174000"])
    follower_id: int = Field(..., examples=[1])
    followee_id: int = Field(..., examples=[2])
    created_at: datetime = Field(..., examples=["2026-05-22T12:00:00Z"])
    
    model_config = ConfigDict(from_attributes=True)

class FollowCountResponse(BaseModel):
    followers_count: int = Field(..., examples=[150])
    following_count: int = Field(..., examples=[45])

class IsFollowingResponse(BaseModel):
    is_following: bool = Field(..., examples=[True])
