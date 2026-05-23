"""
KaPak - Search Router
Full-text search across posts, users, and hashtags with pagination.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func, text, exc as sa_exc

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post, Comment
from app.models.hashtag import Hashtag
from app.models.search_history import SearchHistory
from app.schemas.search import (
    SearchPostsResult, SearchUsersResult, SearchHashtagsResult,
    SearchPostItem, MatchContext, MatchedComment,
)
from app.schemas.user import UserPublicResponse

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


def _make_snippet(content: str, query: str, radius: int = 50) -> str:
    idx = content.lower().find(query.lower())
    if idx == -1:
        end = min(len(content), radius * 2)
        return content[:end] + ("..." if len(content) > radius * 2 else "")
    start = max(0, idx - radius)
    end = min(len(content), idx + len(query) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return f"{prefix}{content[start:end]}{suffix}"


def _build_match_context(post: Post, post_match_ids: set, comment_matches_by_post: dict):
    match_context = MatchContext(
        post_match=post.id in post_match_ids,
    )
    if post.id in comment_matches_by_post:
        for cmt in comment_matches_by_post[post.id]:
            match_context.matched_comments.append(MatchedComment(
                id=cmt.id,
                snippet=_make_snippet(cmt.content, cmt._search_q),
                author=UserPublicResponse.model_validate(cmt.author),
            ))
    return match_context


@router.get("/posts", response_model=SearchPostsResult)
def search_posts(
    q: str = Query(..., min_length=1, max_length=500),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    include_comments: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full-text search on posts by content and author username/display_name.
    Optionally includes posts whose comments match the query.
    Uses PostgreSQL tsvector for content; ILIKE for author name matching.
    """
    tenant = current_user.tenant_id
    ilike_q = f"%{q}%"

    base = db.query(Post).filter(Post.tenant_id == tenant)

    try:
        ts_query = func.plainto_tsquery("english", q)
        ts_match = func.to_tsvector("english", Post.content).op("@@")(ts_query)
        content_match = ts_match
    except (sa_exc.OperationalError, sa_exc.ProgrammingError):
        content_match = Post.content.ilike(ilike_q)

    author_match = or_(
        User.username.ilike(ilike_q),
        User.display_name.ilike(ilike_q),
    )

    query_filter = or_(content_match, author_match)

    # Phase 1a: direct post matches
    direct_query = (
        base.join(User, Post.author_id == User.id)
        .filter(query_filter)
    )
    direct_post_ids = {row.id for row in direct_query.with_entities(Post.id).all()}
    direct_total = direct_query.count()

    # Phase 1b: comment matches (only when requested)
    comment_post_ids = set()
    comment_matches_by_post = {}
    if include_comments:
        comment_rows = (
            db.query(Comment)
            .options(joinedload(Comment.author))
            .filter(
                Comment.tenant_id == tenant,
                Comment.content.ilike(ilike_q),
            )
            .all()
        )
        for cmt in comment_rows:
            cmt._search_q = q
            comment_post_ids.add(cmt.post_id)
            comment_matches_by_post.setdefault(cmt.post_id, []).append(cmt)

    # Merge, deduplicate, sort (defer to DB)
    all_ids = direct_post_ids | comment_post_ids
    total = len(all_ids)

    if all_ids:
        page_ids = sorted(all_ids, reverse=True)[offset:offset + limit]
        posts = (
            db.query(Post)
            .options(
                joinedload(Post.author),
                joinedload(Post.comments).joinedload(Comment.author),
                joinedload(Post.likes),
                joinedload(Post.reposts),
                joinedload(Post.media),
                joinedload(Post.tags),
            )
            .filter(Post.id.in_(page_ids))
            .order_by(Post.created_at.desc())
            .all()
        )
        posts_by_id = {p.id: p for p in posts}
        ordered = [posts_by_id[pid] for pid in page_ids if pid in posts_by_id]
    else:
        ordered = []

    # Fallback: if tsvector returned no results for direct matches, retry with ILIKE
    if not direct_post_ids and not comment_post_ids:
        content_ilike = Post.content.ilike(ilike_q)
        fallback_filter = or_(content_ilike, author_match)
        fallback_query = (
            base.join(User, Post.author_id == User.id)
            .filter(fallback_filter)
        )
        fallback_ids = {row.id for row in fallback_query.with_entities(Post.id).all()}
        fallback_total = fallback_query.count()
        all_ids = fallback_ids | comment_post_ids
        total = max(total, fallback_total)

        if all_ids:
            page_ids = sorted(all_ids, reverse=True)[offset:offset + limit]
            posts = (
                db.query(Post)
                .options(
                    joinedload(Post.author),
                    joinedload(Post.comments).joinedload(Comment.author),
                    joinedload(Post.likes),
                    joinedload(Post.reposts),
                    joinedload(Post.media),
                    joinedload(Post.tags),
                )
                .filter(Post.id.in_(page_ids))
                .order_by(Post.created_at.desc())
                .all()
            )
            posts_by_id = {p.id: p for p in posts}
            ordered = [posts_by_id[pid] for pid in page_ids if pid in posts_by_id]
            direct_post_ids = fallback_ids

    # Build response items with match_context when include_comments is on
    items = []
    for post in ordered:
        if include_comments:
            ctx = _build_match_context(post, direct_post_ids, comment_matches_by_post)
            item = SearchPostItem.model_validate(post)
            item.match_context = ctx
            items.append(item)
        else:
            items.append(post)

    _log_search(db, current_user.id, tenant, q, "posts", total)

    result = SearchPostsResult(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )
    return result


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
