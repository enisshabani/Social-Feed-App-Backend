"""
KaPak - Posts Router
API Endpoints for creating, editing, deleting, liking, bookmarking, and commenting on posts.
"""

import os
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.cache import cache_service
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.post import (
    AIRefineRequest,
    AIRefineResponse,
    CommentCreate,
    CommentResponse,
    DraftCreate,
    DraftResponse,
    PostBriefResponse,
    PostCreate,
    PostResponse,
    PostUpdate,
    PollResponse,
    PollVoteRequest,
)
from app.services.ai_service import AIService
from app.services.background_tasks import BackgroundTasksService
from app.services.post_service import PostService

router = APIRouter()

POST_UPLOAD_DIR = os.path.join("uploads", "posts")
os.makedirs(POST_UPLOAD_DIR, exist_ok=True)

# Helper to invalidate cached timeline and explore feeds when updates happen
def _invalidate_feed_cache(tenant_id: str, user_id: Optional[int] = None):
    cache_service.invalidate_prefix(f"feed:{tenant_id}")
    if user_id:
        cache_service.invalidate_prefix(f"timeline:{tenant_id}:{user_id}")


# ==========================================
# POST CRUD ENDPOINTS
# ==========================================

@router.post("/media-upload", status_code=status.HTTP_201_CREATED)
def upload_post_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an image or video for use in a post and return a public URL.
    """
    if not file.content_type or not (
        file.content_type.startswith("image/") or file.content_type.startswith("video/")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image or video.",
        )

    media_type = "video" if file.content_type.startswith("video/") else "image"
    extension = os.path.splitext(file.filename or "")[1] or (".mp4" if media_type == "video" else ".jpg")
    filename = f"{current_user.id}_{uuid.uuid4().hex[:10]}{extension}"
    file_path = os.path.join(POST_UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "url": f"/uploads/posts/{filename}",
        "media_type": media_type,
    }

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    post: PostCreate,
    background_tasks: BackgroundTasks,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new post. Automatically parses hashtags and @mentions into HTML formatting.
    """
    service = PostService(db)
    new_post = service.create_post(post, current_user.id, x_tenant_id, post.media)

    # Trigger background tasks
    background_tasks.add_task(BackgroundTasksService.fanout_post_to_followers, new_post.id, current_user.id, x_tenant_id, db)
    background_tasks.add_task(BackgroundTasksService.process_media_attachments, new_post.id, x_tenant_id, db)
    background_tasks.add_task(BackgroundTasksService.process_mentions_and_notifications, new_post.id, post.content, x_tenant_id, db)

    _invalidate_feed_cache(x_tenant_id, current_user.id)
    return new_post


