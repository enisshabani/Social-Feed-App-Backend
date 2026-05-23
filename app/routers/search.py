"""
KaPak - Search Router
Full-text search across posts, users, and hashtags with pagination.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text, exc as sa_exc

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.hashtag import Hashtag
from app.models.search_history import SearchHistory
from app.schemas.search import SearchPostsResult, SearchUsersResult, SearchHashtagsResult

router = APIRouter()


def _log_search(db: Session, user_id: int, tenant_id: str, query: str, search_type: str, result_count: int):
    entry = SearchHistory(
        user_id=user_id,
        query=query,
        search_type=search_type,
        result_count=result_count,
        tenant_id=tenant_id,
    )
    db.add(entry)
    db.commit()


@router.get("/posts", response_model=SearchPostsResult)
def search_posts(
    q: str = Query(..., min_length=1, max_length=500),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full-text search on posts by content and author username/display_name.
    Uses PostgreSQL tsvector for content; ILIKE for author name matching.
    """
    tenant = current_user.tenant_id
    ilike_q = f"%{q}%"

    # Base query: posts in this tenant
    base = db.query(Post).filter(Post.tenant_id == tenant)

    # Build a filter that matches content OR author name
    # Try PostgreSQL full-text on content first
    try:
        ts_query = func.plainto_tsquery("english", q)
        ts_match = func.to_tsvector("english", Post.content).op("@@")(ts_query)
        content_match = ts_match
    except (sa_exc.OperationalError, sa_exc.ProgrammingError):
        # SQLite fallback
        content_match = Post.content.ilike(ilike_q)

    # Join with User to search by author name
    author_match = or_(
        User.username.ilike(ilike_q),
        User.display_name.ilike(ilike_q),
    )

    # Search: content match OR author match
    query_filter = or_(content_match, author_match)

    # Apply filter with the join
    results = (
        base.join(User, Post.author_id == User.id)
        .filter(query_filter)
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = (
        base.join(User, Post.author_id == User.id)
        .filter(query_filter)
        .count()
    )

    # Fallback: if tsvector returned no results, try full ILIKE on content
    if len(results) == 0:
        content_ilike = Post.content.ilike(ilike_q)
        fallback_filter = or_(content_ilike, author_match)
        results = (
            base.join(User, Post.author_id == User.id)
            .filter(fallback_filter)
            .order_by(Post.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = (
            base.join(User, Post.author_id == User.id)
            .filter(fallback_filter)
            .count()
        )

    _log_search(db, current_user.id, tenant, q, "posts", total)

    return SearchPostsResult(
        items=results,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/users", response_model=SearchUsersResult)
def search_users(
    q: str = Query(..., min_length=1, max_length=500),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search users by username or display name (case-insensitive).
    """
    tenant = current_user.tenant_id
    ilike_q = f"%{q}%"

    base = db.query(User).filter(
        User.tenant_id == tenant,
        or_(
            User.username.ilike(ilike_q),
            User.display_name.ilike(ilike_q),
        ),
    )

    total = base.count()
    results = (
        base.order_by(User.username)
        .offset(offset)
        .limit(limit)
        .all()
    )

    _log_search(db, current_user.id, tenant, q, "users", total)

    return SearchUsersResult(
        items=results,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/hashtags", response_model=SearchHashtagsResult)
def search_hashtags(
    q: str = Query(..., min_length=1, max_length=500),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search hashtags by name (case-insensitive).
    Leading # characters are stripped automatically.
    """
    tenant = current_user.tenant_id
    clean_q = q.lstrip("#")
    ilike_q = f"%{clean_q}%"

    base = db.query(Hashtag).filter(
        Hashtag.tenant_id == tenant,
        Hashtag.name.ilike(ilike_q),
    )

    total = base.count()
    results = (
        base.order_by(Hashtag.mention_count.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    _log_search(db, current_user.id, tenant, clean_q, "hashtags", total)

    return SearchHashtagsResult(
        items=results,
        total=total,
        offset=offset,
        limit=limit,
    )
