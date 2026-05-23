"""
KaPak - Post Service
Business Logic Layer for validating, filtering, formatting posts, parsing tags, and managing workflows.
"""

import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.repositories.post_repo import PostRepository
from app.models.post import Post, Comment, PostLike, PostRepost, Draft, SavedPost
from app.schemas.post import PostCreate, PostUpdate, CommentCreate, DraftCreate, DraftUpdate, MediaCreate
from app.core.hashtag_utils import link_hashtags_to_post


class PostService:
    """Service class containing business logic for posts, hashtags, comments, and drafts."""

    def __init__(self, db: Session):
        self.repo = PostRepository(db)

    # Regex patterns for parsing content
    HASHTAG_REGEX = re.compile(r"#(\w+)")
    MENTION_REGEX = re.compile(r"@(\w+)")

    # ==========================================
    # CORE POST BUSINESS LOGIC
    # ==========================================

    def create_post(self, post_in: PostCreate, author_id: int, tenant_id: str = "default", media_in: Optional[List[MediaCreate]] = None) -> Post:
        """Create a post, parse hashtags/mentions, enrich with HTML, and attach media."""
        # 1. Parse and generate HTML content representation
        content_html = self._enrich_content_to_html(post_in.content)
        
        # 2. Create the post in DB
        # Temp modification to set html content since schema doesn't pass content_html directly
        post = self.repo.create_post(post_in, author_id, tenant_id)
        post.content_html = content_html
        self.repo.db.commit()

        # 3. Parse and associate hashtags
        hashtags = self._extract_hashtags(post_in.content)
        for tag_name in hashtags:
            tag = self.repo.get_or_create_tag(tag_name, tenant_id)
            self.repo.link_tag_to_post(post.id, tag.id)

        # 3b. Also write to the new Hashtag/ContentHashtag system (for trending)
        link_hashtags_to_post(post.id, hashtags, self.repo.db, tenant_id)

        # 4. Attach media if provided
        if media_in:
            for item in media_in:
                self.repo.create_media(post.id, item.url, item.media_type, item.meta, tenant_id)

        self.repo.db.refresh(post)
        return post

    def get_post(self, post_id: int, tenant_id: str = "default") -> Optional[Post]:
        """Retrieve a specific post."""
        return self.repo.get_post_by_id(post_id, tenant_id)

    def list_feed(self, tenant_id: str = "default", skip: int = 0, limit: int = 20) -> List[Post]:
        """Fetch general public home feed posts."""
        return self.repo.list_posts(tenant_id, skip, limit)

    def list_user_timeline(self, user_id: int, tenant_id: str = "default", skip: int = 0, limit: int = 20) -> List[Post]:
        """Fetch posts made by a specific user for their timeline."""
        return self.repo.list_user_posts(user_id, tenant_id, skip, limit)

    def update_post(self, post_id: int, post_in: PostUpdate, author_id: int, tenant_id: str = "default") -> Optional[Post]:
        """Update post content and refresh HTML enrichment & hashtags if content changed."""
        post = self.repo.get_post_by_id(post_id, tenant_id)
        if not post or post.author_id != author_id:
            return None

        # Process text updates
        if post_in.content is not None:
            post.content_html = self._enrich_content_to_html(post_in.content)
            
            # Re-process hashtags (simple version: add newly parsed ones)
            hashtags = self._extract_hashtags(post_in.content)
            for tag_name in hashtags:
                tag = self.repo.get_or_create_tag(tag_name, tenant_id)
                self.repo.link_tag_to_post(post.id, tag.id)

            # Also write to the new Hashtag/ContentHashtag system (for trending)
            link_hashtags_to_post(post.id, hashtags, self.repo.db, tenant_id)

        return self.repo.update_post(post, post_in)

    def delete_post(self, post_id: int, author_id: int, tenant_id: str = "default") -> bool:
        """Delete a post if authorized."""
        post = self.repo.get_post_by_id(post_id, tenant_id)
        if not post or post.author_id != author_id:
            return False
        return self.repo.delete_post(post)

    # ==========================================
    # COMMENT BUSINESS LOGIC
    # ==========================================

    def add_comment(self, post_id: int, comment_in: CommentCreate, author_id: int, tenant_id: str = "default") -> Optional[Comment]:
        """Add comment to a valid post."""
        post = self.repo.get_post_by_id(post_id, tenant_id)
        if not post:
            return None
        return self.repo.create_comment(comment_in, post_id, author_id, tenant_id)

    def remove_comment(self, comment_id: int, author_id: int, tenant_id: str = "default") -> bool:
        """Remove comments if authorized."""
        comment = self.repo.get_comment_by_id(comment_id, tenant_id)
        if not comment or comment.author_id != author_id:
            return False
        return self.repo.delete_comment(comment)

    # ==========================================
    # LIKE & REPOST BUSINESS LOGIC
    # ==========================================

    def toggle_like(self, post_id: int, user_id: int, tenant_id: str = "default") -> Tuple[bool, str]:
        """Toggle post like state. Returns (is_liked, message)."""
        post = self.repo.get_post_by_id(post_id, tenant_id)
        if not post:
            return False, "Post not found"

        # Check if already liked
        liked = self.repo.db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
            PostLike.tenant_id == tenant_id
        ).first()

        if liked:
            self.repo.remove_like(post_id, user_id, tenant_id)
            return False, "Post unliked successfully"
        else:
            self.repo.create_like(post_id, user_id, tenant_id)
            return True, "Post liked successfully"

    def toggle_repost(self, post_id: int, user_id: int, tenant_id: str = "default") -> Tuple[bool, str]:
        """Toggle post repost state. Returns (is_reposted, message)."""
        post = self.repo.get_post_by_id(post_id, tenant_id)
        if not post:
            return False, "Post not found"

        # Check if already reposted
        reposted = self.repo.db.query(PostRepost).filter(
            PostRepost.original_post_id == post_id,
            PostRepost.user_id == user_id,
            PostRepost.tenant_id == tenant_id
        ).first()

        if reposted:
            self.repo.remove_repost(post_id, user_id, tenant_id)
            return False, "Repost removed successfully"
        else:
            self.repo.create_repost(post_id, user_id, tenant_id)
            return True, "Post reposted successfully"

    # ==========================================
    # DRAFTS BUSINESS LOGIC
    # ==========================================

    def create_draft(self, draft_in: DraftCreate, author_id: int, tenant_id: str = "default") -> Draft:
        """Save a new draft."""
        return self.repo.create_draft(draft_in, author_id, tenant_id)

    def publish_draft(self, draft_id: int, author_id: int, tenant_id: str = "default") -> Optional[Post]:
        """Convert a saved draft to a live post and delete draft."""
        draft = self.repo.get_draft_by_id(draft_id, tenant_id)
        if not draft or draft.author_id != author_id:
            return None

        # Build PostCreate from draft
        post_in = PostCreate(
            content=draft.content,
            visibility="public"
        )
        
        # Publish live post
        post = self.create_post(post_in, author_id, tenant_id)
        
        # Remove draft
        self.repo.delete_draft(draft)
        return post

    # ==========================================
    # BOOKMARKS / SAVED POSTS
    # ==========================================

    def toggle_bookmark(self, post_id: int, user_id: int, tenant_id: str = "default") -> Tuple[bool, str]:
        """Toggle post bookmark state."""
        post = self.repo.get_post_by_id(post_id, tenant_id)
        if not post:
            return False, "Post not found"

        existing = self.repo.db.query(SavedPost).filter(
            SavedPost.post_id == post_id,
            SavedPost.user_id == user_id,
            SavedPost.tenant_id == tenant_id
        ).first()

        if existing:
            self.repo.unsave_post(post_id, user_id, tenant_id)
            return False, "Post removed from bookmarks"
        else:
            self.repo.save_post(post_id, user_id, tenant_id)
            return True, "Post saved to bookmarks"

    # ==========================================
    # SEARCH & EXPLORE BUSINESS LOGIC
    # ==========================================

    def search_posts_by_tag(self, tag: str, tenant_id: str = "default", skip: int = 0, limit: int = 20) -> List[Post]:
        """Search posts by hashtag."""
        return self.repo.get_posts_by_tag(tag, tenant_id, skip, limit)

    def get_trending_hashtags(self, tenant_id: str = "default", limit: int = 10) -> List[dict]:
        """Retrieve trending tag names with statistics."""
        results = self.repo.list_trending_tags(tenant_id, limit)
        return [{"tag": tag.name, "usage_count": count} for tag, count in results]

    # ==========================================
    # HELPERS
    # ==========================================

    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtag strings from text."""
        return list(set(self.HASHTAG_REGEX.findall(text)))

    def _enrich_content_to_html(self, text: str) -> str:
        """Convert hashtags and mentions to interactive HTML spans."""
        enriched = text
        # Convert hashtags: #hello -> <span class="hashtag">#hello</span>
        enriched = self.HASHTAG_REGEX.sub(r'<span class="hashtag">#\1</span>', enriched)
        # Convert mentions: @user -> <span class="mention">@user</span>
        enriched = self.MENTION_REGEX.sub(r'<span class="mention">@\1</span>', enriched)
        return enriched
