from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

from app.modules.follows.schemas import FollowResponse, FollowCountResponse, IsFollowingResponse
from app.modules.follows.service import FollowService

router = APIRouter(
    prefix="/follows",
    tags=["Follows"],
)

def get_follow_service(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> FollowService:
    return FollowService(db=db, tenant_id=current_user.tenant_id)

@router.post("/{user_id}", response_model=FollowResponse, status_code=status.HTTP_201_CREATED, summary="Follow a user")
def follow_user(
    user_id: int, 
    service: FollowService = Depends(get_follow_service),
    current_user: User = Depends(get_current_user)
):
    """
    Follow another user by their user_id.
    """
    return service.follow_user(follower_id=current_user.id, followee_id=user_id)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Unfollow a user")
def unfollow_user(
    user_id: int, 
    service: FollowService = Depends(get_follow_service),
    current_user: User = Depends(get_current_user)
):
    """
    Unfollow another user by their user_id.
    """
    service.unfollow_user(follower_id=current_user.id, followee_id=user_id)

@router.get("/followers/{user_id}", response_model=List[FollowResponse], summary="Get followers of a user")
def get_followers(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: FollowService = Depends(get_follow_service)
):
    """
    Retrieve a list of users who follow the specified user.
    """
    return service.get_followers(user_id=user_id, skip=skip, limit=limit)

@router.get("/following/{user_id}", response_model=List[FollowResponse], summary="Get following list of a user")
def get_following(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service: FollowService = Depends(get_follow_service)
):
    """
    Retrieve a list of users the specified user is following.
    """
    return service.get_following(user_id=user_id, skip=skip, limit=limit)

@router.get("/counts/{user_id}", response_model=FollowCountResponse, summary="Get follower/following counts")
def get_follow_counts(
    user_id: int,
    service: FollowService = Depends(get_follow_service)
):
    """
    Get the total number of followers and following for a specific user.
    """
    return service.get_follow_counts(user_id=user_id)

@router.get("/check/{user_id}", response_model=IsFollowingResponse, summary="Check if following a user")
def check_if_following(
    user_id: int,
    service: FollowService = Depends(get_follow_service),
    current_user: User = Depends(get_current_user)
):
    """
    Check if the current authenticated user is following the specified user.
    """
    is_following = service.is_following(follower_id=current_user.id, followee_id=user_id)
    return IsFollowingResponse(is_following=is_following)
