from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

from app.modules.notifications.schemas import NotificationListResponse, MarkReadResponse
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)

def get_notification_service(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> NotificationService:
    return NotificationService(db=db, tenant_id=current_user.tenant_id)

@router.get("", response_model=NotificationListResponse, summary="Get user notifications")
def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    type: Optional[NotificationType] = Query(None, description="Filter by notification type"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve paginated notifications for the current user.
    Can be filtered by type and read status.
    """
    items, unread_count, total = service.get_notifications(
        recipient_id=current_user.id,
        skip=skip,
        limit=limit,
        type_filter=type,
        is_read_filter=is_read
    )
    return NotificationListResponse(items=items, unread_count=unread_count, total=total)

@router.put("/{notification_id}/read", response_model=MarkReadResponse, summary="Mark a notification as read")
def mark_as_read(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    """
    service.mark_as_read(notification_id=notification_id, recipient_id=current_user.id)
    return MarkReadResponse(success=True, message="Notification marked as read")

@router.put("/read-all", response_model=MarkReadResponse, summary="Mark all notifications as read")
def mark_all_as_read(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    """
    Mark all unread notifications for the current user as read.
    """
    service.mark_all_as_read(recipient_id=current_user.id)
    return MarkReadResponse(success=True, message="All notifications marked as read")

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a notification")
def delete_notification(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a specific notification.
    """
    service.delete_notification(notification_id=notification_id, recipient_id=current_user.id)

@router.get("/unread-count", summary="Get unread notification count")
def get_unread_count(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get the total count of unread notifications for the current user.
    """
    count = service.get_unread_count(recipient_id=current_user.id)
    return {"unread_count": count}
