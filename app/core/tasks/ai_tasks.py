"""
KaPak - AI Celery Tasks
Async tasks for AI-powered features: hashtag suggestion, sentiment analysis, personalized feed.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.openai_client import OpenAIClient
from app.models.ai_task import AiTask

logger = logging.getLogger(__name__)
settings = get_settings()

_engine = create_engine(settings.DATABASE_URL)
_SessionLocal = sessionmaker(bind=_engine)


def _get_ai_client() -> OpenAIClient:
    return OpenAIClient()


def _update_task_status(task_id: int, status: str, output_data=None, error_message=None):
    db = _SessionLocal()
    try:
        task = db.query(AiTask).filter(AiTask.id == task_id).first()
        if task:
            task.status = status
            if output_data is not None:
                task.output_data = output_data
            if error_message is not None:
                task.error_message = error_message
            if status in ("completed", "failed"):
                task.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def suggest_hashtags_task(self, task_id: int, post_text: str, user_id: int, tenant_id: str):
    """
    Calls AI to suggest 3-5 relevant hashtags for a post.
    Stores result in AiTask.output_data.
    """
    _update_task_status(task_id, "processing")
    try:
        client = _get_ai_client()
        hashtags = client.suggest_hashtags(post_text)
        _update_task_status(task_id, "completed", output_data={"hashtags": hashtags})
        return {"task_id": task_id, "hashtags": hashtags}
    except Exception as exc:
        logger.error(f"Hashtag suggestion failed for task {task_id}: {exc}")
        _update_task_status(task_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def analyze_sentiment_task(self, task_id: int, post_text: str, user_id: int, tenant_id: str):
    """
    Calls AI to analyze sentiment of a post.
    Stores result in AiTask.output_data as {sentiment, confidence, mood_tags}.
    """
    _update_task_status(task_id, "processing")
    try:
        client = _get_ai_client()
        result = client.analyze_sentiment(post_text)
        _update_task_status(task_id, "completed", output_data=result)
        return {"task_id": task_id, "result": result}
    except Exception as exc:
        logger.error(f"Sentiment analysis failed for task {task_id}: {exc}")
        _update_task_status(task_id, "failed", error_message=str(exc))
        raise self.retry(exc=exc)
