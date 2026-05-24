import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference
from app.models.user import User
from app.modules.follows.models import Follow
from app.modules.notifications.models import Notification, NotificationType

logger = logging.getLogger("kapak.workers.notifications")

class NotificationWorker:
    def __init__(self, db: Session):
        self.db = db

    def _create_notification(self, type_: NotificationType, actor_id: int, recipient_id: int, tenant_id: str, entity_id: int = None):
        try:
            # Skip self-notifications
            if actor_id == recipient_id:
                logger.info(f"Skipping self-notification for user {actor_id}")
                return

            # Check Preferences
            pref = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == recipient_id,
                NotificationPreference.tenant_id == tenant_id
            ).first()

            if pref:
                if pref.filter_not_following:
                    # Does recipient follow actor?
                    is_following = self.db.query(Follow).filter(
                        Follow.follower_id == recipient_id,
                        Follow.followee_id == actor_id,
                        Follow.tenant_id == tenant_id
                    ).first()
                    if not is_following:
                        logger.info(f"Filtered: recipient {recipient_id} does not follow actor {actor_id}")
                        return

                if pref.filter_not_followed_by:
                    # Does actor follow recipient?
                    is_followed_by = self.db.query(Follow).filter(
                        Follow.follower_id == actor_id,
                        Follow.followee_id == recipient_id,
                        Follow.tenant_id == tenant_id
                    ).first()
                    if not is_followed_by:
                        logger.info(f"Filtered: actor {actor_id} does not follow recipient {recipient_id}")
                        return

                if pref.filter_new_accounts:
                    actor = self.db.query(User).filter(User.id == actor_id).first()
                    if actor and (datetime.now(timezone.utc) - actor.created_at) < timedelta(days=7):
                        logger.info(f"Filtered: actor {actor_id} is a new account")
                        return

            notification = Notification(
                type=type_,
                actor_id=actor_id,
                recipient_id=recipient_id,
                tenant_id=tenant_id,
                entity_id=str(entity_id) if entity_id else None
            )
            self.db.add(notification)
            self.db.commit()
            logger.info(f"Successfully created {type_.name} notification for user {recipient_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create {type_.name} notification for user {recipient_id}: {str(e)}")

    def create_follow_notification(self, actor_id: int, recipient_id: int, tenant_id: str):
        self._create_notification(NotificationType.FOLLOW, actor_id, recipient_id, tenant_id)

    def create_like_notification(self, actor_id: int, recipient_id: int, post_id: int, tenant_id: str):
        self._create_notification(NotificationType.LIKE, actor_id, recipient_id, tenant_id, entity_id=post_id)

    def create_mention_notification(self, actor_id: int, recipient_id: int, post_id: int, tenant_id: str):
        self._create_notification(NotificationType.MENTION, actor_id, recipient_id, tenant_id, entity_id=post_id)


def process_follow_notification(actor_id: int, recipient_id: int, tenant_id: str):
    """Entry point for FastAPI BackgroundTasks"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        worker = NotificationWorker(db)
        worker.create_follow_notification(actor_id, recipient_id, tenant_id)
    finally:
        db.close()
