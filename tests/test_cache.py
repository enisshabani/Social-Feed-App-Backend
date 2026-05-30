"""
KaPak - Cache Tests (P4-035)
Unit tests for InMemoryCache + API integration tests for cache hit/miss on endpoints.
"""

import time

from app.core.cache import cache_service


# ==========================================
# UNIT: InMemoryCache / Cache facade
# ==========================================

def test_cache_set_get():
    cache_service.set("test_key", {"foo": "bar"}, expire_seconds=300)
    result = cache_service.get("test_key")
    assert result == {"foo": "bar"}


def test_cache_get_missing_key():
    result = cache_service.get("nonexistent_key_12345")
    assert result is None


def test_cache_delete():
    cache_service.set("delete_me", "value", expire_seconds=300)
    cache_service.delete("delete_me")
    assert cache_service.get("delete_me") is None


def test_cache_invalidate_prefix():
    cache_service.set("feed:page1", {"data": 1})
    cache_service.set("feed:page2", {"data": 2})
    cache_service.set("other:data", {"data": 3})

    cache_service.invalidate_prefix("feed:")

    assert cache_service.get("feed:page1") is None
    assert cache_service.get("feed:page2") is None
    assert cache_service.get("other:data") == {"data": 3}


def test_cache_ttl_expiration():
    cache_service.set("short_lived", "ephemeral", expire_seconds=1)
    assert cache_service.get("short_lived") == "ephemeral"
    time.sleep(1.5)
    assert cache_service.get("short_lived") is None


def test_cache_overwrite():
    cache_service.set("overwrite_key", "first")
    cache_service.set("overwrite_key", "second")
    assert cache_service.get("overwrite_key") == "second"


def test_cache_complex_object():
    nested = {
        "posts": [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": ["c"]}],
        "meta": {"count": 2, "page": 1},
    }
    cache_service.set("complex", nested)
    assert cache_service.get("complex") == nested


def test_cache_boolean_value():
    cache_service.set("bool_true", True)
    cache_service.set("bool_false", False)
    assert cache_service.get("bool_true") is True
    assert cache_service.get("bool_false") is False


def test_cache_list_value():
    cache_service.set("list_key", [1, 2, 3])
    assert cache_service.get("list_key") == [1, 2, 3]


def test_cache_string_value():
    cache_service.set("str_key", "simple string")
    assert cache_service.get("str_key") == "simple string"


def test_cache_delete_nonexistent_key():
    cache_service.delete("never_stored")
    assert cache_service.get("never_stored") is None


# ==========================================
# API INTEGRATION: cache hit/miss on endpoints (P4-035)
# ==========================================

FAKE_ITEM = {
    "id": 999,
    "content": "CACHED_CONTENT",
    "content_html": None,
    "author_id": 1,
    "author": None,
    "visibility": "public",
    "is_repost": False,
    "original_post_id": None,
    "like_count": 0,
    "reply_count": 0,
    "repost_count": 0,
    "created_at": "2026-01-01T00:00:00",
    "likes": [],
}

FAKE_FEED = {
    "items": [FAKE_ITEM],
    "next_cursor": None,
    "has_more": False,
}


def test_feed_cache_hit_returns_cached_data(test_client):
    cache_service.set("feed:default:0:20", FAKE_FEED, expire_seconds=300)

    res = test_client.get("/api/v1/feeds/home")
    assert res.status_code == 200
    data = res.json()
    assert data["items"][0]["id"] == 999
    assert data["items"][0]["content"] == "CACHED_CONTENT"


def test_feed_cache_miss_falls_through_to_db(test_client):
    test_client.post("/api/v1/posts/", json={
        "content": "Post to populate feed cache", "visibility": "public",
    })

    res = test_client.get("/api/v1/feeds/home")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["content"] == "Post to populate feed cache"


def test_post_cache_hit(test_client):
    payload = {"content": "Original post for cache test", "visibility": "public"}
    post_res = test_client.post("/api/v1/posts/", json=payload)
    post_id = post_res.json()["id"]

    res1 = test_client.get(f"/api/v1/posts/{post_id}")
    assert res1.status_code == 200
    real_post = res1.json()

    fake_post = real_post.copy()
    fake_post["content"] = "INJECTED_CACHED_VALUE"
    cache_service.set(f"post:default:{post_id}", fake_post, expire_seconds=300)

    res2 = test_client.get(f"/api/v1/posts/{post_id}")
    assert res2.status_code == 200
    assert res2.json()["content"] == "INJECTED_CACHED_VALUE"


def test_post_creation_invalidates_feed_cache(test_client):
    cache_service.set("feed:default:0:20", {"cached": True}, expire_seconds=300)
    assert cache_service.get("feed:default:0:20") is not None

    test_client.post("/api/v1/posts/", json={
        "content": "This post invalidates the feed cache", "visibility": "public",
    })

    assert cache_service.get("feed:default:0:20") is None
