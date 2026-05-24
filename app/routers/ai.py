"""
KaPak - AI Router
Endpoints for AI-powered features: hashtag suggestion, sentiment analysis.
All operations are async via Celery tasks. Falls back to marking task as failed if broker is down.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tasks.ai_tasks import (
    analyze_sentiment_task,
    suggest_hashtags_task,
)
from app.models.ai_task import AiTask
from app.models.user import User
from app.schemas.ai_task import (
    AiTaskResponse,
    AnalyzeSentimentRequest,
    SuggestHashtagsRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI"])


def _enqueue(db: Session, task: AiTask, celery_task, **kwargs):
    try:
        celery_task.delay(**kwargs)
    except Exception as e:
        logger.error(f"Failed to enqueue {task.task_type} task {task.id}: {e}")
        task.status = "failed"
        task.error_message = f"Celery broker unreachable: {str(e)[:500]}"
        db.commit()


@router.post("/suggest-hashtags", response_model=AiTaskResponse, status_code=202)
def suggest_hashtags(
    body: SuggestHashtagsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = AiTask(
        task_type="suggest_hashtags",
        input_data={"post_text": body.post_text},
        status="pending",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    _enqueue(db, task, suggest_hashtags_task,
        task_id=task.id,
        post_text=body.post_text,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return task


@router.post("/analyze-sentiment", response_model=AiTaskResponse, status_code=202)
def analyze_sentiment(
    body: AnalyzeSentimentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = AiTask(
        task_type="analyze_sentiment",
        input_data={"post_text": body.post_text},
        status="pending",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    _enqueue(db, task, analyze_sentiment_task,
        task_id=task.id,
        post_text=body.post_text,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return task
