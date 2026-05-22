"""
KaPak - Hashtags Router
API Endpoints for trending hashtags, trending statuses, and hashtag-filtered posts.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.hashtag import Hashtag, ContentHashtag
from app.models.post import Post, Comment, Like, Repost
from app.schemas.hashtag import (
    HashtagResponse,
    HashtagTrendingResponse,
    HashtagHistoryItem,
    TrendingPostResponse,
)
from app.schemas.post import PostResponse

router = APIRouter()


@router.get("/trending", response_model=List[HashtagTrendingResponse])
def get_trending_hashtags(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get top N trending hashtags from the last `days` days,
    sorted by usage count descending. Includes daily history
    (uses + unique accounts) for each hashtag.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    tenant = current_user.tenant_id

    rows = (
        db.query(
            Hashtag,
            func.count(ContentHashtag.id).label("period_count"),
        )
        .join(ContentHashtag, ContentHashtag.hashtag_id == Hashtag.id)
        .filter(
            ContentHashtag.created_at >= cutoff,
            Hashtag.tenant_id == tenant,
        )
        .group_by(Hashtag.id)
        .order_by(desc("period_count"))
        .limit(limit)
        .all()
    )

    results: list[HashtagTrendingResponse] = []
    for hashtag, _ in rows:
        history_rows = (
            db.query(
                func.date_trunc("day", ContentHashtag.created_at).label("day"),
                func.count(ContentHashtag.id).label("uses"),
                func.count(func.distinct(Post.author_id)).label("accounts"),
            )
            .join(Post, Post.id == ContentHashtag.post_id)
            .filter(
                ContentHashtag.hashtag_id == hashtag.id,
                ContentHashtag.created_at >= cutoff,
            )
            .group_by(func.date_trunc("day", ContentHashtag.created_at))
            .order_by(func.date_trunc("day", ContentHashtag.created_at))
            .all()
        )

        history = [
            HashtagHistoryItem(
                day=str(h.day),
                uses=h.uses,
                accounts=h.accounts,
            )
            for h in history_rows
        ]

        results.append(
            HashtagTrendingResponse(
                id=hashtag.id,
                name=hashtag.name,
                mention_count=hashtag.mention_count,
                created_at=hashtag.created_at,
                history=history,
            )
        )

    return results


@router.get("/trending-statuses", response_model=List[TrendingPostResponse])
def get_trending_statuses(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get top N trending posts from the last `days` days,
    ranked by total interactions (likes + comments + reposts).
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    tenant = current_user.tenant_id

    like_subq = (
        db.query(func.count(Like.id))
        .filter(Like.post_id == Post.id, Like.created_at >= cutoff)
        .correlate(Post)
        .scalar_subquery()
    )
    comment_subq = (
        db.query(func.count(Comment.id))
        .filter(Comment.post_id == Post.id, Comment.created_at >= cutoff)
        .correlate(Post)
        .scalar_subquery()
    )
    repost_subq = (
        db.query(func.count(Repost.id))
        .filter(Repost.original_post_id == Post.id, Repost.created_at >= cutoff)
        .correlate(Post)
        .scalar_subquery()
    )

    interaction_sum = func.coalesce(like_subq, 0) + func.coalesce(comment_subq, 0) + func.coalesce(repost_subq, 0)

    posts_with_count = (
        db.query(Post, interaction_sum.label("interaction_count"))
        .filter(Post.tenant_id == tenant)
        .order_by(desc("interaction_count"))
        .limit(limit)
        .all()
    )

    return [
        TrendingPostResponse(
            id=post.id,
            content=post.content,
            author_id=post.author_id,
            created_at=post.created_at,
            updated_at=post.updated_at,
            interaction_count=count,
        )
        for post, count in posts_with_count
    ]


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
