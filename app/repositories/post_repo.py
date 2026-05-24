"""
KaPak - Post Repository
Data Access Layer (DAL) for managing all database queries related to posts.
"""

from typing import List, Optional, Tuple

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.post import (
    Comment,
    Draft,
    HashtagStats,
    Media,
    Post,
    PostEditHistory,
    PostLike,
    PostRepost,
    PostTag,
    Poll,
    PollOption,
    PollVote,
    SavedPost,
    Tag,
)
from app.schemas.post import CommentCreate, DraftCreate, DraftUpdate, MediaCreate, PollCreate, PostCreate, PostUpdate


class PostRepository:
    """Repository class containing SQL operations for posts, likes, reposts, comments, and drafts."""

    def __init__(self, db: Session):
        self.db = db

    # ==========================================
    # POST CRUD
    # ==========================================

    def create_post(self, post_in: PostCreate, author_id: int, tenant_id: str = "default", is_repost: bool = False, original_post_id: Optional[int] = None) -> Post:
        """Create a new post."""
        db_post = Post(
            content=post_in.content,
            visibility=post_in.visibility,
            reply_to_post_id=post_in.reply_to_post_id,
            author_id=author_id,
            tenant_id=tenant_id,
            is_repost=is_repost,
            original_post_id=original_post_id
        )
        self.db.add(db_post)
        self.db.commit()
        self.db.refresh(db_post)
        return db_post

    def get_post_by_id(self, post_id: int, tenant_id: str = "default") -> Optional[Post]:
        """Fetch a single post by ID within a tenant."""
        return self.db.query(Post).filter(
            Post.id == post_id,
            Post.tenant_id == tenant_id
        ).first()

    def list_posts(self, tenant_id: str = "default", skip: int = 0, limit: int = 20) -> List[Post]:
        """List root level posts (not replies) ordered by creation date."""
        return self.db.query(Post).filter(
            Post.tenant_id == tenant_id,
            Post.reply_to_post_id.is_(None)
        ).order_by(desc(Post.created_at)).offset(skip).limit(limit).all()

    def list_user_posts(self, user_id: int, tenant_id: str = "default", skip: int = 0, limit: int = 20) -> List[Post]:
        """List posts created by a specific user."""
        return self.db.query(Post).filter(
            Post.tenant_id == tenant_id,
            Post.author_id == user_id
        ).order_by(desc(Post.created_at)).offset(skip).limit(limit).all()

    def update_post(self, post: Post, post_in: PostUpdate) -> Post:
        """Update post content and record edit history."""
        update_data = post_in.model_dump(exclude_unset=True)
        media_items = update_data.pop("media", None)

        # Record history if content changes
        if "content" in update_data and update_data["content"] != post.content:
            history = PostEditHistory(
                post_id=post.id,
                old_content=post.content,
                new_content=update_data["content"],
                edited_by=post.author_id,
                tenant_id=post.tenant_id
            )
            self.db.add(history)

        for field, value in update_data.items():
            setattr(post, field, value)

        if media_items is not None:
            self.replace_media(post.id, media_items, post.tenant_id)

        self.db.commit()
        self.db.refresh(post)
        return post

    def delete_post(self, post: Post) -> bool:
        """Delete a post and trigger cascade deletes."""
        self.db.delete(post)
        self.db.commit()
        return True

    # ==========================================
    # COMMENTS
    # ==========================================

    def create_comment(self, comment_in: CommentCreate, post_id: int, author_id: int, tenant_id: str = "default") -> Comment:
        """Add a comment/reply to a post."""
        comment = Comment(
            content=comment_in.content,
            post_id=post_id,
            author_id=author_id,
            tenant_id=tenant_id
        )
        self.db.add(comment)

        # Increment comment reply_count
        post = self.get_post_by_id(post_id, tenant_id)
        if post:
            post.reply_count = (post.reply_count or 0) + 1

        self.db.commit()
        self.db.refresh(comment)
        return comment

    def delete_comment(self, comment: Comment) -> bool:
        """Remove a comment and decrement comment count on the post."""
        post = self.get_post_by_id(comment.post_id, comment.tenant_id)
        if post:
            post.reply_count = max(0, (post.reply_count or 1) - 1)

        self.db.delete(comment)
        self.db.commit()
        return True

    def get_comment_by_id(self, comment_id: int, tenant_id: str = "default") -> Optional[Comment]:
        """Fetch comment by ID."""
        return self.db.query(Comment).filter(
            Comment.id == comment_id,
            Comment.tenant_id == tenant_id
        ).first()

    # ==========================================
    # LIKES
    # ==========================================

    def create_like(self, post_id: int, user_id: int, tenant_id: str = "default") -> Optional[PostLike]:
        """Like a post (idempotent)."""
        existing = self.db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
            PostLike.tenant_id == tenant_id
        ).first()

        if existing:
            return existing

        like = PostLike(post_id=post_id, user_id=user_id, tenant_id=tenant_id)
        self.db.add(like)

        # Increment counter
        post = self.get_post_by_id(post_id, tenant_id)
        if post:
            post.like_count = (post.like_count or 0) + 1

        self.db.commit()
        self.db.refresh(like)
        return like

    def remove_like(self, post_id: int, user_id: int, tenant_id: str = "default") -> bool:
        """Unlike a post."""
        like = self.db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
            PostLike.tenant_id == tenant_id
        ).first()

        if not like:
            return False

        self.db.delete(like)

        # Decrement counter
        post = self.get_post_by_id(post_id, tenant_id)
        if post:
            post.like_count = max(0, (post.like_count or 1) - 1)

        self.db.commit()
        return True

    # ==========================================
    # REPOSTS
    # ==========================================

    def create_repost(self, post_id: int, user_id: int, tenant_id: str = "default") -> Optional[PostRepost]:
        """Repost a post (idempotent)."""
        existing = self.db.query(PostRepost).filter(
            PostRepost.original_post_id == post_id,
            PostRepost.user_id == user_id,
            PostRepost.tenant_id == tenant_id
        ).first()

        if existing:
            return existing

        repost = PostRepost(original_post_id=post_id, user_id=user_id, tenant_id=tenant_id)
        self.db.add(repost)

        # Create a matching Post record that marks it as is_repost=True
        original_post = self.get_post_by_id(post_id, tenant_id)
        if original_post:
            original_post.repost_count = (original_post.repost_count or 0) + 1

            repost_post_record = Post(
                content=original_post.content,
                author_id=user_id,
                tenant_id=tenant_id,
                is_repost=True,
                original_post_id=post_id,
                visibility=original_post.visibility
            )
            self.db.add(repost_post_record)

        self.db.commit()
        self.db.refresh(repost)
        return repost

    def remove_repost(self, post_id: int, user_id: int, tenant_id: str = "default") -> bool:
        """Remove a repost."""
        repost = self.db.query(PostRepost).filter(
            PostRepost.original_post_id == post_id,
            PostRepost.user_id == user_id,
            PostRepost.tenant_id == tenant_id
        ).first()

        if not repost:
            return False

        self.db.delete(repost)

        # Also find and remove the matching Post record marked as repost
        repost_post = self.db.query(Post).filter(
            Post.author_id == user_id,
            Post.original_post_id == post_id,
            Post.is_repost,
            Post.tenant_id == tenant_id
        ).first()
        if repost_post:
            self.db.delete(repost_post)

        # Decrement counter
        original_post = self.get_post_by_id(post_id, tenant_id)
        if original_post:
            original_post.repost_count = max(0, (original_post.repost_count or 1) - 1)

        self.db.commit()
        return True

    # ==========================================
    # DRAFTS
    # ==========================================

    def create_draft(self, draft_in: DraftCreate, author_id: int, tenant_id: str = "default") -> Draft:
        """Save a new post draft."""
        draft = Draft(
            content=draft_in.content,
            author_id=author_id,
            tenant_id=tenant_id
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def get_draft_by_id(self, draft_id: int, tenant_id: str = "default") -> Optional[Draft]:
        """Fetch a specific draft."""
        return self.db.query(Draft).filter(
            Draft.id == draft_id,
            Draft.tenant_id == tenant_id
        ).first()

    def list_drafts(self, user_id: int, tenant_id: str = "default") -> List[Draft]:
        """Get all drafts belonging to a user."""
        return self.db.query(Draft).filter(
            Draft.author_id == user_id,
            Draft.tenant_id == tenant_id
        ).order_by(desc(Draft.created_at)).all()

    def update_draft(self, draft: Draft, draft_in: DraftUpdate) -> Draft:
        """Update an existing draft's contents."""
        for field, value in draft_in.model_dump(exclude_unset=True).items():
            setattr(draft, field, value)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def delete_draft(self, draft: Draft) -> bool:
        """Delete a draft."""
        self.db.delete(draft)
        self.db.commit()
        return True

    # ==========================================
    # BOOKMARKS (SAVED POSTS)
    # ==========================================

    def save_post(self, post_id: int, user_id: int, tenant_id: str = "default") -> Optional[SavedPost]:
        """Bookmark a post."""
        existing = self.db.query(SavedPost).filter(
            SavedPost.post_id == post_id,
            SavedPost.user_id == user_id,
            SavedPost.tenant_id == tenant_id
        ).first()

        if existing:
            return existing

        saved = SavedPost(post_id=post_id, user_id=user_id, tenant_id=tenant_id)
        self.db.add(saved)
        self.db.commit()
        self.db.refresh(saved)
        return saved

    def unsave_post(self, post_id: int, user_id: int, tenant_id: str = "default") -> bool:
        """Remove a post bookmark."""
        saved = self.db.query(SavedPost).filter(
            SavedPost.post_id == post_id,
            SavedPost.user_id == user_id,
            SavedPost.tenant_id == tenant_id
        ).first()

        if not saved:
            return False

        self.db.delete(saved)
        self.db.commit()
        return True

    def list_saved_posts(self, user_id: int, tenant_id: str = "default", skip: int = 0, limit: int = 20) -> List[Post]:
        """Fetch all posts bookmarked by a user."""
        saved_entries = self.db.query(SavedPost).filter(
            SavedPost.user_id == user_id,
            SavedPost.tenant_id == tenant_id
        ).order_by(desc(SavedPost.created_at)).offset(skip).limit(limit).all()

        return [entry.post for entry in saved_entries if entry.post]

    # ==========================================
    # TAGS / HASHTAGS
    # ==========================================

    def get_or_create_tag(self, tag_name: str, tenant_id: str = "default") -> Tag:
        """Get tag by name or create it if missing."""
        name_clean = tag_name.lower().strip().replace("#", "")
        tag = self.db.query(Tag).filter(
            Tag.name == name_clean,
            Tag.tenant_id == tenant_id
        ).first()

        if not tag:
            tag = Tag(name=name_clean, tenant_id=tenant_id)
            self.db.add(tag)
            self.db.commit()
            self.db.refresh(tag)
        return tag

    def link_tag_to_post(self, post_id: int, tag_id: int):
        """Link a hashtag to a post."""
        existing = self.db.query(PostTag).filter(
            PostTag.post_id == post_id,
            PostTag.tag_id == tag_id
        ).first()

        if not existing:
            post_tag = PostTag(post_id=post_id, tag_id=tag_id)
            self.db.add(post_tag)

            # Update stats
            stats = self.db.query(HashtagStats).filter(
                HashtagStats.tag_id == tag_id
            ).first()
            if not stats:
                stats = HashtagStats(tag_id=tag_id, usage_count=1)
                self.db.add(stats)
            else:
                stats.usage_count = (stats.usage_count or 0) + 1

            self.db.commit()

    def get_posts_by_tag(self, tag_name: str, tenant_id: str = "default", skip: int = 0, limit: int = 20) -> List[Post]:
        """Find all posts with a specific hashtag."""
        name_clean = tag_name.lower().strip().replace("#", "")
        tag = self.db.query(Tag).filter(
            Tag.name == name_clean,
            Tag.tenant_id == tenant_id
        ).first()

        if not tag:
            return []

        return self.db.query(Post).join(PostTag).filter(
            PostTag.tag_id == tag.id,
            Post.tenant_id == tenant_id
        ).order_by(desc(Post.created_at)).offset(skip).limit(limit).all()

    def list_trending_tags(self, tenant_id: str = "default", limit: int = 10) -> List[Tuple[Tag, int]]:
        """List trending tags by usage count."""
        results = self.db.query(Tag, HashtagStats.usage_count).join(HashtagStats).filter(
            Tag.tenant_id == tenant_id
        ).order_by(desc(HashtagStats.usage_count)).limit(limit).all()
        return results

    # ==========================================
    # MEDIA
    # ==========================================

    def create_media(self, post_id: int, url: str, media_type: str = "image", meta: Optional[dict] = None, tenant_id: str = "default") -> Media:
        """Attach a media file to a post."""
        media = Media(
            post_id=post_id,
            url=url,
            media_type=media_type,
            meta=meta,
            tenant_id=tenant_id
        )
        self.db.add(media)
        self.db.commit()
        self.db.refresh(media)
        return media

    def replace_media(self, post_id: int, media_items: List[MediaCreate], tenant_id: str = "default") -> None:
        """Replace all media attachments for a post."""
        self.db.query(Media).filter(
            Media.post_id == post_id,
            Media.tenant_id == tenant_id,
        ).delete(synchronize_session=False)

        for item in media_items:
            url = item.url if hasattr(item, "url") else item.get("url")
            media_type = item.media_type if hasattr(item, "media_type") else item.get("media_type", "image")
            meta = item.meta if hasattr(item, "meta") else item.get("meta")
            self.db.add(Media(
                post_id=post_id,
                url=url,
                media_type=media_type,
                meta=meta,
                tenant_id=tenant_id,
            ))

    # ==========================================
    # POLLS
    # ==========================================

    def create_poll(self, post_id: int, poll_in: PollCreate, tenant_id: str = "default") -> Poll:
        """Attach a poll to a post."""
        poll = Poll(
            post_id=post_id,
            question=poll_in.question.strip(),
            tenant_id=tenant_id,
        )
        self.db.add(poll)
        self.db.flush()

        for option_text in poll_in.options:
            option = PollOption(
                poll_id=poll.id,
                text=option_text.strip(),
                tenant_id=tenant_id,
            )
            self.db.add(option)

        self.db.commit()
        self.db.refresh(poll)
        return poll

    def vote_poll(self, post_id: int, option_id: int, user_id: int, tenant_id: str = "default") -> Optional[Poll]:
        """Create or move a user's poll vote and keep option counters correct."""
        poll = self.db.query(Poll).filter(
            Poll.post_id == post_id,
            Poll.tenant_id == tenant_id,
        ).first()
        if not poll:
            return None

        option = self.db.query(PollOption).filter(
            PollOption.id == option_id,
            PollOption.poll_id == poll.id,
            PollOption.tenant_id == tenant_id,
        ).first()
        if not option:
            return None

        existing = self.db.query(PollVote).filter(
            PollVote.poll_id == poll.id,
            PollVote.user_id == user_id,
            PollVote.tenant_id == tenant_id,
        ).first()

        if existing and existing.option_id == option_id:
            return poll

        if existing:
            previous = self.db.query(PollOption).filter(PollOption.id == existing.option_id).first()
            if previous:
                previous.vote_count = max(0, (previous.vote_count or 0) - 1)
            existing.option_id = option_id
        else:
            self.db.add(PollVote(
                poll_id=poll.id,
                option_id=option_id,
                user_id=user_id,
                tenant_id=tenant_id,
            ))

        option.vote_count = (option.vote_count or 0) + 1
        self.db.commit()
        self.db.refresh(poll)
        return poll
