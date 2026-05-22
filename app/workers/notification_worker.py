import logging
from sqlalchemy.orm import Session
from app.modules.notifications.models import Notification, NotificationType

logger = logging.getLogger("kapak.workers.notifications")

class NotificationWorker:
    def __init__(self, db: Session):
        self.db = db

    def _create_notification(self, type_: NotificationType, actor_id: int, recipient_id: int, tenant_id: str, entity_id: int = None):
        try:
            # Skip self-notifications
            if str(actor_id) == str(recipient_id):
                logger.info(f"Skipping self-notification for user {actor_id}")
                return

            notification = Notification(
                type=type_,
                actor_id=str(actor_id),
                recipient_id=str(recipient_id),
                tenant_id=str(tenant_id),
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
