from fastapi import APIRouter, Depends, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

from app.modules.follows.schemas import FollowResponse, FollowCountResponse, IsFollowingResponse
from app.modules.follows.service import FollowService
from app.workers.notification_worker import process_follow_notification

router = APIRouter(
    tags=["Follows"],
)

def get_follow_service(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FollowService:
    return FollowService(db=db, tenant_id=current_user.tenant_id)

@router.post(
    "/{user_id}", 
    response_model=FollowResponse, 
    status_code=status.HTTP_201_CREATED, 
    summary="Follow a user",
    description="Follow another user by their user_id. Creates a follow relationship in the database.",
    responses={
        201: {"description": "Successfully followed user"},
        400: {"description": "Bad Request - Cannot follow yourself"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        404: {"description": "Not Found - User does not exist"},
        409: {"description": "Conflict - Already following this user"}
    }
)
def follow_user(
    user_id: int, 
    background_tasks: BackgroundTasks,
    service: FollowService = Depends(get_follow_service),
    current_user: User = Depends(get_current_user)
):
    follow = service.follow_user(follower_id=current_user.id, followee_id=user_id)
    
    background_tasks.add_task(
        process_follow_notification,
        actor_id=current_user.id,
        recipient_id=user_id,
        tenant_id=current_user.tenant_id
    )
    
    return follow

@router.delete(
    "/{user_id}", 
    status_code=status.HTTP_204_NO_CONTENT, 
    summary="Unfollow a user",
    description="Unfollow another user by their user_id. Deletes the follow relationship.",
    responses={
        204: {"description": "Successfully unfollowed user"},
        400: {"description": "Bad Request - Cannot unfollow yourself"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        404: {"description": "Not Found - Not following this user"}
    }
)
def unfollow_user(
    user_id: int, 
    service: FollowService = Depends(get_follow_service),
    current_user: User = Depends(get_current_user)
):
    service.unfollow_user(follower_id=current_user.id, followee_id=user_id)

@router.get(
    "/followers/{user_id}", 
    response_model=List[FollowResponse], 
    summary="Get followers of a user",
    description="Retrieve a paginated list of users who follow the specified user.",
    responses={
        200: {"description": "List of followers retrieved"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"}
    }
)
def get_followers(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max number of records to return"),
    service: FollowService = Depends(get_follow_service)
):
    return service.get_followers(user_id=user_id, skip=skip, limit=limit)

@router.get(
    "/following/{user_id}", 
    response_model=List[FollowResponse], 
    summary="Get following list of a user",
    description="Retrieve a paginated list of users the specified user is following.",
    responses={
        200: {"description": "List of following users retrieved"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"}
    }
)
def get_following(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max number of records to return"),
    service: FollowService = Depends(get_follow_service)
):
    return service.get_following(user_id=user_id, skip=skip, limit=limit)

@router.get(
    "/pending-follow-backs",
    response_model=List[FollowResponse],
    summary="Get pending follow-back reminders",
    description="Retrieve users the current user follows who have not followed back yet.",
    responses={
        200: {"description": "Pending follow-back reminders retrieved"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"}
    }
)
def get_pending_follow_backs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max number of records to return"),
    service: FollowService = Depends(get_follow_service),
    current_user: User = Depends(get_current_user)
):
    return service.get_pending_follow_backs(user_id=current_user.id, skip=skip, limit=limit)

@router.get(
    "/counts/{user_id}", 
    response_model=FollowCountResponse, 
    summary="Get follower/following counts",
    description="Get the total number of followers and following for a specific user.",
    responses={
        200: {"description": "Counts retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"}
    }
)
def get_follow_counts(
    user_id: int,
    service: FollowService = Depends(get_follow_service)
):
    return service.get_follow_counts(user_id=user_id)

@router.get(
    "/check/{user_id}", 
    response_model=IsFollowingResponse, 
    summary="Check if following a user",
    description="Check if the current authenticated user is following the specified user.",
    responses={
        200: {"description": "Check completed successfully"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"}
    }
)
def check_if_following(
    user_id: int,
    service: FollowService = Depends(get_follow_service),
    current_user: User = Depends(get_current_user)
):
    is_following = service.is_following(follower_id=current_user.id, followee_id=user_id)
    return IsFollowingResponse(is_following=is_following)
