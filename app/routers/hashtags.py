"""
KaPak - Hashtags Router
API Endpoints for trending hashtags and hashtag-filtered posts.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.hashtag import Hashtag, ContentHashtag
from app.models.post import Post
from app.schemas.hashtag import HashtagResponse
from app.schemas.post import PostResponse

router = APIRouter()


@router.get("/trending", response_model=List[HashtagResponse])
def get_trending_hashtags(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get top N trending hashtags sorted by mention_count descending.
    """
    hashtags = (
        db.query(Hashtag)
        .filter(Hashtag.tenant_id == current_user.tenant_id)
        .order_by(desc(Hashtag.mention_count))
        .limit(limit)
        .all()
    )
    return hashtags


@router.get("/{name}/posts", response_model=List[PostResponse])
def get_hashtag_posts(
    name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get paginated posts for a specific hashtag.
    """
    hashtag = (
        db.query(Hashtag)
        .filter(
            Hashtag.name == name.lower(),
            Hashtag.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not hashtag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hashtag not found",
        )

    posts = (
        db.query(Post)
        .join(ContentHashtag, ContentHashtag.post_id == Post.id)
        .filter(
            ContentHashtag.hashtag_id == hashtag.id,
            Post.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(Post.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return posts
