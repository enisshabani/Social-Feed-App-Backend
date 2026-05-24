"""
KaPak - Tasks Router
Generic endpoint for polling Celery task status.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.ai_task import AiTask
from app.schemas.ai_task import TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
def get_task_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = (
        db.query(AiTask)
        .filter(
            AiTask.id == task_id,
            AiTask.user_id == current_user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return TaskStatusResponse(
        task_id=task.id,
        task_type=task.task_type,
        status=task.status,
        output_data=task.output_data,
        error_message=task.error_message,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )
