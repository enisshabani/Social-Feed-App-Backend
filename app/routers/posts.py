"""
KaPak - Posts & Feed Router
API Endpoints for Posts, Comments, Likes, Feed, Search and Filtering.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user 
from app.models.user import User
from app.models.post import Post, Comment, Like, Repost
from app.schemas.post import (
    PostCreate, PostUpdate, PostResponse, 
    CommentCreate, CommentResponse, 
    LikeCreate, LikeResponse,
    RepostCreate, RepostResponse
)

# ==========================================
# POST ENDPOINTS
# ==========================================

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    post: PostCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new post for the authenticated user.
    """
    new_post = Post(content=post.content, author_id=current_user.id)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@router.get("/", response_model=List[PostResponse])
def get_posts(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search posts by content"),
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """
    Retrieve a paginated list of posts, optionally filtered by search text.
    Ordered by creation date descending.
    """
    query = db.query(Post)
    
    if search:
        query = query.filter(Post.content.ilike(f"%{search}%"))
        
    posts = query.order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    return posts


# ==========================================
# COMMENT ENDPOINTS
# ==========================================

@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: int,
    comment: CommentCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a comment to a specific post.
    Raises 404 if the post does not exist.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    new_comment = Comment(content=comment.content, post_id=post_id, author_id=current_user.id)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


# ==========================================
# LIKE AND REPOST ENDPOINTS
# ==========================================

@router.post("/{post_id}/like", status_code=status.HTTP_201_CREATED)
def like_post(
    post_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle a like on a post. 
    If already liked, removes the like. If not, adds the like.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    existing_like = db.query(Like).filter(Like.post_id == post_id, Like.user_id == current_user.id).first()
    
    if existing_like:
        db.delete(existing_like)
        db.commit()
        return {"message": "Like removed"}
    else:
        new_like = Like(post_id=post_id, user_id=current_user.id)
        db.add(new_like)
        db.commit()
        return {"message": "Like added"}


@router.post("/{post_id}/repost", response_model=RepostResponse, status_code=status.HTTP_201_CREATED)
def repost_post(
    post_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Repost an original post to the current user's feed.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    new_repost = Repost(original_post_id=post_id, user_id=current_user.id)
    db.add(new_repost)
    db.commit()
    db.refresh(new_repost)
    return new_repost
