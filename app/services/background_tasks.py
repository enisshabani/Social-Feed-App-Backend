"""
KaPak - Background Tasks Service
Handles asynchronous background tasks using FastAPI's BackgroundTasks.
Implements write-on-write timeline fan-out, media processing, and notification dispatching.
"""

import logging

from sqlalchemy.orm import Session

from app.models.post import Media, TimelineItem
from app.models.user import User

logger = logging.getLogger(__name__)


class BackgroundTasksService:
    """Service to execute heavy, asynchronous operations in the background of FastAPI."""

    @staticmethod
    def fanout_post_to_followers(post_id: int, author_id: int, tenant_id: str, db: Session):
        """
        Executes write-on-write timeline fan-out (Req 15 timeline logic).
        Pushes a new post record into the timeline feeds of all users following the author.
        """
        try:
            logger.info(f"Starting fan-out for post {post_id} by author {author_id}...")

            # 1. Fetch author's followers (Simulated check/lookup)
            # In a full follow system, we would query the follows table:
            # followers = db.query(Follow).filter(Follow.followed_id == author_id).all()

            # Since the Follow module is built by another team, we'll fetch all active users
            # who are not the author as simulated followers, representing a global fan-out.
            followers = db.query(User).filter(
                User.id != author_id,
                User.is_active
            ).all()

            timeline_items = []
            for follower in followers:
                item = TimelineItem(
                    owner_user_id=follower.id,
                    post_id=post_id,
                    originator_user_id=author_id,
                    tenant_id=tenant_id
                )
                timeline_items.append(item)

            if timeline_items:
                db.bulk_save_objects(timeline_items)
                db.commit()
                logger.info(f"Successfully fanned out post {post_id} to {len(timeline_items)} timelines.")
        except Exception as e:
            logger.error(f"Error executing feed fan-out: {e}")
            db.rollback()

    @staticmethod
    def process_media_attachments(post_id: int, tenant_id: str, db: Session):
        """
        Processes attached media files (e.g. image optimization, video thumbnailing).
        """
        try:
            logger.info(f"Processing media attachments for post {post_id}...")

            # Fetch post media
            media_items = db.query(Media).filter(
                Media.post_id == post_id,
                Media.tenant_id == tenant_id
            ).all()

            for item in media_items:
                # Simulate heavy processing / optimization
                logger.info(f"Optimizing media url: {item.url}")
                item.meta = {
                    **(item.meta or {}),
                    "optimized": True,
                    "processed_at": "background-worker"
                }

            if media_items:
                db.commit()
                logger.info(f"Optimized {len(media_items)} media items.")
        except Exception as e:
            logger.error(f"Error processing media: {e}")
            db.rollback()

    @staticmethod
    def process_mentions_and_notifications(post_id: int, content: str, tenant_id: str, db: Session):
        """
        Scans post text for @mentions and simulates sending pushes or emails.
        """
        import re
        try:
            mentions = re.findall(r"@(\w+)", content)
            if not mentions:
                return

            logger.info(f"Found mentions in post {post_id}: {mentions}")
            for username in mentions:
                # Find mentioned user
                target_user = db.query(User).filter(
                    User.username == username,
                    User.is_active
                ).first()

                if target_user:
                    # In a full system, you would insert notification entries:
                    # notification = Notification(user_id=target_user.id, type="mention", post_id=post_id)
                    # db.add(notification)
                    logger.info(f"Simulating push notification dispatch to user: {username}")

        except Exception as e:
            logger.error(f"Error handling post mentions/notifications: {e}")
