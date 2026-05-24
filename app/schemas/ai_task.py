"""
KaPak - AI Task Schemas
Pydantic models for AI task request/response payloads.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AiTaskCreate(BaseModel):
    task_type: str
    input_data: Optional[dict] = None


class AiTaskResponse(BaseModel):
    id: int
    task_type: str
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    user_id: int
    tenant_id: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskStatusResponse(BaseModel):
    task_id: int
    task_type: str
    status: str
    output_data: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class SuggestHashtagsRequest(BaseModel):
    post_text: str = Field(..., min_length=1, max_length=5000)


class AnalyzeSentimentRequest(BaseModel):
    post_text: str = Field(..., min_length=1, max_length=5000)
