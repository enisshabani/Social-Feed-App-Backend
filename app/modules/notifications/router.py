from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

from app.modules.notifications.schemas import NotificationListResponse, MarkReadResponse, NotificationPreferenceSchema
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService

router = APIRouter(
    tags=["Notifications"],
)

def get_notification_service(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> NotificationService:
    return NotificationService(db=db, tenant_id=current_user.tenant_id)

@router.get(
    "", 
    response_model=NotificationListResponse, 
    summary="Get user notifications",
    description="Retrieve paginated notifications for the current user. Can be filtered by type and read status.",
    responses={
        200: {"description": "Successfully retrieved notifications"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"}
    }
)
def get_notifications(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max number of records to return"),
    type: Optional[NotificationType] = Query(None, description="Filter by notification type"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    items, unread_count, total = service.get_notifications(
        recipient_id=current_user.id,
        skip=skip,
        limit=limit,
        type_filter=type,
        is_read_filter=is_read
    )
    return NotificationListResponse(items=items, unread_count=unread_count, total=total)

@router.put(
    "/{notification_id}/read", 
    response_model=MarkReadResponse, 
    summary="Mark a notification as read",
    description="Mark a specific notification as read. Fails if the notification belongs to another user.",
    responses={
        200: {"description": "Successfully marked as read"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - You do not own this notification"},
        404: {"description": "Not Found - Notification does not exist"}
    }
)
def mark_as_read(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    service.mark_as_read(notification_id=notification_id, recipient_id=current_user.id)
    return MarkReadResponse(success=True, message="Notification marked as read")

@router.put(
    "/read-all", 
    response_model=MarkReadResponse, 
    summary="Mark all notifications as read",
    description="Mark all unread notifications for the current user as read in bulk.",
    responses={
        200: {"description": "Successfully marked all as read"},
        401: {"description": "Unauthorized"}
    }
)
def mark_all_as_read(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    service.mark_all_as_read(recipient_id=current_user.id)
    return MarkReadResponse(success=True, message="All notifications marked as read")

@router.delete(
    "/clear-all",
    response_model=MarkReadResponse,
    summary="Clear all notifications",
    description="Delete all notifications for the current user.",
    responses={
        200: {"description": "Successfully cleared notifications"},
        401: {"description": "Unauthorized"}
    }
)
def clear_notifications(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    deleted = service.clear_notifications(recipient_id=current_user.id)
    return MarkReadResponse(success=True, message=f"Cleared {deleted} notifications")

@router.delete(
    "/{notification_id}", 
    status_code=status.HTTP_204_NO_CONTENT, 
    summary="Delete a notification",
    description="Delete a specific notification. Fails if it does not belong to the user.",
    responses={
        204: {"description": "Successfully deleted notification"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - You do not own this notification"},
        404: {"description": "Not Found - Notification does not exist"}
    }
)
def delete_notification(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    service.delete_notification(notification_id=notification_id, recipient_id=current_user.id)

@router.get(
    "/unread-count", 
    summary="Get unread notification count",
    description="Get the total count of unread notifications for the current authenticated user.",
    responses={
        200: {"description": "Successfully retrieved count"},
        401: {"description": "Unauthorized"}
    }
)
def get_unread_count(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    count = service.get_unread_count(recipient_id=current_user.id)
    return {"unread_count": count}

@router.get(
    "/preferences",
    response_model=NotificationPreferenceSchema,
    summary="Get user notification preferences"
)
def get_preferences(
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    return service.get_preferences(user_id=current_user.id)

@router.put(
    "/preferences",
    response_model=NotificationPreferenceSchema,
    summary="Update user notification preferences"
)
def update_preferences(
    preferences: NotificationPreferenceSchema,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(get_current_user)
):
    return service.update_preferences(user_id=current_user.id, preferences=preferences)

