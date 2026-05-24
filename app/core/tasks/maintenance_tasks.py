"""
KaPak - Maintenance Celery Tasks
Periodic background jobs: trending recalculation, cleanup, token expiry.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker

from app.core.cache import cache_service
from app.core.celery_app import celery_app
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_engine = create_engine(settings.DATABASE_URL)
_SessionLocal = sessionmaker(bind=_engine)


@celery_app.task
def recalculate_trending_hashtags(tenant_id: str = "default"):
    """
    Recalculate trending hashtags for the given tenant.
    Invalidate the explore cache so fresh data is fetched on next request.
    """
    db = _SessionLocal()
    try:
        from app.models.hashtag import ContentHashtag, Hashtag

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        rows = (
            db.query(
                Hashtag.id,
                func.count(ContentHashtag.id).label("count"),
            )
            .outerjoin(ContentHashtag, ContentHashtag.hashtag_id == Hashtag.id)
            .filter(
                Hashtag.tenant_id == tenant_id,
                (ContentHashtag.created_at >= cutoff) | (ContentHashtag.created_at.is_(None)),
            )
            .group_by(Hashtag.id)
            .order_by(desc("count"))
            .all()
        )

        for hashtag_id, count in rows:
            db.query(Hashtag).filter(Hashtag.id == hashtag_id).update(
                {"mention_count": count or 0}, synchronize_session=False
            )

        db.commit()

        cache_service.invalidate_prefix(f"explore:{tenant_id}")
        cache_service.invalidate_prefix(f"trending_hashtags:{tenant_id}")

        logger.info(f"Recalculated trending hashtags for tenant '{tenant_id}' ({len(rows)} hashtags)")
        return {"tenant_id": tenant_id, "hashtags_updated": len(rows)}
    except Exception as e:
        logger.error(f"Trending recalculation failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task
def cleanup_stale_ai_tasks(tenant_id: str = "default"):
    """
    Mark AiTasks that have been pending for over 30 minutes as failed.
    """
    db = _SessionLocal()
    try:
        from app.models.ai_task import AiTask

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

        stale = (
            db.query(AiTask)
            .filter(
                AiTask.tenant_id == tenant_id,
                AiTask.status.in_(["pending", "processing"]),
                AiTask.created_at < cutoff,
            )
            .update(
                {"status": "failed", "error_message": "Task timed out after 30 minutes"},
                synchronize_session=False,
            )
        )

        db.commit()
        logger.info(f"Cleaned up {stale} stale AI tasks for tenant '{tenant_id}'")
        return {"tenant_id": tenant_id, "stale_tasks_cleaned": stale}
    except Exception as e:
        logger.error(f"Cleanup stale tasks failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task
def cleanup_old_search_history(tenant_id: str = "default"):
    """
    Delete search history entries older than 30 days to keep the table lean.
    """
    db = _SessionLocal()
    try:
        from app.models.search_history import SearchHistory

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        deleted = (
            db.query(SearchHistory)
            .filter(
                SearchHistory.tenant_id == tenant_id,
                SearchHistory.created_at < cutoff,
            )
            .delete(synchronize_session=False)
        )

        db.commit()
        logger.info(f"Deleted {deleted} old search history entries for tenant '{tenant_id}'")
        return {"tenant_id": tenant_id, "entries_deleted": deleted}
    except Exception as e:
        logger.error(f"Cleanup old search history failed: {e}")
        db.rollback()
    finally:
        db.close()
