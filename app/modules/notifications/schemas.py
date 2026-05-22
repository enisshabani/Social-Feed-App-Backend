from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List
from app.modules.notifications.models import NotificationType

class NotificationResponse(BaseModel):
    id: str = Field(..., examples=["123e4567-e89b-12d3-a456-426614174000"])
    recipient_id: int = Field(..., examples=[1])
    actor_id: int = Field(..., examples=[2])
    type: NotificationType = Field(..., examples=[NotificationType.FOLLOW])
    entity_id: Optional[int] = Field(default=None, examples=[42])
    is_read: bool = Field(..., examples=[False])
    created_at: datetime = Field(..., examples=["2026-05-22T12:00:00Z"])

    model_config = ConfigDict(from_attributes=True)

class NotificationListResponse(BaseModel):
    items: List[NotificationResponse] = Field(..., examples=[[]])
    unread_count: int = Field(..., examples=[5])
    total: int = Field(..., examples=[20])

class MarkReadResponse(BaseModel):
    success: bool = Field(..., examples=[True])
    message: str = Field(..., examples=["Notifications marked as read"])
