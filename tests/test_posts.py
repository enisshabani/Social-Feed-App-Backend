"""
KaPak - Posts & Feeds API Tests
Verifies all posts, comments, likes, reposts, bookmarks, drafts, and AI refinement endpoints.
"""

import pytest


# ==========================================
# TEST CASES
# ==========================================

def test_create_post(test_client):
    """Verify creating a post parses tags/mentions and builds HTML content."""
    payload = {
        "content": "Hello #world, this is @testuser!",
        "visibility": "public"
    }
    response = test_client.post("/api/v1/posts/", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["content"] == payload["content"]
    assert data["author_id"] == 1
    assert '<span class="hashtag">#world</span>' in data["content_html"]
    assert '<span class="mention">@testuser</span>' in data["content_html"]


def test_get_single_post(test_client):
    """Verify fetching post detail and relationships."""
    payload = {"content": "Detail post", "visibility": "public"}
    post_res = test_client.post("/api/v1/posts/", json=payload)
    post_id = post_res.json()["id"]

    response = test_client.get(f"/api/v1/posts/{post_id}")
    assert response.status_code == 200
    assert response.json()["id"] == post_id
    assert response.json()["content"] == "Detail post"


def test_like_post_toggle(test_client):
    """Verify liking and unliking a post updates counters."""
    post_res = test_client.post("/api/v1/posts/", json={"content": "Liking post", "visibility": "public"})
    post_id = post_res.json()["id"]

    response = test_client.post(f"/api/v1/posts/{post_id}/like")
    assert response.status_code == 200
    assert response.json()["liked"] is True
    assert "liked successfully" in response.json()["message"]

    detail_res = test_client.get(f"/api/v1/posts/{post_id}")
    assert detail_res.json()["like_count"] == 1

    response = test_client.post(f"/api/v1/posts/{post_id}/like")
    assert response.status_code == 200
    assert response.json()["liked"] is False
    assert "unliked successfully" in response.json()["message"]

    detail_res = test_client.get(f"/api/v1/posts/{post_id}")
    assert detail_res.json()["like_count"] == 0


def test_post_comment(test_client):
    """Verify adding comments to a post."""
    post_res = test_client.post("/api/v1/posts/", json={"content": "Post with comment", "visibility": "public"})
    post_id = post_res.json()["id"]

    payload = {"content": "This is a great post!"}
    response = test_client.post(f"/api/v1/posts/{post_id}/comments", json=payload)
    assert response.status_code == 201
    assert response.json()["content"] == payload["content"]
    assert response.json()["post_id"] == post_id


def test_repost_post(test_client):
    """Verify reposting toggles correctly."""
    post_res = test_client.post("/api/v1/posts/", json={"content": "Original Post", "visibility": "public"})
    post_id = post_res.json()["id"]

    response = test_client.post(f"/api/v1/posts/{post_id}/repost")
    assert response.status_code == 200
    assert response.json()["reposted"] is True

    detail_res = test_client.get(f"/api/v1/posts/{post_id}")
    assert detail_res.json()["repost_count"] == 1


def test_draft_publish(test_client):
    """Verify saving a draft and publishing it as a post."""
    payload = {"content": "This is a draft content."}
    draft_res = test_client.post("/api/v1/posts/drafts/save", json=payload)
    assert draft_res.status_code == 201
    draft_id = draft_res.json()["id"]

    drafts_list = test_client.get("/api/v1/posts/drafts/all")
    assert len(drafts_list.json()) == 1

    publish_res = test_client.post(f"/api/v1/posts/drafts/{draft_id}/publish")
    assert publish_res.status_code == 201
    assert publish_res.json()["content"] == payload["content"]

    drafts_list = test_client.get("/api/v1/posts/drafts/all")
    assert len(drafts_list.json()) == 0


def test_ai_text_refinement(test_client):
    """Verify AI text refinement works with mock fallback."""
    payload = {"content": "This is raw input text", "style": "professional"}
    response = test_client.post("/api/v1/posts/refine-ai", json=payload)
    assert response.status_code == 200
    assert "refined_content" in response.json()
    assert "#Professional" in response.json()["refined_content"]


def test_get_feeds(test_client):
    """Verify home, explore, and tag feed endpoints."""
    test_client.post("/api/v1/posts/", json={"content": "Tag test #cooltag", "visibility": "public"})

    home_feed = test_client.get("/api/v1/feeds/home")
    assert home_feed.status_code == 200
    assert len(home_feed.json()["items"]) == 1

    explore = test_client.get("/api/v1/feeds/explore")
    assert explore.status_code == 200
    assert len(explore.json()) == 1
    assert explore.json()[0]["tag"] == "cooltag"

    tag_feed = test_client.get("/api/v1/feeds/tag/cooltag")
    assert tag_feed.status_code == 200
    assert len(tag_feed.json()["items"]) == 1


def test_home_feed_includes_root_posts_and_excludes_replies(test_client):
    root_res = test_client.post("/api/v1/posts/", json={"content": "Root feed post", "visibility": "public"})
    root_id = root_res.json()["id"]
    test_client.post(f"/api/v1/posts/{root_id}/comments", json={"content": "Reply should stay out of home feed"})

    home_feed = test_client.get("/api/v1/feeds/home")

    assert home_feed.status_code == 200
    items = home_feed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == root_id
