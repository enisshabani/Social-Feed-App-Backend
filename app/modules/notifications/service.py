from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.redis import get_or_set_cache, invalidate_cache
from app.models.notification_preference import NotificationPreference
from app.modules.notifications.exceptions import NotificationForbiddenError, NotificationNotFoundError
from app.modules.notifications.models import Notification, NotificationType


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
        invalidate_cache(f"unread_count:{self.tenant_id}:{recipient_id}")

    def mark_all_as_read(self, recipient_id: int) -> None:
        self.db.query(Notification).filter(
            Notification.recipient_id == recipient_id,
            Notification.tenant_id == self.tenant_id,
            not Notification.is_read
        ).update({"is_read": True})
        self.db.commit()
        invalidate_cache(f"unread_count:{self.tenant_id}:{recipient_id}")

    def delete_notification(self, notification_id: str, recipient_id: int) -> None:
        notification = self._get_notification(notification_id, recipient_id)
        self.db.delete(notification)
        self.db.commit()
        invalidate_cache(f"unread_count:{self.tenant_id}:{recipient_id}")

    def clear_notifications(self, recipient_id: int) -> int:
        deleted = self.db.query(Notification).filter(
            Notification.recipient_id == recipient_id,
            Notification.tenant_id == self.tenant_id
        ).delete(synchronize_session=False)
        self.db.commit()
        invalidate_cache(f"unread_count:{self.tenant_id}:{recipient_id}")
        return deleted

    def get_unread_count(self, recipient_id: int) -> int:
        def fetch():
            return self.db.query(func.count(Notification.id)).filter(
                Notification.recipient_id == recipient_id,
                Notification.tenant_id == self.tenant_id,
                not Notification.is_read
            ).scalar() or 0

        key = f"unread_count:{self.tenant_id}:{recipient_id}"
        return get_or_set_cache(key, 120, fetch)

    def get_preferences(self, user_id: int) -> NotificationPreference:
        pref = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.tenant_id == self.tenant_id
        ).first()

        if not pref:
            pref = NotificationPreference(user_id=user_id, tenant_id=self.tenant_id)
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)

        return pref

    def update_preferences(self, user_id: int, preferences) -> NotificationPreference:
        pref = self.get_preferences(user_id)

        pref.filter_not_following = preferences.filter_not_following
        pref.filter_not_followed_by = preferences.filter_not_followed_by
        pref.filter_new_accounts = preferences.filter_new_accounts
        pref.highlight_unread = preferences.highlight_unread
        pref.display_all_categories = preferences.display_all_categories

        self.db.commit()
        self.db.refresh(pref)
        return pref

