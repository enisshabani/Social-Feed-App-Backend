from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.exceptions import NotificationNotFoundError, NotificationForbiddenError

class NotificationService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _get_notification(self, notification_id: str, recipient_id: int) -> Notification:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.tenant_id == self.tenant_id
        ).first()
        
        if not notification:
            raise NotificationNotFoundError()
            
        if notification.recipient_id != recipient_id:
            raise NotificationForbiddenError()
            
        return notification

    def get_notifications(self, recipient_id: int, skip: int = 0, limit: int = 50, type_filter: Optional[NotificationType] = None, is_read_filter: Optional[bool] = None) -> tuple:
        query = self.db.query(Notification).filter(
            Notification.recipient_id == recipient_id,
            Notification.tenant_id == self.tenant_id
        )
        
        if type_filter is not None:
            query = query.filter(Notification.type == type_filter)
            
        if is_read_filter is not None:
            query = query.filter(Notification.is_read == is_read_filter)
            
        total = query.count()
        unread_count = self.get_unread_count(recipient_id)
        
        items = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
        return items, unread_count, total

    def mark_as_read(self, notification_id: str, recipient_id: int) -> None:
        notification = self._get_notification(notification_id, recipient_id)
        notification.is_read = True
        self.db.commit()

    def mark_all_as_read(self, recipient_id: int) -> None:
        self.db.query(Notification).filter(
            Notification.recipient_id == recipient_id,
            Notification.tenant_id == self.tenant_id,
            Notification.is_read == False
        ).update({"is_read": True})
        self.db.commit()

    def delete_notification(self, notification_id: str, recipient_id: int) -> None:
        notification = self._get_notification(notification_id, recipient_id)
        self.db.delete(notification)
        self.db.commit()

    def get_unread_count(self, recipient_id: int) -> int:
        return self.db.query(func.count(Notification.id)).filter(
            Notification.recipient_id == recipient_id,
            Notification.tenant_id == self.tenant_id,
            Notification.is_read == False
        ).scalar() or 0
