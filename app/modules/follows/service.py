from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.modules.follows.models import Follow
from app.modules.follows.exceptions import AlreadyFollowingError, NotFollowingError, SelfFollowError

class FollowService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def follow_user(self, follower_id: int, followee_id: int) -> Follow:
        if follower_id == followee_id:
            raise SelfFollowError()
            
        existing = self.db.query(Follow).filter(
            Follow.follower_id == follower_id,
            Follow.followee_id == followee_id,
            Follow.tenant_id == self.tenant_id
        ).first()
        
        if existing:
            raise AlreadyFollowingError()
            
        new_follow = Follow(
            follower_id=follower_id,
            followee_id=followee_id,
            tenant_id=self.tenant_id
        )
        self.db.add(new_follow)
        self.db.commit()
        self.db.refresh(new_follow)
        return new_follow

    def unfollow_user(self, follower_id: int, followee_id: int) -> None:
        if follower_id == followee_id:
            raise SelfFollowError()
            
        existing = self.db.query(Follow).filter(
            Follow.follower_id == follower_id,
            Follow.followee_id == followee_id,
            Follow.tenant_id == self.tenant_id
        ).first()
        
        if not existing:
            raise NotFollowingError()
            
        self.db.delete(existing)
        self.db.commit()

    def get_followers(self, user_id: int, skip: int = 0, limit: int = 50) -> List[Follow]:
        return self.db.query(Follow).filter(
            Follow.followee_id == user_id,
            Follow.tenant_id == self.tenant_id
        ).offset(skip).limit(limit).all()

    def get_following(self, user_id: int, skip: int = 0, limit: int = 50) -> List[Follow]:
        return self.db.query(Follow).filter(
            Follow.follower_id == user_id,
            Follow.tenant_id == self.tenant_id
        ).offset(skip).limit(limit).all()

    def get_follow_counts(self, user_id: int) -> dict:
        followers_count = self.db.query(func.count(Follow.id)).filter(
            Follow.followee_id == user_id,
            Follow.tenant_id == self.tenant_id
        ).scalar() or 0
        
        following_count = self.db.query(func.count(Follow.id)).filter(
            Follow.follower_id == user_id,
            Follow.tenant_id == self.tenant_id
        ).scalar() or 0
        
        return {
            "followers_count": followers_count,
            "following_count": following_count
        }

    def is_following(self, follower_id: int, followee_id: int) -> bool:
        existing = self.db.query(Follow).filter(
            Follow.follower_id == follower_id,
            Follow.followee_id == followee_id,
            Follow.tenant_id == self.tenant_id
        ).first()
        return existing is not None
