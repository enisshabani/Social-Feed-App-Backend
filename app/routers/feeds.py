"""
KaPak - Feeds Router
API Endpoints for Home Feed, User Timelines, Hashtags, and Trending/Explore listings.
Supports Redis/In-Memory caching for optimal performance.
"""

from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.cache import cache_service
from app.schemas.post import PostBriefResponse, HashtagStatsResponse, FeedResponse
from app.services.post_service import PostService

router = APIRouter()


# ==========================================
# HOME FEED ENDPOINT
# ==========================================

@router.get("/home", response_model=FeedResponse)
def get_home_feed(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    """
    Get the global Home Feed. Includes a highly optimized 5-second server-side cache.
    """
    cache_key = f"feed:{x_tenant_id}:{skip}:{limit}"
    cached = cache_service.get(cache_key)
    if cached:
        return cached

    service = PostService(db)
    posts = service.list_feed(x_tenant_id, skip, limit)
    
    # Check if there are potentially more items
    has_more = len(posts) == limit
    next_cursor = str(skip + limit) if has_more else None

    # Construct schema response
    brief_posts = [PostBriefResponse.model_validate(p) for p in posts]
    feed_data = FeedResponse(
        items=brief_posts,
        next_cursor=next_cursor,
        has_more=has_more
    )

    # Store in cache for 5 seconds to throttle rapid loads
    cache_service.set(cache_key, feed_data.model_dump(), expire_seconds=5)
    return feed_data


# ==========================================
# USER TIMELINE ENDPOINT
# ==========================================

@router.get("/timeline/{user_id}", response_model=FeedResponse)
def get_user_timeline(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    """
    Get all posts made by a specific user for their public timeline/profile page.
    Cached for 5 seconds.
    """
    cache_key = f"timeline:{x_tenant_id}:{user_id}:{skip}:{limit}"
    cached = cache_service.get(cache_key)
    if cached:
        return cached

    service = PostService(db)
    posts = service.list_user_timeline(user_id, x_tenant_id, skip, limit)

    has_more = len(posts) == limit
    next_cursor = str(skip + limit) if has_more else None

    brief_posts = [PostBriefResponse.model_validate(p) for p in posts]
    timeline_data = FeedResponse(
        items=brief_posts,
        next_cursor=next_cursor,
        has_more=has_more
    )

    cache_service.set(cache_key, timeline_data.model_dump(), expire_seconds=5)
    return timeline_data


# ==========================================
# EXPLORE / TRENDING TAGS ENDPOINT
# ==========================================

@router.get("/explore", response_model=List[dict])
def get_explore_trending(
    limit: int = Query(10, ge=1, le=50),
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    """
    Get the top trending hashtags based on real-time post metrics.
    Cached for 30 seconds.
    """
    cache_key = f"explore:{x_tenant_id}:{limit}"
    cached = cache_service.get(cache_key)
    if cached:
        return cached

    service = PostService(db)
    trending = service.get_trending_hashtags(x_tenant_id, limit)

    cache_service.set(cache_key, trending, expire_seconds=30)
    return trending


# ==========================================
# HASHTAG FILTERED ENDPOINT
# ==========================================

@router.get("/tag/{tag_name}", response_model=FeedResponse)
def get_posts_by_tag(
    tag_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    db: Session = Depends(get_db)
):
    """
    Search and filter posts containing a specific #hashtag.
    """
    service = PostService(db)
    posts = service.search_posts_by_tag(tag_name, x_tenant_id, skip, limit)

    has_more = len(posts) == limit
    next_cursor = str(skip + limit) if has_more else None

    brief_posts = [PostBriefResponse.model_validate(p) for p in posts]
    feed_data = FeedResponse(
        items=brief_posts,
        next_cursor=next_cursor,
        has_more=has_more
    )
    return feed_data
