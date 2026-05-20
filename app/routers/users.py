"""
KaPak - Users Router
Endpoints: profile view, profile update, change password, list users, admin actions.
"""

from typing import List
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.core.dependencies import get_current_user, get_current_active_admin
from app.models.user import User, UserRole
from app.schemas.user import (
    UserResponse,
    UserPublicResponse,
    UserUpdate,
    PasswordChange,
)

router = APIRouter()


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
def deactivate_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deactivate the current user's account (soft delete).
    The account can be reactivated by an admin.
    """
    current_user.is_active = False
    db.commit()
    return {"message": "Account deactivated successfully"}


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
