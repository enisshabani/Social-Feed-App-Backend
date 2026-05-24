"""
KaPak - Users Router
Endpoints: profile view, profile update, change password, list users, admin actions.
"""

from typing import List
import logging
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.cache import cache_service
from app.core.security import hash_password, verify_password
from app.core.dependencies import get_current_user, get_current_active_admin
from app.models.ai_task import AiTask
from app.models.notification_preference import NotificationPreference
from app.models.post import (
    Comment,
    Draft,
    Media,
    Post,
    PostAttachment,
    PostEditHistory,
    PostLike,
    PostRepost,
    PostTag,
    SavedPost,
    TimelineItem,
)
from app.models.search_history import SearchHistory
from app.modules.follows.models import Follow
from app.modules.notifications.models import Notification
from app.models.user import User, UserRole
from app.schemas.user import (
    UserResponse,
    UserPublicResponse,
    UserUpdate,
    PasswordChange,
)

router = APIRouter()
logger = logging.getLogger("kapak")


@router.get("/", response_model=List[UserPublicResponse])
def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of users to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all users (paginated).
    Returns public profiles only.
    """
    users = (
        db.query(User)
        .filter(User.is_active == True)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return users


@router.get("/{username}", response_model=UserPublicResponse)
def get_user_profile(
    username: str,
    db: Session = Depends(get_db),
):
    """
    Get a user's public profile by username.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.put("/me/profile", response_model=UserResponse)
def update_my_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the current user's profile information.
    Only updates fields that are provided (non-null).
    """
    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/me/password")
def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change the current user's password.
    Requires the current password for verification.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    current_user.hashed_password = hash_password(password_data.new_password)
    db.add(current_user)
    db.commit()

    return {"message": "Password changed successfully"}


@router.post("/me/avatar", response_model=UserResponse)
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a profile avatar.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File provided is not an image.",
        )
    
    file_extension = file.filename.split(".")[-1]
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
    file_path = os.path.join("uploads", "avatars", filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    current_user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.delete("/me", status_code=status.HTTP_200_OK)
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete the current user's account permanently from the database.
    """
    user_id = current_user.id
    user_id_str = str(user_id)
    tenant_id = current_user.tenant_id

    try:
        user_post_ids = [
            post_id
            for (post_id,) in (
                db.query(Post.id)
                .filter(Post.author_id == user_id, Post.tenant_id == tenant_id)
                .all()
            )
        ]

        if user_post_ids:
            db.query(TimelineItem).filter(
                TimelineItem.tenant_id == tenant_id,
                TimelineItem.post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(PostTag).filter(PostTag.post_id.in_(user_post_ids)).delete(synchronize_session=False)
            db.query(PostEditHistory).filter(
                PostEditHistory.tenant_id == tenant_id,
                PostEditHistory.post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(SavedPost).filter(
                SavedPost.tenant_id == tenant_id,
                SavedPost.post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(PostLike).filter(
                PostLike.tenant_id == tenant_id,
                PostLike.post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(PostRepost).filter(
                PostRepost.tenant_id == tenant_id,
                PostRepost.original_post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(Comment).filter(
                Comment.tenant_id == tenant_id,
                Comment.post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(Media).filter(
                Media.tenant_id == tenant_id,
                Media.post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(PostAttachment).filter(
                PostAttachment.tenant_id == tenant_id,
                PostAttachment.post_id.in_(user_post_ids),
            ).delete(synchronize_session=False)
            db.query(Post).filter(
                Post.tenant_id == tenant_id,
                Post.original_post_id.in_(user_post_ids),
            ).update({Post.original_post_id: None}, synchronize_session=False)
            db.query(Post).filter(
                Post.tenant_id == tenant_id,
                Post.reply_to_post_id.in_(user_post_ids),
            ).update({Post.reply_to_post_id: None}, synchronize_session=False)

        db.query(TimelineItem).filter(
            TimelineItem.tenant_id == tenant_id,
            (
                (TimelineItem.owner_user_id == user_id)
                | (TimelineItem.originator_user_id == user_id)
            ),
        ).delete(synchronize_session=False)
        db.query(Notification).filter(
            Notification.tenant_id == tenant_id,
            (
                (Notification.recipient_id == user_id_str)
                | (Notification.actor_id == user_id_str)
            ),
        ).delete(synchronize_session=False)
        db.query(Follow).filter(
            Follow.tenant_id == tenant_id,
            (
                (Follow.follower_id == user_id_str)
                | (Follow.followee_id == user_id_str)
            ),
        ).delete(synchronize_session=False)
        db.query(NotificationPreference).filter(
            NotificationPreference.tenant_id == tenant_id,
            NotificationPreference.user_id == user_id,
        ).delete(synchronize_session=False)
        db.query(SearchHistory).filter(
            SearchHistory.tenant_id == tenant_id,
            SearchHistory.user_id == user_id,
        ).delete(synchronize_session=False)
        db.query(AiTask).filter(
            AiTask.tenant_id == tenant_id,
            AiTask.user_id == user_id,
        ).delete(synchronize_session=False)
        db.query(Draft).filter(
            Draft.tenant_id == tenant_id,
            Draft.author_id == user_id,
        ).delete(synchronize_session=False)
        db.query(SavedPost).filter(
            SavedPost.tenant_id == tenant_id,
            SavedPost.user_id == user_id,
        ).delete(synchronize_session=False)
        db.query(PostLike).filter(
            PostLike.tenant_id == tenant_id,
            PostLike.user_id == user_id,
        ).delete(synchronize_session=False)
        db.query(PostRepost).filter(
            PostRepost.tenant_id == tenant_id,
            PostRepost.user_id == user_id,
        ).delete(synchronize_session=False)
        db.query(Comment).filter(
            Comment.tenant_id == tenant_id,
            Comment.author_id == user_id,
        ).delete(synchronize_session=False)
        db.query(PostEditHistory).filter(
            PostEditHistory.tenant_id == tenant_id,
            PostEditHistory.edited_by == user_id,
        ).delete(synchronize_session=False)

        db.query(Post).filter(
            Post.tenant_id == tenant_id,
            Post.author_id == user_id,
        ).delete(synchronize_session=False)
        db.delete(current_user)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to delete account user_id=%s tenant_id=%s: %s", user_id, tenant_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gabim gjatë fshirjes së llogarisë.",
        )

    cache_service.invalidate_prefix(f"feed:{tenant_id}")
    cache_service.invalidate_prefix(f"timeline:{tenant_id}:{user_id}")
    cache_service.invalidate_prefix(f"follow_counts:{tenant_id}:{user_id}")
    cache_service.invalidate_prefix(f"unread_count:{tenant_id}:{user_id}")
    return {"message": "Account deleted successfully"}


# ─── Admin Endpoints ────────────────────────────────────────

@router.get("/admin/all", response_model=List[UserResponse])
def admin_list_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db),
):
    """
    [ADMIN] List all users including inactive ones.
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.put("/admin/{user_id}/role")
def admin_change_user_role(
    user_id: int,
    role: UserRole,
    admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db),
):
    """
    [ADMIN] Change a user's role (user, moderator, admin).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.role = role
    db.commit()
    return {"message": f"User {user.username} role changed to {role.value}"}


@router.put("/admin/{user_id}/activate")
def admin_activate_user(
    user_id: int,
    admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db),
):
    """
    [ADMIN] Reactivate a deactivated user account.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = True
    db.commit()
    return {"message": f"User {user.username} has been reactivated"}