@router.get("/{post_id}", response_model=PostResponse)
def get_post(
    post_id: int,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    """
    Fetch a single post by ID along with its author, comments, likes, reposts, and tags.
    """
    # Check cache first
    cache_key = f"post:{x_tenant_id}:{post_id}"
    cached = cache_service.get(cache_key)
    if cached:
        return cached

    service = PostService(db)
    post = service.get_post(post_id, x_tenant_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )

    # Save to cache for 1 minute
    post_data = PostResponse.model_validate(post).model_dump()
    cache_service.set(cache_key, post_data, expire_seconds=60)
    return post


@router.put("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    post_update: PostUpdate,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Edit a post's content and media. Automatically updates parsed tags and records history.
    """
    service = PostService(db)
    updated = service.update_post(post_id, post_update, current_user.id, x_tenant_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update post (unauthorized or not found)"
        )

    # Clear cache
    cache_service.delete(f"post:{x_tenant_id}:{post_id}")
    _invalidate_feed_cache(x_tenant_id, current_user.id)
    return updated


@router.delete("/{post_id}", status_code=status.HTTP_200_OK)
def delete_post(
    post_id: int,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a post. Triggers cascade deletion of comments, likes, media, and tags mapping.
    """
    service = PostService(db)
    success = service.delete_post(post_id, current_user.id, x_tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete post (unauthorized or not found)"
        )

    # Invalidate cache
    cache_service.delete(f"post:{x_tenant_id}:{post_id}")
    _invalidate_feed_cache(x_tenant_id, current_user.id)
    return {"message": "Post deleted successfully"}


# ==========================================
# COMMENT ENDPOINTS
# ==========================================

@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    post_id: int,
    comment: CommentCreate,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a comment to a specific post.
    """
    service = PostService(db)
    new_comment = service.add_comment(post_id, comment, current_user.id, x_tenant_id)
    if not new_comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )

    # Invalidate cached post detail and feeds
    cache_service.delete(f"post:{x_tenant_id}:{post_id}")
    _invalidate_feed_cache(x_tenant_id)
    return new_comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_200_OK)
def remove_comment(
    comment_id: int,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a comment by ID (must be comment author).
    """
    service = PostService(db)
    success = service.remove_comment(comment_id, current_user.id, x_tenant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete comment (unauthorized or not found)"
        )

    _invalidate_feed_cache(x_tenant_id)
    return {"message": "Comment removed successfully"}


# ==========================================
# POLL ENDPOINTS
# ==========================================

@router.post("/{post_id}/poll/vote", response_model=PollResponse, status_code=status.HTTP_200_OK)
def vote_poll(
    post_id: int,
    vote: PollVoteRequest,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Vote on a post poll. Users can change their vote; counters update in place.
    """
    service = PostService(db)
    poll = service.vote_poll(post_id, vote.option_id, current_user.id, x_tenant_id)
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll or option not found"
        )

    cache_service.delete(f"post:{x_tenant_id}:{post_id}")
    _invalidate_feed_cache(x_tenant_id)
    return poll


# ==========================================
# LIKE AND REPOST ENDPOINTS
# ==========================================

@router.post("/{post_id}/like", status_code=status.HTTP_200_OK)
def like_post(
    post_id: int,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle a like on a post. Safe, idempotent, and updates denormalized like counters.
    """
    service = PostService(db)
    liked, message = service.toggle_like(post_id, current_user.id, x_tenant_id)

    # Invalidate cache
    cache_service.delete(f"post:{x_tenant_id}:{post_id}")
    _invalidate_feed_cache(x_tenant_id)

    return {"liked": liked, "message": message}


@router.post("/{post_id}/repost", status_code=status.HTTP_200_OK)
def repost_post(
    post_id: int,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle a repost. If not reposted, shares it; if already reposted, deletes the repost post.
    """
    service = PostService(db)
    reposted, message = service.toggle_repost(post_id, current_user.id, x_tenant_id)

    # Invalidate cache
    cache_service.delete(f"post:{x_tenant_id}:{post_id}")
    _invalidate_feed_cache(x_tenant_id, current_user.id)

    return {"reposted": reposted, "message": message}


# ==========================================
# BOOKMARKS (SAVED POSTS) ENDPOINTS
# ==========================================

@router.post("/{post_id}/bookmark", status_code=status.HTTP_200_OK)
def bookmark_post(
    post_id: int,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle bookmark (Saved Post) for a post.
    """
    service = PostService(db)
    bookmarked, message = service.toggle_bookmark(post_id, current_user.id, x_tenant_id)
    return {"bookmarked": bookmarked, "message": message}


@router.get("/bookmarks/all", response_model=List[PostBriefResponse])
def get_bookmarked_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch posts saved/bookmarked by the current user.
    """
    service = PostService(db)
    return service.repo.list_saved_posts(current_user.id, x_tenant_id, skip, limit)


# ==========================================
# DRAFTS ENDPOINTS
# ==========================================

@router.post("/drafts/save", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
def save_draft(
    draft: DraftCreate,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Save post content as a draft.
    """
    service = PostService(db)
    return service.create_draft(draft, current_user.id, x_tenant_id)


@router.get("/drafts/all", response_model=List[DraftResponse])
def list_drafts(
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all drafts saved by the current user.
    """
    service = PostService(db)
    return service.repo.list_drafts(current_user.id, x_tenant_id)


@router.post("/drafts/{draft_id}/publish", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def publish_draft(
    draft_id: int,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Convert a saved draft to a live post and delete the draft.
    """
    service = PostService(db)
    post = service.publish_draft(draft_id, current_user.id, x_tenant_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft not found or unauthorized"
        )
    _invalidate_feed_cache(x_tenant_id, current_user.id)
    return post


# ==========================================
# AI TEXT REFINEMENT ENDPOINT
# ==========================================

@router.post("/refine-ai", response_model=AIRefineResponse, status_code=status.HTTP_200_OK)
def refine_post_text(
    request_data: AIRefineRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Refine post content text before publishing using OpenAI GPT models.
    Supports styles: 'casual', 'professional', 'witty', 'concise'.
    """
    ai_service = AIService()
    refined = ai_service.refine_text(request_data.content, request_data.style)
    return AIRefineResponse(refined_content=refined)

